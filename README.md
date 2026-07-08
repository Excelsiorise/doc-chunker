# doc-chunker

面向 Lenovo AI Coding take-home 的上下文感知文档解析与分块模块。

第一版有意保持范围很小：解析本地文档，将其转换为规范化 block，生成带上下文元数据和前后链接的 chunk，存入本地 JSONL，并同时通过 CLI 和 nanobot Tool 适配层暴露完整流程。

## 文档导航

- `DESIGN.md`：架构、数据流、边界和已知限制。
- `DECISIONS.md`：设计决策和取舍记录。
- `TESTING.md`：自动化测试和手动 demo 命令。
- `docs/study/`：入门指南和学习路径。
- `docs/interview/`：面试讲稿和检查清单。
- `docs/process/`：AI 工作流记录、review 发现、改进 TODO 列表和升级总结（`UPGRADE_SUMMARY.md`）。

## 快速开始

运行测试：

```bash
python -m pytest tests -q
```

导入文档：

```bash
python -m doc_chunker.cli ingest "samples/Document Chunker Validation Sample.pdf" --out .doc_index
```

搜索索引，并可选择恢复每个命中结果周围的上下文：

```bash
python -m doc_chunker.cli search .doc_index "downstream users"
python -m doc_chunker.cli search .doc_index "downstream users" --expand neighbors
python -m doc_chunker.cli search .doc_index "downstream users" --expand section
```

导出某个文档的 chunk，供下游消费者使用：

```bash
python -m doc_chunker.cli export .doc_index --doc-id <doc_id> --out chunks_export.jsonl
```

运行独立的下游消费者 demo（直接读取 `chunks.jsonl`，不 import `doc_chunker`）：

```bash
python scripts/demo_retriever.py .doc_index "keyword" --expand section
```

如果从仓库源码直接运行且尚未安装包，请设置 `PYTHONPATH=src`；运行测试时测试套件已经会注入 `src`。

## 支持的输入

- `.pdf`：通过 `pypdf` 按页抽取文本；如果 PDF 自带 outline/bookmark tree，则从其中读取标题结构（否则退化为无标题结构，并在 chunk metadata 中记录 `pdf_headings: unavailable`）。
- `.docx`：从 Word XML 包中抽取段落和标题样式。
- `.xlsx`：通过 `openpyxl` 按 sheet 抽取行；第一行视为表头。
- `.txt`、`.md`、`.csv`：作为低成本 demo 和测试格式支持（无标题结构）。

## 输出格式

每个 store 目录包含：

- `manifest.json`：聚合的 `chunk_count`，以及每个已导入文档对应的 `documents[]` 条目，包含源路径、解析器、单文档 chunk 数、分块配置和时间戳。
- `chunks.jsonl`：每行一个 chunk JSON 对象。

Chunk 字段包括 `chunk_id`、`doc_id`、`text`、`source_file`、`locator`、`heading_path`、`prev_chunk_id`、`next_chunk_id` 和 `metadata`（其中也保留解析器层面的结构化元数据，例如 XLSX 列头，不只是 chunk 层面的 bookkeeping）。

## 搜索之外的查询能力

`ChunkStore`（`store.py`）暴露：

- `get_by_document(doc_id)`
- `get_neighbors(chunk_id, before=1, after=1)`：沿 `prev_chunk_id`/`next_chunk_id` 查找相邻 chunk。
- `get_section(chunk_id)`：返回与目标 chunk 共享 `heading_path` 的全部 chunk（动态 small-to-big 聚合，不是物理存储的 parent block）。


