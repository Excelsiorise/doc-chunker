# 面试讲稿

这份讲稿用于 3-5 分钟介绍 `doc-chunker`。建议面试时不要逐字朗读,而是按四段讲:问题理解、设计取舍、实现闭环、验证方法。

---

## 3-5 分钟主讲稿

大家好,我这次选择的是"上下文感知的文档导入与分块模块"这个题目。

我对题目的理解是:它不是要求我做一个完整 RAG 系统,而是要求我证明三件事。第一,我能把 PDF、Word、Excel 这类本地文档解析成结构化文本。第二,我能设计一种分块策略,让 chunk 不只是孤立文本片段,而是保留章节、页码、表格行、前后相邻关系这些上下文。第三,我能讲清楚这个模块怎么和 nanobot 协作,以及怎么验证 AI 生成的代码确实按预期工作。

所以我第一步没有直接写代码,而是先读 nanobot 源码。我重点看了 Tool、Skill、entry_points 插件发现、MCP 这几条路径。最后我选的是"独立 Python 包 + nanobot Tool adapter"。原因是这个方案对 nanobot 侵入最小,核心 chunker 可以独立测试,同时又能通过 `nanobot.tools` entry_points 真的接入 nanobot。Skill 更适合写提示词,不适合承载解析和分块逻辑;MCP 复用性很好,但第一版要维护独立进程和协议层,对 48 小时 take-home 来说成本偏高。

实现上我把模块拆成五层。`parsers.py` 负责把不同格式统一解析成 `DocumentBlock`;`chunker.py` 把 block 变成 `Chunk`;`store.py` 把结果写到 `manifest.json` 和 `chunks.jsonl`;`cli.py` 提供本地 demo;`nanobot_tool.py` 是很薄的一层 adapter,只负责参数 schema、ingest/search 分发和错误返回。核心解析、分块、存储都不依赖 nanobot,这样我可以不启动完整 agent 就验证大部分逻辑。

分块策略上,我没有简单按固定字符数硬切。每个 chunk 都保留 `source_file`、`locator`、`heading_path`、`prev_chunk_id`、`next_chunk_id` 和 `metadata`。例如 PDF 会保留页码,也会尝试读取 PDF 自带的 outline/bookmark 补上标题路径;Excel 会保留 sheet、row 和表头;Word 会保留常见 heading 路径。长文本超过 `max_chars` 时优先按句子边界切(中文全角标点不要求后面有空格,小数点会被保护不被当成句号),并加可配置 overlap,避免把一句话从中间截断。更重要的一条边界规则是:合并 block 时一旦 `heading_path` 或 `block_type` 变化就强制切块,不会把两个章节的内容混进同一个 chunk——这是我在自己复盘代码时抓到的一个真实 bug,早期实现只会保留第一个 block 的标题,导致后半段内容被误标成前一个章节的。

检索这块是这一轮修的重点:光存 `prev_chunk_id`/`next_chunk_id`/`heading_path` 没用,得真的有查询方法把它们用起来。所以我在 `search()` 上加了 `expand` 参数:`expand="neighbors"` 沿着前后链接把命中 chunk 两边的邻居一起带回来,`expand="section"` 按 `heading_path` 动态聚合出整节内容返回——不是物理存一份父块,是查询时现算,这样不用维护两份数据。这条能力直接对应题目里"保留父子、相邻、章节层级关系"的要求。

存储我选了 JSONL 加 manifest,没有上 SQLite 或向量数据库。这个选择是有意收敛:JSONL 很容易人工检查、diff 和测试;manifest 记录文档 ID、源文件、parser、chunk 数量、分块参数。存储层本身抽成了 `ChunkStore` 接口,`DocumentStore`(JSONL)是唯一实现——题目要求"至少一个内存或本地文件后端",一个就够,所以我没有再加第二个后端去证明"这个接口真的可替换",那样属于没有对应验收点的自选加固。题目也明确说不要求真实向量数据库或 embedding 训练,所以 search 做确定性关键词匹配。CLI 新增了 `export` 子命令,配一个完全不 import 本包、只读 `chunks.jsonl` 的独立脚本 `demo_retriever.py`,用来证明导出格式是一份真实的、下游可以独立消费的契约,不是内部实现细节。

验证方面,我没有只做手动 demo。测试覆盖了 parser、chunker(含边界规则、中文分句、小数点保护这些不变量)、store 的契约测试、CLI 和 Tool 的执行合约,一共 `31 passed`。我也跑了 CLI demo:ingest 一个样例文档、search 命中、加 `--expand section` 看到上下文被恢复、export 导出、再用 `demo_retriever.py` 独立读出来验证格式没问题。

使用 AI 的方式上,我把它当作加速器,但没有直接相信它。比如 entry_points 插件发现这件事,我实际跑了 `pip install -e .` 加 `entry_points()` 查询去验证,而不是只在测试里直接 `DocumentChunkerTool()` 实例化。更关键的一次自我修正是:我先按一份内部评审文档几乎把能想到的加固都做了一遍(第二个存储后端、可插拔分块策略、完整性校验、变更检测、nanobot Skill、对照评测脚本),后来重新对照题目的完整原文逐条核对,发现这几项都找不到直接依据,属于扩展出来的东西,于是又都删掉了,只留下真正对应要求的部分。这个过程记录在 `DECISIONS.md` D008/D009 里——我认为这比"功能堆得多"更能说明问题:知道什么时候该停,也是验证能力的一部分。

如果给我一周,我会沿着现在的边界继续扩展,而不是推翻重做。优先级是:第一,加 SQLite 后端;第二,在现有关键词匹配基础上加 BM25 排序,还不引入 embedding 依赖;第三,改进表格解析,处理多行表头、合并单元格和 Word 表格;第四,把 entry_points 验证从"手动跑一次"升级成真正起一个 nanobot `ToolLoader` 的集成测试;第五,把这一轮删掉又觉得有价值的两个小东西(prev/next 链接完整性校验、变更检测跳过未改动文档)重新加回来,它们足够独立,不需要一周那么多时间。更长期(不止一周)的话,会往语义检索、Docling 这类版式感知解析、真正的增量更新、以及按需要再加 MCP adapter 这几个方向走,但这些都会明显改变模块的依赖和复杂度,所以留在"以后需要再做"的清单里,不在第一版硬塞。

总结一下,这个版本不是功能最多的方案,但它是一个自洽的小闭环:解析三类主要文档,保留上下文分块并能在检索命中后恢复上下文,本地可检查存储,CLI 可 demo,nanobot 有 Tool 接口,并且有自动化测试、AI 协作记录、以及一次"删掉自己多做的东西"的取舍记录,证明它不是"看起来能跑"或者"看起来功能很全"。

---

## 60 秒极简版

我做的是一个上下文感知文档导入和分块模块。核心目标不是完整 RAG,而是把 PDF、Word、Excel 解析成结构化 block,再生成带来源和上下文信息的 chunk,并且能在检索命中后把上下文恢复回来。

架构上我选了独立 Python 包加 nanobot Tool adapter。这样对 nanobot 零侵入,核心逻辑可独立测试,同时通过 `nanobot.tools` entry_points 保留真实集成路径,而且我实际跑过 `pip install -e .` 验证过这条路径。Skill 不适合承载代码逻辑,MCP 第一版成本偏高。

实现拆成 parser、chunker、store(`ChunkStore` 抽象 + JSONL 实现)、CLI、nanobot_tool 五层。chunk 里保留 `locator`、`heading_path`、`prev_chunk_id`、`next_chunk_id` 等字段,搜索侧的 `expand=neighbors`/`expand=section` 真正把这些字段用起来,命中后能恢复邻居或整节上下文,不再是存了没用。存储用 `manifest.json + chunks.jsonl`,方便人工检查和测试,CLI 有 `export` 子命令,配一个不依赖本包的独立消费脚本证明格式可移植。

验证上我写了 parser、chunker、store 契约测试、CLI 和 Tool 测试,一共 `31 passed`。我也记录了一次自我修正:先几乎实现了所有能想到的加固,再对照完整题目原文逐条核对,把找不到依据的部分(第二存储后端、可插拔策略、完整性校验、变更检测、Skill、评测脚本)又删掉了。

如果继续做,一周内会加 SQLite 后端和 BM25 排序、增强表格解析、把 entry_points 验证做成自动化集成测试;更长期会往语义检索和版式感知解析走。

---

## 演示顺序

面试时建议只演示 2-3 分钟,不要把时间花在等命令上。

1. 打开 [DESIGN.md](./DESIGN.md),讲五层架构。
2. 打开 [src/doc_chunker/models.py](./src/doc_chunker/models.py),指出 `DocumentBlock` 和 `Chunk` 的字段。
3. 打开 [src/doc_chunker/nanobot_tool.py](./src/doc_chunker/nanobot_tool.py),指出 `name = document_chunker`、参数 schema、`ingest/search`。
4. 运行测试:

```powershell
New-Item -ItemType Directory -Force -Path .tmp | Out-Null
$env:PYTHONPATH="src"
$env:TMP=(Resolve-Path .tmp).Path
$env:TEMP=(Resolve-Path .tmp).Path
python -m pytest tests -q
```

5. 运行 CLI demo(用 `samples/Document Chunker Validation Sample.pdf`——一个真的带书签的 3 页 PDF,专门为验证这个 pipeline 设计的,能让 `heading_path` 和 `expand` 的效果看得见,比 `.txt` 样例有说服力):

```powershell
$env:PYTHONPATH="src"
python -m doc_chunker.cli ingest "samples\Document Chunker Validation Sample.pdf" --out .doc_index --max-chars 500
python -m doc_chunker.cli search .doc_index "retention policy"
python -m doc_chunker.cli search .doc_index "retention policy" --expand section
```

6. 对比"加 `--expand section` 前后"两次输出:不加时只返回命中的那一个 chunk;加了以后能看到 `metadata.pdf_headings = "outline"` 和 `heading_path = ["Retention Policy"]` 是从 PDF 书签读出来的,而 `context` 会把"Retention Policy"这一节的全部 5 个 chunk 都聚合回来——正好可以讲"expand=section 不是瞎猜上下文,是按真实的书签结构聚合"。
7. 可选:跑 `python -m doc_chunker.cli search .doc_index "document chunker validation" --expand neighbors`,展示命中第 1 页 chunk 后,`context` 里带出了它的前后邻居。
8. 可选:跑 `python scripts\demo_retriever.py .doc_index "retention policy" --expand section`,证明这套输出不需要 import 这个包也能被读懂。
9. **如果被追问细节,主动提一句已知限制**:这份 PDF 第 2 页其实有三个小节(Retention Policy / Access Control / Table Context Example),但当前实现每页只生成一个 block,所以整页 chunk 的 `heading_path` 都只会是页面上第一个小节的标题——搜 "access control" 会看到 `heading_path=["Retention Policy"]` 而不是 `["Access Control"]`。这是 `DESIGN.md` 已知限制里写明的,不要等面试官现场发现,主动讲出来更加分:"我知道要做页内按标题切分需要按 PDF 坐标信息切割文本,评估后判断这一版不值得投入,留在后续需要时再做"。

---

## 高频追问备答

### 1. 为什么不用向量数据库?

题目明确说不要求真实向量库,内存或 SQLite 后端即可。我的目标是证明文档解析、上下文分块、持久化和 nanobot 集成这条主链路。向量库会把重点转移到 embedding、索引部署和召回调参上,反而不利于把核心模块讲清楚。这个方向留在 `DESIGN.md` 的"更长期规划"里,不是没考虑过。

### 2. 为什么不用 MCP?

MCP 的优点是语言无关、跨 client 复用,但它需要额外维护 server 进程、transport、JSON-RPC 协议和配置。当前题目更看重模块设计和分块质量,所以我先做同进程 Tool adapter。核心库已经独立,未来要加 MCP 时只是再包一层 adapter。

### 3. 为什么不用 nanobot 内嵌 Tool?

内嵌 Tool 会直接改 nanobot 源码,侵入性高,升级时也容易冲突。独立包加 entry_points 是 nanobot 代码里已经预留的第三方工具扩展方式,能做到 nanobot 零代码改动,而且我实际用 `pip install -e .` 验证过这条发现路径是通的,不是只在测试里 `new` 了一下 Tool 类。

### 4. 你的 chunk 为什么算"上下文感知"?

因为它不只是保存文本,而且保存的关系真的被用起来了。每个 chunk 都保存来源文件、位置 locator、heading path、前后相邻 chunk、block 类型等信息。对 PDF 来说 locator 是页码,标题路径会尝试从 PDF 自带的 outline/bookmark 读;对 Excel 来说是 sheet 和 row,还保留表头;对 Word 来说能保留 heading 路径。命中搜索后,`expand="neighbors"` 能沿 `prev`/`next` 把邻居带回来,`expand="section"` 能按 `heading_path` 把整节内容聚合回来——这是我认为整个项目里最能体现"上下文感知"这四个字的部分,因为它不是存了字段就完事,是真的有查询路径把字段用起来。

### 5. JSONL 会不会太简陋?没有第二个存储后端吗?

JSONL 是有意选的,因为它可读、可 diff、容易写测试。存储层抽成了 `ChunkStore` 接口,`DocumentStore`(JSONL)是当前唯一实现。题目要求是"至少一个内存或本地文件后端",不要求两个都做,所以我没有再额外加一个内存后端——那样做只能证明"接口可以被换掉",但这不是题目要的东西。如果数据量变大或查询条件变复杂,`ChunkStore` 已经把搜索、上下文恢复这些通用逻辑放在基类,新加一个 SQLite 后端只需要实现三个存储 primitive 方法,上层 parser/chunker/CLI/Tool 不用动。

### 6. AI 在这个项目里到底帮了什么?你怎么防止它"看起来做完了但其实没做对"?

AI 主要帮我做三类事:定向读源码、生成候选设计、写代码和测试。但关键决策没有直接盲信。举两个具体例子:第一,nanobot entry_points 机制我没有只信第一轮读源码的结论,而是实际跑了 `pip install -e .` 加 `entry_points()` 查询去验证。第二,也是更重要的一次:我先按一份内部评审文档几乎实现了所有能想到的加固(第二个存储后端、可插拔分块策略接口、完整性校验、变更检测、nanobot Skill 文件、对照评测脚本),这些东西单独看都"很像"是应该做的事,但后来我把完整的题目原文摊开逐条核对,发现这几项在原文里都找不到直接依据。于是又把它们删掉了,只留下真正对应要求的部分,过程记录在 `DECISIONS.md` D008/D009。我认为这比"生成了很多功能"更能说明我在监督 AI,而不是被 AI 的产出牵着走——它很擅长做加法,但"要不要做"这件事需要我自己对着原始需求判断。

### 7. 目前最大限制是什么?

`DESIGN.md` Known Limits 列得比较完整,挑几个讲:第一,PDF 只处理可抽取文本,扫描件需要 OCR;第二,search 是关键词匹配,不是语义检索;第三,DOCX heading 只覆盖常见英文 heading style,也没有解析 Word 表格;第四,`prev`/`next` 链接目前没有自动完整性校验,链接如果意外损坏会静默丢上下文而不是报错;第五,重复 ingest 同一文档没有变更检测,会整篇重新解析。后两条其实做过又删了(见上一题),不是没想到。

### 8. 如果测试只能说明样例通过,怎么证明设计可靠?

我把测试写在模块边界上,不是测私有实现,而且区分了"自动化能判断的"和"需要人判断的"两类(`TESTING.md` 有一张表)。自动化测试(31 个)能判断的是有明确对错的东西:chunk 字段对不对、边界规则有没有生效、store 读写是否一致。但"这是不是 bug"、"这个功能该不该做"这类问题,测试本身判断不了,需要我自己对照代码和原始需求去读——`REVIEW_FINDINGS.md` 里每条 bug 都是我实际跑代码复现出来的,不是猜的;`DECISIONS.md` D008/D009 里砍掉的四项功能,也是靠对照原文逐条核对判断出来的,不是靠测试。

### 9. 如果同一文档重新导入怎么办?

当前实现用源路径生成稳定 doc_id。重新导入同一路径时,store 会移除旧的同 doc_id chunks,再写入新 chunks,整篇重新解析、重新分块。这是全量替换策略,比增量 diff 简单,也更容易解释和验证——代价是没有变更检测,即使内容完全没变也会重新处理一遍;这是一个有意识的取舍,不是遗漏(`DESIGN.md` Known Limits 里写明了)。

### 10. 你会怎么把它接入真实 nanobot?

安装这个包到 nanobot 同一个 Python 环境后,`pyproject.toml` 里的 `[project.entry-points."nanobot.tools"]` 会暴露 `DocumentChunkerTool`。nanobot 的 ToolLoader 会发现这个 entry point,创建 tool,然后 agent 就能调用 `document_chunker(action="ingest", ...)` 或 `document_chunker(action="search", expand="section", ...)`。我不是只看代码判断这条路径通——实际跑过 `pip install -e .` 之后用 `entry_points(group="nanobot.tools")` 查询确认过。

### 11. 你依赖了哪些假设?如果假设不成立会怎样?

写在 `DESIGN.md` Assumptions 里,挑两个最关键的说:第一,假设是单进程单写者,`DocumentStore` 没做文件锁,如果要支持多个进程同时往同一个 store 写,现在会有竞态,得换成 SQLite 加事务;第二,假设 `heading_path` 是章节的可靠代理,但对没有标题信号的格式(txt/md/csv,或者没有书签的 PDF)`heading_path` 是空的,这时候 `expand="section"` 会退化成"整篇文档"——这是设计上认了的降级行为,不是 bug。

---

## 面试表达提醒

- 先讲"我为什么不做完整 RAG",这会显得你知道题目边界。
- 多说"我验证了什么",少说"我觉得应该可以"。
- 讲 AI 使用时要强调"让 AI 做候选和实现,我用源码核查和测试收口"。
- 被问到没做的功能时,回答"不在范围内,但边界已经给它留好了"。
- **主动讲一次"删掉自己多做的东西"的故事**(见高频追问第 6 条):这比堆功能更能说明你在真正监督 AI 产出,而不是照单全收。面试官问"这个功能哪来的"时,能说清楚"做过、后来对照原文删了、原因是什么",比说"这是加分项"更有说服力。
- 避免陷入 parser 细节太久,题目更看重设计、集成和验证。
- 如果被问 Docling/Unstructured,回答:它们是更成熟的生产级解析路线,但为了小闭环用轻量 parser;未来只替换 `parsers.py`,不推翻 chunker/store/nanobot adapter。
