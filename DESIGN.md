# 设计

## 目标

构建一个小而可运行的文档导入与分块模块，用来展示上下文感知的 chunk 边界，以及与 nanobot 集成的清晰路径。这个模块不是完整的 RAG 平台。

## 需求对照

按题目原文六条核心能力要求，逐条标注对应实现位置，方便直接定位，细节见下文各章节，这里不重复展开：

1. **文档解析**（PDF/WORD/EXCEL + 基础元数据）→ `parsers.py`，见下文"解析器选择"。
2. **上下文感知的分块策略**（父子、相邻、章节层级、语义段落、表格上下文）→ `chunker.py` 的边界规则（`heading_path`/`block_type` 硬边界、`prev`/`next` 链接）+ `store.py` 的 `get_neighbors`/`get_section`，见"上下文感知分块"。
3. **分块质量**（按段落/句子切分、避免拦腰截断、可配置块大小与重叠）→ `chunker.py` 的句子边界切分与 `ChunkingConfig`，同样在"上下文感知分块"里说明。
4. **存储抽象**（ChunkStore/DocumentStore，至少一个内存或本地文件后端）→ 见"存储抽象"与"存储选择"。
5. **导出接口**（返回标准结构的 chunk 列表，供下游检索模块消费）→ 见"导出接口"。
6. **与基座及上下游的关系**（nanobot Tool/Skill/独立模块，边界与调用路径）→ 见"Nanobot 边界"；选型对比记录在 `DECISIONS.md` D001。

## 架构

实现分为五层：

1. `parsers.py` 读取源文件并返回规范化的 `DocumentBlock` 记录。
2. `chunker.py` 将 block 转换为带链接的 `Chunk` 记录。
3. `store.py` 定义 `ChunkStore` 抽象和一个后端：基于磁盘 JSONL + manifest 的 `DocumentStore`。
4. `cli.py` 暴露 `ingest` / `search` / `export`，用于本地 demo 和验证。
5. `nanobot_tool.py` 将同一套核心行为适配到 nanobot 的 `Tool` 接口。

核心层不依赖 nanobot。这样设计能让模块更容易测试，也允许同一模块在 nanobot 之外复用。

## 数据流

```text
PDF/DOCX/XLSX/CSV/TXT/MD 路径
  -> parse_document()
  -> list[DocumentBlock]
  -> chunk_blocks()
  -> list[Chunk]                          (永远不会跨越 heading_path 或 block_type 变化)
  -> ChunkStore.write_document()
  -> manifest.json + chunks.jsonl
```

搜索是确定性的关键词匹配，并带一个可选的上下文恢复步骤：

```text
query -> ChunkStore.search(query, expand=None|"neighbors"|"section")
      -> expand=None:       匹配 chunk dict 的扁平列表
      -> expand="neighbors": {chunk, context: [prev.., hit, ..next]}   (沿 prev/next_chunk_id 查找)
      -> expand="section":   {chunk, context: [...]}                   (所有共享 heading_path 的 chunk)
```

`get_neighbors` 和 `get_section` 也可以直接在 `ChunkStore` 上通过程序调用（`get_by_document(doc_id)` 也一样），并不只能通过 `search(expand=...)` 间接使用。

## 上下文感知分块

chunker 通过三种方式保留上下文，正好对应作业要求中需要保留的关系（“父子、相邻、章节层级、语义段落、表格上下文”）：

- `heading_path` 记录章节或 sheet 上下文（章节层级），并且是**硬 chunk 边界**：`chunk_blocks()` 永远不会把 `heading_path` 或 `block_type` 不同的两个 block 合并进同一个 chunk。过去，合并两个 block 的 chunk 只保留第一个 block 的 `heading_path`，会悄悄把第二个 block 的内容贴错标签（见 `docs/process/REVIEW_FINDINGS.md` C7）；现在结构上已经不可能发生。相同的边界规则也保证表格行（`block_type="table_row"`）拥有自己的 chunk，不会和周围正文混在一起（表格上下文）。
- `prev_chunk_id` 和 `next_chunk_id` 保留相邻 chunk 关系（相邻），并被 `get_neighbors`/`search(expand="neighbors")` 消费；之前这些字段存在，但没有任何查询会读取它们。
- `get_section` 是一种**动态 small-to-big / parent 聚合**（父子）：读取时把所有共享 `heading_path` 的 chunk 分组，而不是物理存储第二份更大的 “parent” block。这个选择的代价是每次 `expand="section"` 调用都要做一次 O(n) 扫描，换来的是不必维护两套同步的文档副本。完整取舍见 `DECISIONS.md` D008。

当某个 block 大于 `max_chars` 时，splitter 优先在句子边界切分（语义段落：英文 `. ! ?` 和中文全角 `。！？…`，不要求标点后有空格，因为中文文本通常没有），会保护小数点数字（`3.2` 永远不会被切成 `3.` / `2`），并在切分后的 chunk 之间增加可配置 overlap。Overlap 基于字符数，只会应用在同一个超大 block 自身的句子切分内部；它永远不会跨 heading/block_type 边界 flush，因为把旧章节文本带进新章节 chunk 会重新引入边界规则本来要避免的贴错标签问题。

当前只实现一种分块方式（`chunk_blocks()`，感知边界和句子）。作业要求是“一种或多种”策略，因此一个解释充分的策略已经满足要求；本轮较早的草稿曾经加入第二个 `FixedSizeChunker`，只是为了给评测脚本提供对照基线，后来在确认评测本身不是必需项后一起移除（见 `DECISIONS.md` D008/D009）。

## 存储抽象

`store.ChunkStore` 是一个 `abc.ABC`。后端只需要实现三个抽象原语（`write_document`、`load_chunks`、`get_document_info`）；`get_by_document`、`get_neighbors`、`get_section` 和 `search` 都在基类里基于这三个原语实现一次，所以任何后端都能免费获得这四个行为，并且天然保持一致。

当前只有一个后端：`DocumentStore`，使用磁盘上的 JSONL（`chunks.jsonl`）+ `manifest.json`，便于检查、diff 和调试。作业要求是“至少一个内存**或**本地文件后端”，不是两个都要，所以没有额外加入第二个（例如内存）后端；第二个后端只能证明抽象可替换，但这本身不是功能性要求（完整理由见 `DECISIONS.md` D008，包括为什么本轮较早草稿确实加过一个后端、后来又删除）。

`tests/test_store_contract.py` 仍然通过一个参数化的 `store` fixture 测试 `get_by_document`/`get_neighbors`/`get_section`/`search`，目前只有 `"jsonl"` 一个 case；未来添加后端（SQLite、in-memory 等）只需要实现三个原语并在 `_make_store()` 里加一行，不需要新写测试。

SQLite/vector-store 后端没有实现；这里抽象的意义在于“如果再给一周”时可扩展：新后端是一个实现三个方法的新类，而不是重写 `cli.py`/`nanobot_tool.py`。

## 解析器选择

- DOCX 解析直接使用 Word XML 包。这避免了对 `python-docx` 的硬运行时依赖，同时仍然可以抽取标题和段落。
- XLSX 解析使用 `openpyxl`，这是处理 Excel 的实际可用依赖。
- PDF 解析使用 `pypdf`。当 PDF 自带 outline/bookmark tree（`reader.outline`）时，从中读取标题；每页的 `heading_path` 是该页之前最近的 bookmark 标题。这是一个确定、免费的信号（不需要字体大小启发式、不需要 OCR、不需要额外依赖），直接满足必需基础元数据中的“标题”项。没有 outline 的 PDF 会得到 `heading_path=[]`，并且每个 block 的 `metadata["pdf_headings"] = "unavailable"`，让缺口显式暴露，而不是看起来像“这个 PDF 没有章节”。
- 每个 parsed block 的 `metadata` 都会保留到它贡献出的 chunk 中（`chunker._append_chunk` 将 `first_block.metadata` 合并到 chunk metadata，而不是丢弃）；因此 `xlsx` 列头、`docx` 段落样式和 `pdf_headings` 可用性都能在存储后的 `Chunk` 上查询，而不只是埋在 `text` 里。见 `REVIEW_FINDINGS.md` H2。
- 不使用 PyMuPDF/MinerU/Docling/OCR：PyMuPDF 使用 AGPL license（商业环境里的真实顾虑），而 OCR/layout-model 依赖也与“干净环境可运行”相冲突。

## 存储选择

选择 JSONL 加 manifest，而不是 SQLite。JSONL 容易人工检查，容易 diff，也容易用测试验证。Manifest 顶层只保留聚合的 `chunk_count` 和 `documents[]` 列表；它不再在顶层重复最后一次导入文档的字段，避免在多文档 store 中出现顶层字段和聚合计数描述不同文档的隐性坑。非法的 `overlap_chars >= max_chars` 会通过 `UserWarning` 被 clamp，并在每个文档的 `chunking` metadata 中记录为 `overlap_adjusted`/`requested_overlap_chars`，而不是悄悄套用。

## 导出接口

`ChunkStore.get_by_document(doc_id)` 和 `search()` 都返回普通 dict 形式的 chunk（`Chunk.to_dict()`），这是下游检索模块可消费的“标准结构”，也就是作业要求中的导出接口。`doc-chunker export <store> --doc-id <id> --out <file>` 是一个 CLI 便利命令，用于把某个文档的 chunk 写成 JSON/JSONL 文件交给下游。`scripts/demo_retriever.py` 不 import `doc_chunker`，直接读取 `chunks.jsonl`，作为可执行证明：这个格式是真正独立的契约，而不是内部实现细节。

## Nanobot 边界

nanobot 适配层刻意保持很薄。它只负责：

- 工具名称和描述；
- JSON schema 参数（包括 `expand`）；
- `ingest` 和 `search` 分发；
- 将异常转换为 `ToolResult.error(...)`。

所有有意义的解析、分块和存储行为仍然留在独立包中。`pyproject.toml` 声明 `[project.optional-dependencies] nanobot = ["nanobot"]`，用来说明预期的 `pip install doc-chunker[nanobot]` 关系，尽管当前解析这个依赖需要先从 nanobot 自己的本地路径安装它（nanobot 不在 PyPI 上）。

独立 Python 包 + CLI + nanobot Tool 是选定边界（见 `DECISIONS.md` D001）。Tool 适配层通过 `[project.entry-points."nanobot.tools"]` 注册；本轮曾经草拟过一个 nanobot Skill 作为可选的第三层集成，但后来删除，因为作业文本明确把 Tool/Skill/mixed 列为可替代选项，而不是叠加要求（“它可以是...Tool 或 Skill,也可以混合”）。

## 假设

- **输入是本地且可信的。** 传给 `parse_document()`/`ingest_document()` 的所有路径，都假设是调用者已经有合法文件系统访问权的文件。模块不做 sandbox、大小上限或恶意文件处理（例如 `.docx`/`.xlsx` 这类 zip 容器中的 zip bomb）。
- **单进程、单写者。** `DocumentStore` 不做文件锁。对同一个 store 目录并发调用 `ingest_document()` 不安全；这符合题目描述的单用户 CLI/agent-tool 使用模式，而不是多写者服务。
- **“文档”由 resolved path 标识，而不是由内容标识。** 重新导入同一路径总是整体替换该 `doc_id` 的 chunk（见 `DECISIONS.md` D003）。重命名文件会被视为新文档；这是简化取舍，不是疏漏。
- **`max_chars`/`overlap_chars` 是字符数，不是 token 数。** 模块假设调用方（或下游 embedding/LLM 步骤）负责 token budget 转换；选择字符长度，是为了不把模块绑定到某个 tokenizer 上（见 `DECISIONS.md` D007）。
- **`heading_path` 是“章节”的可靠代理，但不是保证。** 对于没有标题信号的格式（`.txt`/`.md`/`.csv`，或没有 outline 的 PDF），`heading_path` 为空，`expand="section"` 会退化为“整个文档”；调用方应能接受这种退化，而不是把它视为错误（见已知限制）。
- **下游消费者读取 `chunks.jsonl`/`search()`/`export` 输出，而不是直接依赖内部 store 文件。** `manifest.json` 的精确形状不像 `Chunk` 字段那样被视为稳定公开契约；它可以新增字段，而不被认为是 breaking change。
- **nanobot 集成目标是 `entry_points` 形式的 Tool 加载路径**，也就是写 `DECISIONS.md` D001 时 `nanobot/agent/tools/loader.py` 中描述的机制。如果上游机制变化，仍然假设适配层边界（薄 `Tool` 子类）是正确形状，只是注册机制可能需要更新。

## 已知限制

- 搜索是关键词匹配，不是语义检索。
- DOCX 标题抽取处理常见的 `Heading1`、`Heading2` 样式名，但不能覆盖所有本地化 Word 样式。
- PDF 质量依赖可抽取文本；扫描版 PDF 需要 OCR，超出范围。PDF 标题抽取依赖文件自带 outline/bookmark tree；没有 outline 的 PDF 没有标题结构（通过 `metadata["pdf_headings"] = "unavailable"` 显式记录，而不是静默缺失）。
- **一页 PDF 上有多个标题时，只有第一个（按 outline 阅读顺序）会附加到该页的 `heading_path` 上。** 每个 PDF 页面目前只生成一个 `DocumentBlock`（page-level 粒度），所以一页里如果有三个 heading（例如 `samples/Document Chunker Validation Sample.pdf` 第 2 页同时有 "Retention Policy"、"Access Control"、"Table Context Example"），这一页产出的所有 chunk 会共享第一个 heading（"Retention Policy"）的 `heading_path`，后两个 heading 下的内容会被贴上前一个 heading 的标签——这正是本项目要避免的那类"贴错标签"问题，只是发生在页内而不是跨页。本轮把"最后一个 heading 覆盖前面的"（更差的行为）改成了"第一个 heading 生效"（`_pdf_page_headings()` 用 `setdefault` 而不是无条件覆盖），但没有做真正的页内按标题位置切分——那需要用 pypdf 的坐标/visitor 信息按 heading 的 y 坐标切割页面文本，属于一次架构级改动（要把 PDF 的 block 粒度从"每页一个"改成"每个标题区间一个"），评估后判断不值得为这一版投入，留在后续需要时再做。
- 不解析 Word 表格（`w:tbl`），只解析段落（`w:p`）。本版本表格支持仅限 Excel（见 `DECISIONS.md` D006）。
- 不过滤 PDF 页眉/页脚；`parse_pdf()` 会按原样抽取整页文本。
- `max_chars` 是软限制：句子 splitter 产出的 chunk 可能达到 `max_chars + overlap_chars`，因为构造出带 overlap 前缀的 candidate 后没有再次按 `max_chars` 检查。这里选择记录而不是悄悄修改，因为修复它会改变 chunk 边界，而这不是当前要求必需的行为变化。
- `get_section`/`search(expand="section")` 每次调用都会扫描完整 `load_chunks()` 结果（无索引）。在 JSONL/单机规模下没问题；如果后端需要处理大型多文档 store，这是第一个优化点。
- `.txt`/`.md`/`.csv` 是 PDF/DOCX/XLSX 要求之外的低成本 demo/测试格式；它们不会填充 `heading_path`，因此 `expand="section"` 对这些格式会退化为“整个文档”。
- 重新导入同一路径总是完整重新解析和重新分块；没有变更检测或 unchanged skip。本轮较早草稿加入过基于 content-hash 的跳过逻辑，后来因为不属于作业要求而移除（见 `DECISIONS.md` D008）。
- 没有自动检查 prev/next chunk 链接是否互相一致；较早草稿加入过 `validate_export()` 完整性检查，也因为相同原因移除。

## 一周扩展计划

如果再给一周，按优先级：


1. 在现有关键词匹配上加入 BM25 排序，仍然不引入 embedding 依赖；`search()` 的签名已经把排序与存储隔离，因此不影响调用方;before/after参数。
2. 增强表格分块，支持合并单元格、多行表头和 Word 表格（`w:tbl`）;增强pdf的解析方式（标题-排版）; heading path。
3. 添加一个集成测试：让真实 nanobot `ToolLoader`/`ToolRegistry` 加载已安装的 entry point，而不只是检查 `entry_points()` 能解析（见 `TESTING.md`）。
4. 添加 prev/next 链接完整性检查和基于变更检测的 re-ingest skip；两者都在本项目升级过程中做过原型，又因为不在原始范围内被移除（见 `DECISIONS.md` D009），但它们都很小、边界清楚，有更多时间时可以合理加回。

## 更长期路线图（一周之外）

更远期，大致按作业自身“一周扩展”提示的方向排序：先检索质量，再结构覆盖，最后集成广度。

1. **语义检索。** 增加 embedding-backed index（本地模型或 API 方式），作为 `ChunkStore` 邻近的第二条检索路径，同时保留关键词搜索作为零依赖 fallback。这是对回答质量杠杆最大的变化，但明确超出当前版本范围（见目标）。
2. **布局感知解析。** 在 feature flag 后面把 PDF/DOCX 解析切到 layout model（例如 Docling），以获得纯文本抽取做不到的表格结构、多栏布局和页眉/页脚过滤；代价是放弃当前“到处可运行、无需模型下载”的属性。为什么没有从这里开始，见 `DECISIONS.md` 中关于 license/environment 风险的讨论。
3. **增量更新。** 做真正的 content-addressed diff（不是本轮试过又移除的粗粒度 content-hash skip），让大文档的某个章节变化时不必强制重分块整个文件。
4. **多租户 / 并发写入存储。** 如果这个模块要支撑共享服务，而不只是单个 CLI/agent-tool 用户，就需要重新审视“单进程、单写者”假设（见假设）；很可能要从平面 JSONL 迁移到带真实事务的 SQLite 后端。
5. **MCP server 适配器。** 一旦出现非 Python 或跨 agent 消费者的具体需求，就用 MCP server 包一层同一个核心包，不需要改 `parsers.py`/`chunker.py`/`store.py`。
