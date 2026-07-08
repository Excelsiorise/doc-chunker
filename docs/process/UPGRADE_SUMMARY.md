# 升级总结（UPGRADE_SUMMARY.md）

本文件记录这轮升级改了什么、为什么改、还有什么未完成。升级先由 `docs/process/REVIEW_FINDINGS.md`（一次从零开始、实际跑代码并发现真实 bug 的代码评审）和 `docs/process/TODO.md`（由该评审派生的优先级改进计划）驱动；随后，在拿到**真正的原始作业文本**后，又按原文做了一轮范围裁剪（六条核心能力要求 + 五条交付物清单；完整文本和逐项映射见 `DECISIONS.md` D009）。如果想看*推理过程*，请先读那些文档；本文件只是记录实际做了什么，以及同样重要的：哪些东西做过又撤回了。

当前 31 个自动化测试通过（`python -m pytest tests -q`，升级前是 9 个；见 `TESTING.md`）。

## 0. 本轮修订历史

这次升级经历了三轮，每一轮都把范围重新收窄到原始题目真正要求的内容：

1. **第 1 轮**：基本实现了 `REVIEW_FINDINGS.md` 和 `TODO.md` 里的全部内容：带两个后端的存储抽象、可插拔分块策略、上下文恢复（`expand`）、导出契约加固（`validate_export`、`schema_version`）、content-hash 变更检测、nanobot Skill、对照 mini evaluation 脚本、PDF outline 标题等。
2. **第 2 轮**：讨论后移除了第二个存储后端（`InMemoryChunkStore`）：原始需求是“至少一个内存**或**本地文件后端”，不是两个都要；第二个后端主要是在展示抽象可替换，而不是必需功能。见 `DECISIONS.md` D008。
3. **第 3 轮**：拿到完整原始需求文本后，又移除四类没有直接文字依据的内容：可插拔分块策略架构（`ChunkerStrategy` / `FixedSizeChunker`）、mini 对照评测（`scripts/mini_eval.py`、`docs/process/EVAL.md`）、nanobot Skill（`skills/`），以及导出/存储加固三件套（`validate_export()`、`schema_version`、content-hash skip-if-unchanged）。哪些保留、哪些删除及其原因，见 `DECISIONS.md` D009。

下面的表描述的是三轮之后的**最终状态**，不是第 1 轮较大范围的中间状态。

---

## 1. REVIEW_FINDINGS.md 逐项对应（最终状态）

| ID | 发现 | 状态 | 变化 |
| --- | --- | --- | --- |
| C1 | `ChunkStore`/`DocumentStore` 没有抽象 | **已修复** | `store.ChunkStore` 现在是 `abc.ABC`；`DocumentStore`（JSONL）实现它，`get_by_document`/`get_neighbors`/`get_section`/`search` 在 ABC 上实现一次，未来第二后端可直接复用。当前只有一个后端，见上文第 2 轮和 `DECISIONS.md` D008。 |
| C2 | `get_neighbors(chunk_id)` 和 `get_by_document(doc_id)` 不存在 | **已修复** | 两者都已在 `ChunkStore` 上实现，同时增加 `get_section(chunk_id)`（原始需求没点名这个方法名，但对应的是“命中后扩展上下文”的同一需求，并且直接映射到原文的“父子/章节层级”关系）。 |
| C3 | 没有可插拔分块策略，`chunk_blocks()` 是单个硬编码函数 | **未保留到最终版** | 第 1 轮实现过 `ChunkerStrategy` Protocol + `FixedSizeChunker` baseline，第 3 轮移除：原文要求“一种或多种”分块策略，一个解释充分的策略已满足；只有一个真实实现的 Protocol 被判断为和被移除的第二 store 后端同类的非必要抽象。`chunk_blocks()` 重新变回普通函数。见 `DECISIONS.md` D009。 |
| C4 | CLI 没有 `export` 子命令 | **已修复** | `doc-chunker export <store_dir> --doc-id <id> --out <file> [--format jsonl\|json]`。注意：原文“导出接口”要求的是 chunk 能以标准结构被消费（由 `get_by_document`/`search` 返回 chunk dict 满足）；CLI verb 是这之上的便利实现，不是原文直接列出的命令清单。之所以保留，是因为它自然且低成本地实现了要求。 |
| C5 | 没有声明 `[project.optional-dependencies]` extras | **已修复** | 添加 `nanobot = ["nanobot"]`（记录意图；nanobot 不在 PyPI，README 已说明）和 `test = ["pytest>=8.0.0"]`。 |
| C6 | 中文分句实际没有生效（正则要求标点后有空格，而中文文本没有），导致可复现的句中截断 | **已修复** | `_SENTENCE_BOUNDARY` 正则不再要求后随空白。回归测试：`test_chunk_blocks_never_splits_mid_sentence`。 |
| C7 | 跨标题合并 block 时只保留第一个 block 的 `heading_path`，会把第二个 block 的内容贴错标签，直接破坏“上下文感知、避免误引用”的核心前提 | **已修复** | `chunk_blocks()` 现在在下一个 block 的 `heading_path` 或 `block_type` 与当前 buffer 不同时强制 flush。这种 flush 不带 overlap（把旧章节文本带进新章节 chunk 只会把同一个 bug 挪地方）。回归测试：`test_chunk_blocks_does_not_cross_heading_boundary`、`test_chunk_blocks_does_not_cross_block_type_boundary`。 |
| C8 | `nanobot.tools` entry_points 发现路径从未真正跑过；之前所有“验证”都是直接实例化 `DocumentChunkerTool()` | **已人工验证一次** | 在本环境运行 `pip install -e .`，随后 `entry_points(group="nanobot.tools")` 能解析到 `EntryPoint(name='document_chunker', value='doc_chunker.nanobot_tool:DocumentChunkerTool', ...)`，之后又卸载该包（见 §5）。这是一次性检查，不是交付物；原文没有要求这项验证，因此没有围绕它建立永久测试或脚本。 |
| H1 | PDF 测试依赖未声明的 `PyMuPDF`（`fitz`）；`importorskip` 导致 clean install 中真正基于 `pypdf` 的路径没被测试 | **已修复** | 新增 `tests/pdf_fixtures.py`，手工构造最小 PDF bytes（除了已需要的 `pypdf` 之外不增加依赖）；PDF 测试现在总是真实执行 `parse_pdf()`。 |
| H2 | 构建 chunk 的 `metadata` 时丢弃 parser 层结构化 metadata（例如 XLSX 列头） | **已修复** | `_append_chunk` 现在将第一个 block 的 `metadata` 合并进 chunk metadata，而不是覆盖。回归测试：`test_chunk_metadata_merges_first_block_metadata`。 |
| M1 | `DECISIONS.md` D003–D007 的字段/ID 方案与 `models.py` 不一致，而且此前绕开了这个落差而不是记录它 | **已修复** | `DECISIONS.md` D008/D009 明确声明 `models.py` 是当前事实来源，并记录本轮决策，包括后来被撤回的决策。 |
| M2 | `max_chars` 是软限制（可能达到 `max_chars + overlap_chars`），但文档没说明 | **已记录，未改行为** | 在 `DESIGN.md` 已知限制中显式说明，而不是只让它静默存在于测试断言里。 |
| M3 | `manifest.json` 在顶层把最后写入文档的字段和聚合 `chunk_count` 摆在一起，多文档 store 中两者可能描述不同文档 | **已修复** | Manifest 顶层现在只保留 `chunk_count` / `documents[]`；不再重复每个文档自己的字段。 |
| M4 | `.txt`/`.md`/`.csv` 支持没有作为范围决策记录 | **已记录** | 在 `DESIGN.md` 已知限制中明确说明（包括这些格式不会填充 `heading_path`，这会影响 `expand="section"`）。 |
| M5 | `AI_WORKFLOW.md` session 编号/空档问题 | **未处理** | 超出范围；这是过程日志清理，不是代码或行为变化。 |

## 2. 代码库现在实际包含什么

下面逐项对应六条核心能力要求（原文见 `DECISIONS.md` D009）：

1. **文档解析**：`parsers.py` 支持 PDF/DOCX/XLSX（外加 TXT/MD/CSV 作为低成本补充），抽取文本、page/paragraph/row locator 和标题（DOCX 样式、PDF outline/bookmark）。
2. **上下文感知的分块策略**：`chunk_blocks()` 保留相邻关系（`prev_chunk_id`/`next_chunk_id` + `get_neighbors`）、章节层级/父子关系（`heading_path` + `get_section` 动态聚合）和表格上下文（通过 block_type 边界规则，表格行永远不和周围正文合并）；取舍写在 `DESIGN.md`。
3. **分块质量**：句子边界切分（英文 + 无空格中文标点）、小数保护、可配置 `max_chars`/`overlap_chars`。
4. **存储抽象**：`ChunkStore` ABC + 一个 `DocumentStore`（JSONL）后端，以及参数化契约测试。
5. **导出接口**：`get_by_document()`/`search()` 返回标准 dict 形式的 chunk；`export` CLI 子命令和 `scripts/demo_retriever.py` 展示下游消费者可以直接读取 `chunks.jsonl`，无需 import `doc_chunker`。
6. **与基座及上下游的关系**：独立 Python 包 + CLI + nanobot Tool（`nanobot_tool.py`，通过 entry_points 注册），边界和 I/O 契约写在 `DESIGN.md`。

## 3. 当前端到端使用方式

```bash
# ingest（边界规则、中文分句、小数保护都会自动生效，无需额外配置）
python -m doc_chunker.cli ingest report.pdf --out .doc_index

# 带上下文恢复的 search
python -m doc_chunker.cli search .doc_index "renewal terms" --expand section

# 导出某个文档给下游消费者，然后用零 doc_chunker import 的方式读取
python -m doc_chunker.cli export .doc_index --doc-id <id> --out chunks.jsonl
python scripts/demo_retriever.py .doc_index "renewal terms" --expand section
```

## 4. 涉及文件（最终状态）

- `src/doc_chunker/chunker.py`：边界规则、中文/小数切分修复、metadata 合并。保留普通 `chunk_blocks()` 函数（无策略模式）。
- `src/doc_chunker/store.py`：`ChunkStore` ABC、`get_by_document`/`get_neighbors`/`get_section`/`get_document_info`、`search(expand=...)`、manifest 形状修复。
- `src/doc_chunker/pipeline.py`：overlap clamp warning 记录进 manifest，而不是静默应用。
- `src/doc_chunker/cli.py`：`export` 子命令、`--expand`。
- `src/doc_chunker/nanobot_tool.py`：`expand` 参数。
- `src/doc_chunker/parsers.py`：PDF outline/bookmark 标题抽取。
- `pyproject.toml`：`[project.optional-dependencies]`。
- `tests/`：新增 `pdf_fixtures.py`、`test_store_contract.py`，并重写 `test_chunker.py`、`test_parsers.py`、`test_cli_and_tool.py` 的相关部分。
- `scripts/demo_retriever.py`：新增；独立下游消费者 demo。
- `DECISIONS.md`、`DESIGN.md`、`README.md`、`TESTING.md`：更新为反映以上全部内容。

**第 1 轮曾经做过、后来移除**（只在 `DECISIONS.md` D008/D009 中保留历史记录，不存在于当前树）：`chunker.ChunkerStrategy`/`FixedSizeChunker`、`store.InMemoryChunkStore`、`store.ChunkStore.validate_export()`、`store` manifest `schema_version`、`pipeline` content-hash skip-if-unchanged、`skills/document-chunker/SKILL.md`、`scripts/mini_eval.py`、`docs/process/EVAL.md`。

## 5. 一个值得知道的副作用

验证 C8 需要一次 editable install：`python -m pip install -e .`，使用的是本机 active `python`（`D:\JZ\anaconda3`，Anaconda base 环境；当时没有启用项目本地 virtualenv）。确认 `entry_points(group="nanobot.tools")` 能正确解析后（见上文 C8），又执行 `python -m pip uninstall -y doc-chunker` 卸载，避免在该环境留下持久变化。如果想重新检查，或实际在该环境中使用 `doc-chunker` console script，可以自行再运行 `pip install -e .`。

## 6. 诚实记录的缺口

- 没有清理 `AI_WORKFLOW.md` 的 session 编号（M5）；这是过程日志问题，不是代码问题，超出代码升级范围。
- 没有针对真实运行中的 nanobot `ToolLoader` 做集成测试；只验证过一次 `entry_points()` 能解析，没有验证完整 discover-and-register 路径，也没有把它做成自动化测试。
- `get_section`/`expand="section"` 每次调用是 O(n)（全 store 扫描）；当前规模下没问题，如果未来后端需要处理大得多的 store，这是 `DESIGN.md` 里标注的第一个优化目标。
- 没有对 `prev_chunk_id`/`next_chunk_id` 链接做 referential-integrity 检查（第 1 轮做过的 `validate_export()` 在第 3 轮因不属于原始要求被移除）；如果链条损坏，当前 `get_neighbors` 会静默少返回上下文，而不是抛错。
- 重新导入同一文档总是完整重新解析和重新分块；没有变更检测（第 1 轮做过的 content-hash skip 也在第 3 轮移除）。
