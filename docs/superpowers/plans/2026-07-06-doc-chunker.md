# 文档分块器实施计划

> **给 agentic workers 的说明：** 必需子技能：使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**目标：** 为 take-home assignment 构建一个可运行的模块，包含文档解析、上下文感知分块、本地存储、CLI 和 nanobot Tool 适配层。

**架构：** 保持核心 `doc_chunker` 包独立于 nanobot。将文件解析成规范化 `DocumentBlock` 记录，把这些记录切成带链接的 `Chunk` 记录，以 JSONL + manifest 持久化，然后通过 CLI 和一个薄 nanobot Tool 插件暴露同一套 ingest/search 行为。

**技术栈：** Python 3.11+、pytest、stdlib zip/xml/csv/json/pathlib、可选 `pypdf`（PDF）和 `openpyxl`（Excel），以及用于适配层测试的 nanobot Tool ABC。

---

### 任务 1：核心数据模型与 chunker

**文件：**
- 创建：`doc-chunker/src/doc_chunker/models.py`
- 创建：`doc-chunker/src/doc_chunker/chunker.py`
- 测试：`doc-chunker/tests/test_chunker.py`

- [ ] 为 chunk size 限制、heading metadata、prev/next 链接编写测试。
- [ ] 运行测试，并确认它们因为包还不存在而失败。
- [ ] 实现 dataclass 和带可配置 `max_chars`、`overlap_chars` 的分块逻辑。
- [ ] 运行测试，并确认它们通过。

### 任务 2：解析器

**文件：**
- 创建：`doc-chunker/src/doc_chunker/parsers.py`
- 测试：`doc-chunker/tests/test_parsers.py`

- [ ] 尽可能使用生成的 DOCX/XLSX/PDF fixture 编写测试。
- [ ] 运行 parser 测试，并确认它们在实现前失败。
- [ ] 实现 plain text、DOCX、XLSX 和 PDF parser，返回 `DocumentBlock` 记录。
- [ ] 运行 parser 测试，并确认它们通过。

### 任务 3：存储与搜索

**文件：**
- 创建：`doc-chunker/src/doc_chunker/store.py`
- 测试：`doc-chunker/tests/test_store.py`

- [ ] 为 JSONL round trip、manifest 内容和简单关键词 search 编写测试。
- [ ] 运行 store 测试，并确认它们在实现前失败。
- [ ] 使用 `manifest.json` 和 `chunks.jsonl` 实现 `DocumentStore`。
- [ ] 运行 store 测试，并确认它们通过。

### 任务 4：CLI 与 nanobot Tool 适配层

**文件：**
- 创建：`doc-chunker/src/doc_chunker/cli.py`
- 创建：`doc-chunker/src/doc_chunker/nanobot_tool.py`
- 创建：`doc-chunker/pyproject.toml`
- 测试：`doc-chunker/tests/test_cli_and_tool.py`

- [ ] 为 CLI ingest/search 和 nanobot tool schema/execution contract 编写测试。
- [ ] 运行测试，并确认它们在实现前失败。
- [ ] 实现 CLI 子命令和 `DocumentChunkerTool`。
- [ ] 运行测试，并确认它们通过。

### 任务 5：文档与验证

**文件：**
- 创建：`doc-chunker/README.md`
- 创建：`doc-chunker/DESIGN.md`
- 创建：`doc-chunker/TESTING.md`
- 修改：`doc-chunker/AI_WORKFLOW.md`

- [ ] 记录 quickstart、架构、决策、测试和已知限制。
- [ ] 运行 `pytest`。
- [ ] 运行 `python -m doc_chunker.cli --help`。
- [ ] 运行一个小型 ingest/search demo。
- [ ] 在 `TESTING.md` 和 `AI_WORKFLOW.md` 中记录验证证据。
