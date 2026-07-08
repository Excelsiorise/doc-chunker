# 测试

## 自动化测试

运行：

```bash
python -m pytest tests -q
```

在这个沙箱工作区中，pytest 需要一个位于项目内部、可写的临时目录：

```powershell
New-Item -ItemType Directory -Force -Path .tmp | Out-Null
$env:PYTHONPATH="src"
$env:TMP=(Resolve-Path .tmp).Path
$env:TEMP=(Resolve-Path .tmp).Path
python -m pytest tests -q
```

最近一次验证结果：2026-07-07，在完成由 `REVIEW_FINDINGS.md`/`TODO.md` 驱动的升级，并随后按原始作业文本做范围裁剪之后（完整历史见 `docs/process/UPGRADE_SUMMARY.md`）：

```text
31 passed in 0.63s
```

当前覆盖重点：

- `tests/test_chunker.py`：heading metadata、chunk size 行为、overlap、prev/next 链接，以及本轮新增的不变量：chunk 永远不会跨越 `heading_path`/`block_type` 边界；中文句子可在无空格的全角标点处分句；小数（`3.2`）永远不会在数字中间被切开；parser metadata 会合并进 chunk metadata；空/空白输入不会产出 chunk；同一输入+配置是确定性的。
- `tests/test_parsers.py`：DOCX 标题/段落抽取、带表头 metadata 的 XLSX sheet 行抽取，以及 PDF 页面文本抽取**和** PDF outline/bookmark 标题抽取；这里使用手工构造的最小 PDF fixture（`tests/pdf_fixtures.py`），而不是上一版在 clean install 中会悄悄 skip 的未声明 `PyMuPDF` 依赖（`REVIEW_FINDINGS.md` H1）。
- `tests/test_store.py`：JSONL round trip、manifest 写入，以及 `DocumentStore` 后端上的关键词 search。
- `tests/test_store_contract.py`：`ChunkStore` 基类一次性实现的查询方法（`get_by_document`、`get_neighbors`、`get_section`、带/不带 `expand` 的 `search`、`get_document_info`），通过参数化 `store` fixture 运行（当前一个 case：`"jsonl"`），因此未来第二个后端只需要加一行，而不是新建测试文件（`REVIEW_FINDINGS.md` C1/C2；为什么今天不实现第二后端，见 `DECISIONS.md` D008/D009）。
- `tests/test_cli_and_tool.py`：CLI `ingest`/`search`/`export`、`--expand`，以及 nanobot Tool schema/execution contract，包括 `expand` 参数。

## 真实验证 nanobot entry_points 路径

`REVIEW_FINDINGS.md` C8 指出，之前所有“验证”都是直接实例化 `DocumentChunkerTool()`，这并不会触发 nanobot 实际的插件发现路径（`importlib.metadata.entry_points(group="nanobot.tools")`）。本环境中已直接验证：

```bash
python -m pip install -e .
python -c "from importlib.metadata import entry_points; print(list(entry_points(group='nanobot.tools')))"
# -> [EntryPoint(name='document_chunker', value='doc_chunker.nanobot_tool:DocumentChunkerTool', group='nanobot.tools')]
```

这确认了包元数据正确，并且能端到端 import。它还没有真正启动 nanobot `ToolLoader`/`ToolRegistry` 并断言 `"document_chunker"` 已注册；那会要求测试套件依赖 `nanobot` 包本身，当前刻意没有加入这个依赖（见 `DESIGN.md` 一周扩展计划第 4 项）。这是一次本地人工验证，不是每次自动化测试都会重复检查的内容。

## 手动 Demo 命令

从 `doc-chunker/` 目录运行：

```bash
python -m doc_chunker.cli ingest path\to\document.docx --out .doc_index
python -m doc_chunker.cli search .doc_index "keyword"
```

如果包尚未安装，请设置：

```bash
$env:PYTHONPATH="src"
```

最近一次 demo 命令（使用 `samples/Document Chunker Validation Sample.pdf`，一个 3 页、带真实 outline/bookmarks 的 PDF：第 1 页 "Overview"/"Project Background"/"Chunking Requirements"，第 2 页 "Retention Policy"/"Access Control"/"Table Context Example"，第 3 页 "Search Scenarios"/"Conclusion"；因此 `heading_path` 和 `pdf_headings` 会实际填充，不像 `.txt` 样例）：

```powershell
$env:PYTHONPATH="src"
python -m doc_chunker.cli ingest "samples\Document Chunker Validation Sample.pdf" --out .doc_index --max-chars 500
python -m doc_chunker.cli search .doc_index "retention policy" --expand section
python -m doc_chunker.cli search .doc_index "document chunker validation" --expand neighbors
python -m doc_chunker.cli export .doc_index --doc-id <ingest 输出里的 doc_id> --out chunks_export.jsonl
python scripts\demo_retriever.py .doc_index "retention policy" --expand section
```

观察到的结果（2026-07-08 重新验证，这个 PDF 每页文本超过 `max_chars`，所以每页会被切成多个 chunk）：

```text
ingest 返回 ok=true, chunk_count=12, parser=pdf
第 1 页的 5 个 chunk：heading_path=["Document Chunker Validation Sample"]（outline 里排在最前的书签，
  即文档标题本身；本页另外两个小节标题 "Overview"/"Project Background"/"Chunking Requirements"
  不会单独出现在 heading_path 里——见下面的已知限制）
第 2 页的 5 个 chunk：heading_path=["Retention Policy"]（本页第一个小节标题）
第 3 页的 2 个 chunk：heading_path=["Search Scenarios"]
search "retention policy" --expand section 命中第 2 页前两个 chunk，context 把整页 5 个 chunk
  （chunk 0006-0010）都聚合回来——因为它们 heading_path 都是 "Retention Policy"
```



`.txt` demo（`samples/example.txt`）仍然可以同样用于 `ingest`/`search`/`export`，但它的 `heading_path` 永远为空（纯文本没有 heading signal），因此 `--expand section` 会退化为"返回整个文档"。

## 验证方法论

测试检查的是模块边界处的行为，而不是私有实现细节：

- Parser 测试断言规范化后的 `DocumentBlock` 输出，使用手工构造 fixture，而不是未声明的测试依赖（`tests/pdf_fixtures.py`）。
- Chunker 测试断言外部有用的 chunk metadata 和不变量（不在句中切断、不跨边界合并、确定性），而不是内部 buffer 状态。
- Store contract 测试断言同一行为适用于 `ChunkStore` 的共享基类方法，并且结构上支持未来第二后端复用同一套测试。
- Tool 测试断言面向 nanobot 的 schema 和 async execution 行为。

这对 AI-assisted coding 很重要：如果测试只是复刻实现，它抓不住错误设计。这些测试直接编码作业要求。

### 测试了什么，以及如何判断正确性

| 内容 | 验证方式 | 自动化还是人工？ |
| --- | --- | --- |
| Parser 输出形状（字段、locator、heading） | `tests/test_parsers.py` 基于手工 fixture 断言精确 `DocumentBlock` 值 | 自动化 |
| Chunk 边界正确性（不断句中间、不跨 heading 合并） | `tests/test_chunker.py` 不变量断言，包括一次真实复现的中文分句 bug（`REVIEW_FINDINGS.md` C6）和小数点回归 | 自动化 |
| Store round-trip 和查询行为（`get_neighbors`、`get_section`、`search`） | `tests/test_store_contract.py`、`tests/test_store.py` | 自动化 |
| CLI 和 nanobot Tool contract（参数、JSON 形状、错误处理） | `tests/test_cli_and_tool.py` | 自动化 |
| “nanobot 插件发现路径是否真的可用”（不只是“Tool 类是否满足接口”） | `pip install -e .` + `importlib.metadata.entry_points()` 检查，见上文 | **人工运行，一次性**；不会被 `pytest` 重复检查。这是一个判断取舍：当前不需要变成永久自动化测试（完整自动化版本需要什么，见 `DESIGN.md` 一周扩展计划第 4 项） |
| “测试暴露的问题到底是 bug 还是预期行为”（例如 heading 贴错标签 bug、软 `max_chars` 限制） | 阅读代码路径，用最小例子复现失败，再决定修复还是记录为已知限制 | **人工判断**；`REVIEW_FINDINGS.md` 对每个 finding 都记录了哪些是修复的 bug，哪些是文档化的设计取舍（例如 `max_chars + overlap_chars` 软限制） |
| “这个功能到底是作业要求，还是 scope creep” | 对每个已实现功能重新阅读原始需求文本 | **人工判断**；这产生了 `DECISIONS.md` D008/D009：几个 AI 建议的加法（第二 store 后端、可插拔分块策略接口、完整性检查器、变更检测缓存、nanobot Skill 文件）曾经被实现，随后在对照原文后移除，因为“代码能跑而且功能更多”不等于“代码回答了题目真正要求的问题”。 |
| 端到端 demo（ingest → search → expand → export → independent re-read） | 手动 CLI 运行，见上文“手动 Demo 命令” | **人工运行**；这是“测试结果或 demo”交付物，不封装进 `pytest`，因为它是给人读的，而不是给断言读的 |

自动化测试负责抓那些有可检查正确答案的回归（chunk 字段、store round-trip）；而所有关于“功能是否应该存在”的判断，包括 bug vs. 预期行为、in-scope vs. scope creep，都需要人把原始需求文本和真实代码放在一起读。`REVIEW_FINDINGS.md` 和 `DECISIONS.md` D008/D009 记录的就是这类判断，而不只是测试套件。
