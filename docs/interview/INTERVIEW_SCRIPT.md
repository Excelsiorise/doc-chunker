# Interview Script

这份讲稿用于 3-5 分钟介绍 `doc-chunker`。建议面试时不要逐字朗读,而是按四段讲:问题理解、设计取舍、实现闭环、验证方法。

---

## 3-5 分钟主讲稿

大家好,我这次选择的是"上下文感知的文档导入与分块模块"这个题目。

我对题目的理解是:它不是要求我做一个完整 RAG 系统,而是要求我证明三件事。第一,我能把 PDF、Word、Excel 这类本地文档解析成结构化文本。第二,我能设计一种分块策略,让 chunk 不只是孤立文本片段,而是保留章节、页码、表格行、前后相邻关系这些上下文。第三,我能讲清楚这个模块怎么和 nanobot 协作,以及怎么验证 AI 生成的代码确实按预期工作。

所以我第一步没有直接写代码,而是先读 nanobot 源码。我重点看了 Tool、Skill、entry_points 插件发现、MCP 这几条路径。最后我选的是"独立 Python 包 + nanobot Tool adapter"。原因是这个方案对 nanobot 侵入最小,核心 chunker 可以独立测试,同时又能通过 `nanobot.tools` entry_points 真的接入 nanobot。Skill 更适合写提示词,不适合承载解析和分块逻辑;MCP 复用性很好,但第一版要维护独立进程和协议层,对 48 小时 take-home 来说成本偏高。

实现上我把模块拆成五层。`parsers.py` 负责把不同格式统一解析成 `DocumentBlock`;`chunker.py` 把 block 变成 `Chunk`;`store.py` 把结果写到 `manifest.json` 和 `chunks.jsonl`;`cli.py` 提供本地 demo;`nanobot_tool.py` 是很薄的一层 adapter,只负责参数 schema、ingest/search 分发和错误返回。核心解析、分块、存储都不依赖 nanobot,这样我可以不启动完整 agent 就验证大部分逻辑。

分块策略上,我没有简单按固定字符数硬切。每个 chunk 都保留 `source_file`、`locator`、`heading_path`、`prev_chunk_id`、`next_chunk_id` 和 `metadata`。例如 PDF 会保留页码,Excel 会保留 sheet、row 和表头,Word 会保留常见 heading 路径。长文本超过 `max_chars` 时优先按句子边界切,并加可配置 overlap,避免把一句话从中间截断。这样下游检索或生成拿到的不只是文本,还能知道它来自哪里、上下文前后是谁。

存储我第一版选了 JSONL 加 manifest,没有上 SQLite 或向量数据库。这个选择是有意收敛:JSONL 很容易人工检查、diff 和测试;manifest 能记录文档 ID、源文件、parser、chunk 数量、分块参数。题目也明确说不要求真实向量数据库或 embedding 训练,所以第一版 search 做确定性关键词匹配,用来证明"导入、分块、存储、检索、nanobot 调用"这条链路跑通。

验证方面,我没有只做手动 demo。测试覆盖了四类边界:parser 测 DOCX heading/paragraph、XLSX sheet row 和 PDF page text;chunker 测 heading metadata、chunk size、overlap 和 prev/next 链接;store 测 JSONL round trip、manifest 和关键词 search;Tool 测 nanobot-facing schema 和 async execute 合约。最后完整验证结果是 `9 passed`。我也跑了 CLI demo:先 ingest `samples/example.txt`,得到 `ok=true` 和 2 个 chunk;再 search `"chunker validation"`,返回的 chunk 里能看到 `prev_chunk_id` 和 `next_chunk_id`。

使用 AI 的方式上,我把它当作加速器,但没有直接相信它。比如 entry_points 插件发现这件事,我让 AI 第一轮读源码后,又单独让它重新核查 `ToolLoader._discover_plugins()` 和注册组名 `nanobot.tools`,两轮结论一致才采用。实现阶段我也记录了 AI 产出的错误:一开始 chunk 配置太保守,小 demo 不好测;CLI 默认 overlap 在小 chunk 场景下会变成非法参数。这个问题是测试跑出来的,不是靠感觉发现的。相应修正也写进了 `AI_WORKFLOW.md`。

如果给我一周,我会沿着现在的边界继续扩展,而不是推翻重做。优先级是:第一,加 SQLite 后端和更强的过滤查询;第二,加 BM25 或 embedding-backed retrieval;第三,改进表格解析,处理多行表头和合并单元格;第四,补一个 nanobot Skill,告诉 agent 什么时候应该调用 `document_chunker`;第五,如果需要跨 agent 复用,再把同一套核心库包一层 MCP server。

总结一下,这个版本不是功能最多的方案,但它是一个自洽的小闭环:解析三类主要文档,保留上下文分块,本地可检查存储,CLI 可 demo,nanobot 有 Tool 接口,并且有自动化测试和 AI 协作记录证明它不是"看起来能跑"。

---

## 60 秒极简版

我做的是一个上下文感知文档导入和分块模块。核心目标不是完整 RAG,而是把 PDF、Word、Excel 解析成结构化 block,再生成带来源和上下文信息的 chunk。

架构上我选了独立 Python 包加 nanobot Tool adapter。这样对 nanobot 零侵入,核心逻辑可独立测试,同时通过 `nanobot.tools` entry_points 保留真实集成路径。Skill 不适合承载代码逻辑,MCP 第一版成本偏高。

实现拆成 parser、chunker、store、CLI、nanobot_tool 五层。chunk 里保留 `locator`、`heading_path`、`prev_chunk_id`、`next_chunk_id` 等字段,避免切完以后丢失章节、页码、表格上下文。存储第一版用 `manifest.json + chunks.jsonl`,方便人工检查和测试。

验证上我写了 parser、chunker、store、CLI 和 Tool contract 测试,最终 `9 passed`。我也记录了 AI 使用过程:先让 AI 定向读 nanobot 源码,再交叉验证 entry_points 机制;实现阶段通过测试发现并修正了参数边界问题。

如果继续做,我会加 SQLite/BM25/embedding 检索、增强表格解析,再视复用需求加 MCP adapter。

---

## Demo 顺序

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

5. 运行 CLI demo:

```powershell
$env:PYTHONPATH="src"
python -m doc_chunker.cli ingest samples\example.txt --out .doc_index --max-chars 160 --overlap-chars 20
python -m doc_chunker.cli search .doc_index "chunker validation"
```

6. 打开 `.doc_index/chunks.jsonl`,展示 `locator`、`prev_chunk_id`、`next_chunk_id`。

---

## 高频追问备答

### 1. 为什么不用向量数据库?

题目明确说不要求真实向量库,内存或 SQLite 后端即可。我的第一版目标是证明文档解析、上下文分块、持久化和 nanobot 集成这条主链路。向量库会把重点转移到 embedding、索引部署和召回调参上,反而不利于 48 小时内把核心模块讲清楚。

### 2. 为什么不用 MCP?

MCP 的优点是语言无关、跨 client 复用,但它需要额外维护 server 进程、transport、JSON-RPC 协议和配置。当前题目更看重模块设计和分块质量,所以我先做同进程 Tool adapter。核心库已经独立,未来要加 MCP 时只是再包一层 adapter。

### 3. 为什么不用 nanobot 内嵌 Tool?

内嵌 Tool 会直接改 nanobot 源码,侵入性高,升级时也容易冲突。独立包加 entry_points 是 nanobot 代码里已经预留的第三方工具扩展方式,能做到 nanobot 零代码改动。

### 4. 你的 chunk 为什么算"上下文感知"?

因为它不只是保存文本。每个 chunk 都保存来源文件、位置 locator、heading path、前后相邻 chunk、block 类型等信息。对 PDF 来说 locator 是页码;对 Excel 来说是 sheet 和 row,还保留表头;对 Word 来说能保留 heading 路径。下游回答时可以知道文本来自哪里,也能沿 prev/next 找回临近上下文。

### 5. JSONL 会不会太简陋?

第一版故意选 JSONL,因为它可读、可 diff、容易写测试,适合 take-home 展示。它不是最终形态。如果数据量变大或查询条件变复杂,我会把 `DocumentStore` 抽象下面再加 SQLite 后端,但上层 parser/chunker/Tool 接口不需要大改。

### 6. AI 在这个项目里到底帮了什么?

AI 主要帮我做三类事:定向读源码、生成候选设计、写第一版代码和测试。但关键决策没有直接盲信 AI。比如 nanobot entry_points 机制我要求它二次核查;实现后用 pytest 和 CLI demo 验证;AI 生成代码里的参数边界问题也是测试暴露后才修正的。我把这些过程记录在 `AI_WORKFLOW.md`。

### 7. 目前最大限制是什么?

最大限制有三个:第一,PDF 只处理可抽取文本,扫描件需要 OCR;第二,search 是关键词匹配,不是语义检索;第三,DOCX heading 只覆盖常见英文 heading style,没有完整处理所有本地化样式和复杂 Word 表格。这些都在 `DESIGN.md` 的 Known Limits 里写明了。

### 8. 如果测试只能说明样例通过,怎么证明设计可靠?

我把测试写在模块边界上,不是测私有实现。parser 测归一化 block 输出;chunker 测上下文字段和链接;store 测落盘再读回;Tool 测 nanobot-facing schema 和 async execute。这些测试对应的是题目要求本身。它不能证明所有真实文档都完美,但能证明核心契约是稳定的。

### 9. 如果同一文档重新导入怎么办?

当前实现用源路径生成稳定 doc_id。重新导入同一路径时,store 会移除旧的同 doc_id chunks,再写入新 chunks。这是第一版的全量替换策略,比增量 diff 简单,也更容易解释和验证。

### 10. 你会怎么把它接入真实 nanobot?

安装这个包到 nanobot 同一个 Python 环境后,`pyproject.toml` 里的 `[project.entry-points."nanobot.tools"]` 会暴露 `DocumentChunkerTool`。nanobot 的 ToolLoader 会发现这个 entry point,创建 tool,然后 agent 就能调用 `document_chunker(action="ingest", ...)` 或 `document_chunker(action="search", ...)`。

---

## 面试表达提醒

- 先讲"我为什么不做完整 RAG",这会显得你知道题目边界。
- 多说"我验证了什么",少说"我觉得应该可以"。
- 讲 AI 使用时要强调"让 AI 做候选和实现,我用源码核查和测试收口"。
- 被问到没做的功能时,回答"不在第一版范围,但边界已经给它留好了"。
- 避免陷入 parser 细节太久,题目更看重设计、集成和验证。
- 如果被问 Docling/Unstructured,回答:它们是更成熟的生产级解析路线,但第一版为了小闭环用轻量 parser;未来只替换 `parsers.py`,不推翻 chunker/store/nanobot adapter。
