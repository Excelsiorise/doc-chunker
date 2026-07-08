# 决策记录（DECISIONS.md）

设计取舍记录。每条格式:决策 → 备选方案 → 选择理由 → 接口/边界 → 状态。
按时间顺序追加,不回填修改历史决策(如推翻,新增一条并标注"取代 D00x")。

---

## D001: 集成方式选型 — 独立 Python 包 + entry_points Tool 适配层(倾向,未最终拍板)

**日期**: 2026-07-06
**背景**: 在写任何代码前,先调研了 nanobot 现有的四种扩展机制:内嵌 Tool、内嵌 Skill、独立包 +
Python 层适配、MCP server。调研方法是直接读源码而非猜测,关键依据:

- Tool 基类与注册链路:`nanobot/agent/tools/base.py`(`Tool` ABC)、
  `nanobot/agent/tools/registry.py`(`ToolRegistry.execute()` 做校验+调用)、
  `nanobot/agent/tools/loader.py`(`ToolLoader.discover()` 包内 pkgutil 扫描 +
  `ToolLoader._discover_plugins()` 用 `entry_points(group="nanobot.tools")` 发现外部插件)。
- Skill 机制:`nanobot/agent/skills.py`(`SkillsLoader`),Skill 本质是 Markdown prompt
  片段,没有代码执行、没有参数校验,靠已有 Tool(shell/curl 等)完成实际动作。
- entry_points 声明模板:`pyproject.toml:149-152`
  (`[project.entry-points."nanobot.tools"]`),证实这是官方预留的第三方 Tool 插件入口。
- MCP client 实现:`nanobot/agent/tools/mcp.py`(远程工具被 `_MCPWrapperBase(Tool)`
  包装后混入同一个 `ToolRegistry`),配置见 `docs/configuration.md`(`tools.mcpServers`,
  支持 stdio/HTTP 两种 transport)。

**四种方式对比**(改动侵入性 / 可独立测试性 / 复用性 / 调用成本):

| 维度 | 内嵌 Tool | 内嵌 Skill | 独立包 + entry_points | MCP server |
|---|---|---|---|---|
| 改动侵入性 | 高——直接改 nanobot 源码仓库,升级需手动合并 | 低——只加一个 markdown 目录,不碰代码 | 低——nanobot 零代码改动,仅需 pip install 到同一环境并声明 entry-points | 最低——纯 config.json 加一段 JSON |
| 可独立测试性 | 中——Tool 类本身可单测,全链路需起 nanobot | 低——没有可测逻辑,本质是 prompt 文本 | 高——独立可安装 Python 项目,与 nanobot 完全解耦,可自带 CI | 最高——独立进程+标准协议,任意 MCP client/curl 可验证 |
| 复用性(跳出 nanobot) | 低——只能在这个 nanobot checkout 里用 | 中——manifest 兼容 OpenClaw 生态,但实际复用性取决于背后调用的 shell 命令是否可移植 | 高——同一个包可再包一层同时对外提供 CLI/库 API/MCP server | 最高——任何遵循 MCP 协议的 client 都能直接接,语言无关 |
| 调用成本 | 最低——同进程函数调用 | 低——不产生新调用路径 | 低——同进程,仅多一层可选的 legacy-error 包装 | 最高——JSON-RPC 序列化 + stdio/网络往返,HTTP 模式还要过 SSRF 校验 |

**选择理由**: 面试考察点是"设计思维"和模块本身的分块能力,不是插件框架能力。独立包 +
entry_points 能在零侵入 nanobot 源码的前提下,把 chunker 做成可独立单测、可独立发布的项目,
同时保留"确实接入了 nanobot"这条完整闭环。MCP 成本更高(需要维护独立进程/协议层),
收益(语言无关、被其他 agent 复用)在本次面试范围内不是刚需,列为**可选的第二层 adapter**,
不是首选路径。纯内嵌 Tool 因为要求候选人改 nanobot 仓库本身,侵入性最高、复用性最低,排除。
纯 Skill 因为不能执行真正的分块代码逻辑,只能作为"何时/如何调用 chunker 工具"的说明书,不能
替代 Tool,排除单独使用。

**接口/边界(初步)**:
- 核心分块逻辑作为独立、无 nanobot 依赖的 Python 库存在,可脱离 nanobot 单测。
- 通过一个薄适配层类(继承 nanobot 的 `Tool` ABC,实现 `name`/`description`/`parameters`/
  `execute()`)暴露给 nanobot,在自己包的 `pyproject.toml` 声明
  `[project.entry-points."nanobot.tools"]`。
- 返回值遵循 nanobot 约定:正常返回可 `str()` 化内容,失败返回 `ToolResult.error(...)`
  而非裸抛异常或 `"Error:"` 前缀字符串(后者是 nanobot 为老插件保留的兼容层,不应作为新代码的
  目标契约)。

**状态**: 倾向性结论,尚未开始实现,后续如有变化以新条目记录并注明"取代 D001"。

---

## D002(待决策,尚未拍板): 分块产出物(chunk 数据)存放位置

**日期**: 2026-07-06
**背景**: 调研发现 nanobot **目前没有任何分块/索引存储惯例可参照**——现有文档导入实现在
`nanobot/utils/document.py`(`extract_text`/`extract_documents`),被
`nanobot/agent/loop.py:1472-1480`(`_prepare_message_media`)在消息进入时调用,做法是把整篇
文档全文抽出来直接拼进对话 `content`(单文件限 200k 字符截断),**没有切块、没有向量化、没有
持久化**。这正是本项目要填补的空白,而不是要去符合一个已经存在的分块惯例。

**已识别的两个可参照惯例**(均来自实际读码,非猜测):
1. workspace 级:仿 `<workspace>/memory/` 的做法,开一个 `<workspace>/doc_index/` 子目录,
   优点是 agent 能直接用内置 `read_file`/`grep` 浏览分块结果。
2. 实例级:仿 `nanobot/utils/artifacts.py` 的 `store_generated_image_artifact()` 惯例——
   按天分桶 + 内容文件与 JSON 元数据 sidecar 同名并列,路径必须 `resolve()` 后落在
   `get_media_dir()` 根目录内部(防目录穿越),对应实现 `get_runtime_subdir("doc_index")` →
   `~/.nanobot/doc_index/<doc_id>/{chunks.jsonl, index.sqlite}` + `manifest.json`。取舍在于
   是否要把原始分块内容暴露给通用文件工具,还是只通过本模块自己的查询接口暴露检索结果。

**状态**: 未决策。取决于后续设计的检索接口是"返回文本片段"还是"允许 agent 直接浏览分块文件",
需要在开始实现前明确,并在本文件补充一条新决策。

---

## D003: 第一版存储与检索接口 — 本地 JSONL + manifest, Tool 返回检索片段

**日期**: 2026-07-06
**背景**: D002 里识别了两个方向:把 chunk 文件放在 workspace 里供通用文件工具浏览,或放在模块自己的
store 目录里通过查询接口暴露。结合 48 小时题目要求,第一版优先证明"解析 → 上下文感知分块 →
持久化 → 查询/集成"的小闭环,不把重点放到 nanobot 文件浏览体验上。

**决策**: 第一版实现一个独立 `DocumentStore`,每个索引目录包含:
- `manifest.json`: 文档 ID、源文件、chunk 数量、创建时间、分块参数、解析器摘要。
- `chunks.jsonl`: 每行一个 chunk,包含 `chunk_id`、`doc_id`、`text`、`source_file`、`locator`
  (如页码/sheet/段落序号)、`heading_path`、`prev_chunk_id`、`next_chunk_id`、`metadata`。

检索接口第一版做关键词包含式 search,返回带上下文元数据的片段列表。nanobot Tool 不直接让 agent
浏览内部文件,而是提供两个 action:
- `ingest`: 解析并分块一个本地文档,写入 store。
- `search`: 在已有 store 中按关键词返回相关 chunk。

**备选方案**:
- SQLite: 查询更强,但第一版 schema/migration/调试成本更高;可作为后续增强。
- workspace 可浏览目录: 对 agent 透明,但会把模块内部格式暴露成长期接口,且题目重点不是文件浏览。
- MCP server: 复用性更高,但协议层成本超过本次闭环所需。

**选择理由**: JSONL 便于人工检查、测试、demo 和面试解释;manifest 可以把验证需要的元数据固定下来;
Tool 返回片段能清楚对接下游检索/生成模块,符合题目"与下游的集成方式讲清楚"的要求。

**接口/边界**:
- 核心库不 import nanobot。
- nanobot adapter 只负责参数 schema、调用核心库、把结果转成 JSON 字符串或 `ToolResult.error(...)`。
- 第一版 search 是确定性关键词匹配,不做向量库和 embedding 训练。

**状态**: 已拍板,作为第一版实现依据。

---

## D003: `doc_id` = 路径哈希,不做版本链

**日期**: 2026-07-06
**背景**: 数据模型设计第一轮里列了三个方案(路径派生 / 内容哈希 / 显式分配+version)。
**选择**: `doc_id = sha256(规范化绝对路径)[:16]`。同一路径 = 同一逻辑文档,不管内容怎么改。
**理由**: 面试要求"自洽的小闭环",优先选心智模型最简单、新手一看就懂的方案——"同一个文件永远
是同一个文档"符合直觉,不需要引入"版本"概念。`content_hash`(文件字节哈希)保留,但只用于
判断"文件是否变过、要不要重新解析",不驱动任何版本链或增量 diff 逻辑。
**接口/边界**: 重新导入同一路径的文档 = 把该 `doc_id` 下所有旧 chunk 删除、全量重新分块,
不做增量更新。`Document.version` 字段(D001 讨论稿里提到的)**不采用**。
**状态**: 已确认。

---

## D004: `chunk_id` = 方案 A(顺序位置式),取代方案 B/C 的候选讨论

**日期**: 2026-07-06
**背景**: 数据模型设计第一轮给了 3 个 chunk_id 命名方案(顺序位置式 / 内容哈希式 / 结构路径式),
当时倾向内容哈希式(方案B),理由是"增量更新时更稳定"。
**选择**: `chunk_id = f"{doc_id}:{chunk_index:06d}"`(方案 A)。
**理由**: 这是一个由 D003 直接推导出的简化——既然"重新导入 = 全量替换"已经是既定策略,
"chunk_id 在文档局部编辑后要不要保持稳定"这个问题本身就不再存在:旧 chunk 整批作废、
新 chunk 整批重新生成,没有谁需要跨编辑前后保持同一个 ID。内容哈希式方案(B)原本要解决的
正是这个不再存在的问题,继续选它是在为一个已经不存在的需求付复杂度成本(哈希计算、
重复文本消歧)。这是"一个存储层决策消掉一个 ID 设计层复杂决策"的典型例子。
**接口/边界**: `chunk_index` 是文档内的顺序号(从 0 起),`chunk_id` 由它和 `doc_id` 拼接生成,
不依赖 chunk 文本内容。`content_hash` 字段仍保留在 Chunk 上,但只用于未来可能的去重场景,
不参与 `chunk_id` 生成。
**状态**: 已确认,取代 D001 讨论稿里对方案 B 的倾向性表述。

---

## D005: `chunk_type` 简化为 `{narrative, heading_only, table}`,去掉 `list`

**日期**: 2026-07-06
**理由**: 列表渲染成文本后就是若干行带项目符号的段落,分句/分段逻辑不需要为它单独分支,
正文分块器怎么处理段落就怎么处理列表。单独保留 `list` 类型不产生任何下游行为差异,是"为了
分类完整而分类",主动砍掉。`heading_only` 保留,因为它解决一个真实问题:标题后暂无正文时,
避免 `heading_path` 断链或凭空造出一个空 chunk。
**状态**: 已确认。

---

## D006: `header_context` 字段通用化,但 MVP 只实现 Excel

**日期**: 2026-07-06
**理由**: 数据模型上 `header_context` 挂在 `Chunk` 上,任何 `chunk_type == "table"` 都可能有值,
不写死"仅 Excel"——避免以后支持 Word 表格时要改 schema。但**实现范围**这一轮只做 Excel,
Word 表格解析分支留空(`None`),避免现在就为一个不在明确需求里的场景增加解析复杂度。
**接口/边界**: 字段定义通用,实现按格式分阶段补齐。
**状态**: 已确认。

---

## D007: `language_hint` / `token_count` 用轻量启发式,不引入外部 NLP/tokenizer 依赖

**日期**: 2026-07-06
**理由**: 需求是"中文全角标点要正确分句",不是"支持任意语言检测",所以 `language_hint` 用
CJK 字符占比的简单计数判断 `zh`/`en`/`mixed`,不接入 `langdetect`/`fasttext`。`token_count` 用
经验比例估算(如中文约 1 字符≈1 token、英文约 4 字符≈1 token),不接入 `tiktoken` 之类和
具体模型绑定的真实分词器——这个字段只用于下游预算的粗略参考,精确到 ±20% 已经够用,接入
真实 tokenizer 会让存储模块被绑死在某个模型的分词规则上,收益不匹配复杂度。
**状态**: 已确认。

---

## D008: 承认 D003–D007 字段清单与实现的落差,并记录本轮(REVIEW_FINDINGS.md /
TODO.md 驱动)升级的关键取舍

**日期**: 2026-07-07
**背景**: `docs/process/REVIEW_FINDINGS.md`(M1)指出 D003–D007 记录的 `chunk_id` 格式、
`chunk_type` 枚举、完整字段清单等和 `models.py` 实际实现不一致,且这个落差此前被"面试讲稿
只引用当前代码"绕开,而不是显式承认。按 M1 的建议,这里不回改 D003–D007 的历史记录,只显式
声明:**`Chunk`/`DocumentBlock` 的字段清单以当前 `models.py` 为准**,D003–D007 中和实现不符
的部分(尤其是 D005 提到的 `chunk_type` 字段、D006/D007 讨论稿里列出的 `char_offset` /
`token_count` / `content_hash` / `element_ids` 等字段)是设计阶段的候选清单,第一版及本轮实现
做了简化,不代表最终字段集。

**本轮升级实现的决策**(响应 `REVIEW_FINDINGS.md` 和 `TODO.md`,细节见
`docs/process/UPGRADE_SUMMARY.md`):

- **`ChunkStore` 用 `abc.ABC` 而不是 `Protocol`**:`get_by_document`/`get_neighbors`/
  `get_section`/`search`/`validate_export` 只依赖三个抽象方法
  (`write_document`/`load_chunks`/`get_document_info`),所以把它们实现成 ABC 上的具体方法,
  任何新后端只需要实现这三个方法就能免费获得其余全部行为,不需要重复实现一遍——这是
  `tests/test_store_contract.py` 能在不改测试代码的前提下,直接参数化接入下一个后端的前提。
  选 ABC 而不是纯 `Protocol`,是因为需要共享实现代码,不只是共享类型签名。
- **只实现一个后端(`DocumentStore`/JSONL),不再额外做 `InMemoryChunkStore`**:原始需求是
  "至少实现一个内存**或**本地文件后端",不是"两个都要"——`DocumentStore` 已经满足这条。
  最初这一轮实现里加了 `InMemoryChunkStore` 作为第二个后端外加跨后端契约测试,用来更充分地
  证明"换后端不用改调用方代码";讨论后确认这不是原文要求的必需项,且在当前数据规模下
  "内存后端更快"这个常见理由也不成立(JSONL 走 `tmp_path` 跑全部测试也就零点几秒),收益主要是
  "面试展示设计能力"而非实际需要,所以移除,只保留 `ChunkStore` 抽象 + `DocumentStore` 一个
  实现。契约测试(`tests/test_store_contract.py`)保留,`store` fixture 仍然参数化,新增后端
  时只需要在 `_make_store()` 里加一行,不需要改测试本身。
- **`get_section` 是动态聚合,不是物理 parent 块**:按 `TODO.md` P0-2 的取舍,parent
  在本实现中是"同 `heading_path` 的 chunk 集合"这个逻辑视图,查询时现算,不落盘存储、不需要
  第二套 ID 体系、文档更新时不需要双层同步。代价是每次 `expand=section` 都要扫一遍
  `load_chunks()`(当前 O(n) 全量扫描),在 JSONL 单机小数据量场景下可接受;数据量大到需要
  索引时,这里是清晰的优化切入点。
- **分块跨边界规则只看 `heading_path` 和 `block_type` 相等性,不做更细粒度的语义边界**:
  这是 `TODO.md` P0-4 的直接实现,修复了 `REVIEW_FINDINGS.md` C7(合并块时只保留第一个
  block 的 `heading_path`,导致跨标题内容被张冠李戴)。边界触发时**不**做 overlap 尾部拼接
  (只有因为 `max_chars` 溢出触发的 flush 才带 overlap)——跨标题的重叠文本本身就会被贴错
  标签,索性不做。
- **中文分句正则改为不要求标点后有空格**,同时保护小数点(`3.2` 不会被拆成 `3.` / `2`)。
  后者是 `scripts/mini_eval.py` 跑出来的真实回归,不是主动设计的边界情况。
- **`FixedSizeChunker` 作为唯一的第二策略**,不做更多策略(如按 token 数切分):它的角色是
  给 `RecursiveStructureChunker` 提供一个对照基线,`docs/process/EVAL.md` 里的评测表就是
  用它证明"结构边界感知"本身的价值,而不是提供一个真正推荐使用的替代策略。
- **`pip install -e .` 已在本地验证过 entry_points 发现路径**(`REVIEW_FINDINGS.md` C8):
  `entry_points(group="nanobot.tools")` 能查到
  `EntryPoint(name='document_chunker', value='doc_chunker.nanobot_tool:DocumentChunkerTool', ...)`。
  没有进一步写"真正起一个 nanobot `ToolLoader`/`ToolRegistry` 并断言注册成功"的集成测试——
  这需要给测试引入对 `nanobot` 包本身的依赖,取舍在于是否要让 `doc-chunker` 的 CI 依赖一个
  未发布到 PyPI 的兄弟项目;当前选择不引入,留作后续如果要做才做的一步,已在
  `docs/process/UPGRADE_SUMMARY.md` 里如实记录这个边界。

**状态**: 已确认。

---

## D009: 拿到完整原始需求原文(核心能力六条 + 交付物清单五条)后,砍掉四项 D008
未能对照验证的功能

**日期**: 2026-07-07
**背景**: D008 记录 D001–D007 时,一些取舍(尤其是 `FixedSizeChunker`、entry_points 验证、
存储抽象要不要第二后端)是照着 `REVIEW_FINDINGS.md`/`TODO.md` 这两份*派生*文档做的,而不是
直接对照原始需求原文——这两份文档本身是另一轮会话对原始需求的转述和展开,不等于原文。拿到
使用者直接贴出的原文后,逐条核对发现原文只有六条"核心能力要求"("文档解析"、"上下文感知的
分块策略"、"分块质量"、"存储抽象"、"导出接口"、"与基座及上下游的关系")和五条"交付物清单"
("可运行代码"、"设计文档"、"测试流程"、"如果再给一周会补什么"、"测试结果或demo")——都不包含
`REVIEW_FINDINGS.md` C4 引用的"CLI 子命令集(至少 ingest/query/export)"这句话,也不包含任何
"要做对照评测""要有 Skill""要做变更检测""要做完整性校验"的字面要求。

**决策**:砍掉以下四项,因为在原文六条 + 五条交付物里找不到直接对应,且都是"能加分但不是
必需项"的自选动作,不是"漏了会直接丢分"的缺口:

1. **`FixedSizeChunker` 和整个 `ChunkerStrategy` 可插拔架子**——原文第 2 条是"设计一种或
   多种分块策略",一种就够;`ChunkerStrategy` Protocol 只有一个真实实现时,是为可插拔性
   本身付复杂度,而可插拔性不是原文要求的东西。`chunker.py` 退回成一个直接的 `chunk_blocks()`
   函数,边界规则、中文分句修复、小数点保护这些**正确性修复**保留——它们服务的是原文第 2/3
   条("保留上下文关系"、"不把一句话拦腰截断"),和"要不要做策略模式"是两回事。
2. **`scripts/mini_eval.py`(对照评测脚本)**——原文交付物清单里"测试结果或demo"要求的是
   "展示关键路径正确、核心链路跑通",pytest 套件 + `TESTING.md` 里的手动 demo 命令已经覆盖;
   一份专门的对照评测(naive vs 边界感知)不在这条要求里,且它的存在前提(`FixedSizeChunker`)
   已经被砍。
3. **`skills/document-chunker/SKILL.md`**——原文第 6 条明确写的是"它可以是...nanobot 的
   Tool 或 Skill,也可以混合",这是给的一组*可选实现方式*,不是"Tool 和 Skill 都要做"。
   已经用独立包 + CLI + Tool(entry_points)满足这条,再加一份 Skill 属于锦上添花,不是必需项。
4. **`validate_export()` + `schema_version` + content-hash 跳过未变化导入**——三者都不在
   原文任何一条里。`validate_export()` 是防御性的完整性校验,`schema_version` 是导出契约加固,
   content-hash 跳过是增量更新优化——都是"存储抽象"和"导出接口"两条要求之外的自选加固,砍掉
   之后这两条要求本身(`ChunkStore` 抽象、返回标准结构的 chunk 列表)不受影响。

**继续保留、不受这轮影响的**(逐条核对后确认直接对应原文):

- `ChunkStore` 抽象 + `DocumentStore` 一个后端(对应第 4 条,`D008` 已确认)。
- `get_neighbors`/`get_section`/`search(expand=...)`(对应第 2 条明确点名的"父子、相邻、
  章节层级"关系)。
- 分块边界规则、中文分句修复、小数点保护(对应第 2/3 条)。
- PDF outline 标题提取(对应第 1 条"基础元数据...标题")。
- CLI `export` 子命令、`get_by_document`/`search()` 返回标准 chunk 结构(对应第 5 条
  "导出接口...返回 chunk 列表的标准结构")——`export` 本身不是原文点名的 CLI 命令名,但它是
  第 5 条要求的一种自然实现方式,保留;`scripts/demo_retriever.py` 作为"下游确实能消费"的
  可执行证明也保留,因为它服务的正是第 5/6 条,不属于本轮要砍的"自选加固"。
- `pip install -e .` 验证 entry_points——不是交付物,是验证第 6 条"调用路径"的一次性检查
  动作,保留验证过的事实记录(见 `TESTING.md`),但不算作代码交付物。

**为什么不回改 D008**:D008 里"`FixedSizeChunker` 作为唯一的第二策略"那条陈述在写下时是
准确的(描述当时的实现),现在过时,但按本文件开头的约定"不回填修改历史决策",不去改
D008 原文,这条 D009 是取代它的新记录。

**状态**: 已确认。
