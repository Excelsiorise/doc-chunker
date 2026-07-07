# DECISIONS.md

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
