# REVIEW_FINDINGS.md

面试官视角的代码评审。评审对象:另一个 LLM 会话(AI_WORKFLOW.md Session 2/3)在
`src/doc_chunker/` 下产出的第一版实现,对照原始需求文档(数据模型/接口契约/存储抽象/
CLI/nanobot 集成的完整要求)和 `DECISIONS.md` 里记录的设计决策。

**方法论声明**:下面每一条"确认(Confirmed)"的问题都不是读代码猜出来的,而是我实际跑了
代码验证过的(命令附在每条后面,可以直接复现)。"未验证(Unverified)"的条目会明确标注,
不混在一起充数。

**总体结论:尚未达到可以直接提交面试的状态。** 不是因为代码跑不起来(`pytest` 9 个用例
确实全过),而是因为:(a) 原始需求里明确写的几个"必须有"的接口/能力(`get_neighbors`、
`get_by_document`、内存后端、分块策略模式、`export` 子命令、可选依赖 extras)整体缺失;
(b) 已经实现的核心分块逻辑里,有两个真实可复现的 bug,而且都恰好打在"上下文感知分块"
这个项目的核心卖点上;(c) 项目最想证明的那件事——"nanobot 通过 entry_points 自动发现
这个 Tool"——从未被真正跑过一次,所有"验证"都绕开了这条路径直接 `new` 了 Tool 类。

---

## 一、Critical:原始需求里明确要求、但完全没做的能力

### C1. 存储抽象只有一个具体类,没有接口,没有内存后端

**需求原文**:"存储抽象:ChunkStore / DocumentStore 接口,至少实现内存 + 本地文件(JSONL
或 SQLite)两种后端"。

**实际情况**:`src/doc_chunker/store.py` 只有一个具体类 `DocumentStore`,没有抽象基类/
`Protocol`,没有第二个后端。所有测试(`test_store.py`、`test_cli_and_tool.py`)都用
`tmp_path` 走真实磁盘 I/O,连"内存后端"这个概念在代码里都不存在。

**为什么重要**:这条需求是原始需求里唯一明确要求"至少两种实现"的一条,直接考察"存储抽象"
设计能力(接口 vs 实现分离)。现在的代码没有体现任何抽象——`ingest_document()`、
`cli.py`、`nanobot_tool.py` 全部直接 `import DocumentStore` 并耦合它的具体方法,换一个
后端(哪怕只是内存 dict)需要改调用方代码,不是"换一个实现类"就行。

**怎么改**:抽出一个 `ChunkStore` Protocol/ABC,定义 `write_document` /
`load_chunks` / `get_by_document` / `get_neighbors` / `search` 的签名;
`DocumentStore`(JSONL)和一个新的 `InMemoryChunkStore`(纯 dict,单元测试用)都实现它;
`pipeline.py`/`cli.py`/`nanobot_tool.py` 只依赖接口类型,不依赖具体类。

---

### C2. `get_neighbors(chunk_id)` 和 `get_by_document(doc_id)` 完全不存在

**需求原文**:"[ChunkStore] 必须包含 `get_neighbors(chunk_id)`(检索命中后扩展上下文用)
和 `get_by_document(doc_id)`"。

**确认(Confirmed)**:读了 `store.py` 全文——`DocumentStore` 只有
`write_document` / `load_chunks` / `search` / `_load_manifest` 四个方法。这两个被
写进需求原文、用括号特别注明用途的方法,一个都没写。

**为什么重要**:`prev_chunk_id`/`next_chunk_id` 已经存在于 `Chunk` 里,数据具备了,但
没有对外暴露"给我这个 chunk 前后 N 个"的查询方法——也就是说,下游检索模块命中一个 chunk
后,**没有任何编程接口能把上下文扩展回来**,而"扩展上下文"正是需求里给 `get_neighbors`
标注的用途,也是这个项目区别于"裸切文本"的核心价值之一。`get_by_document` 缺失则意味着
"给我某篇文档的全部 chunk"这种最基础的查询也做不到,只能自己在 `load_chunks()` 的全量
结果里手写 `if chunk.doc_id == ...` 过滤。

**怎么改**:在 `ChunkStore` 接口(见 C1)里加:
- `get_by_document(doc_id) -> list[Chunk]`:内部按 `doc_id` 过滤 `load_chunks()`
  即可,成本很低。
- `get_neighbors(chunk_id, before=1, after=1) -> list[Chunk]`:先按 `chunk_id` 找到
  目标 chunk,再顺着 `prev_chunk_id`/`next_chunk_id` 链表各走 N 步。注意要处理"链表
  跨文档"的边界(不应该借到别的文档的 chunk),以及"chunk_id 不存在"的情况。

---

### C3. 没有可插拔的分块策略,`chunk_blocks()` 是唯一一个写死的函数

**需求原文**:"策略模式接口 + 两个实现:`FixedSizeChunker`(baseline)、
`RecursiveStructureChunker`(默认,先章节→段落→句子逐级降级,可配 overlap)"。

**实际情况**:`chunker.py` 里只有一个函数 `chunk_blocks()`,把"按 block 分组塞进
buffer"和"超长时按句子/硬切分"混在一起,没有类、没有接口、没有第二种策略。想加一个
`FixedSizeChunker` 做 baseline 对比,现在要复制整段逻辑,不是"换一个策略对象"。

**怎么改**:定义一个 `ChunkerStrategy` Protocol(`chunk(blocks, config) -> list[Chunk]`),
现在这个函数改名重构成 `RecursiveStructureChunker`,再单独写一个纯粹按字符数切、不管
句子边界的 `FixedSizeChunker` 作为 baseline(这个反而是最简单的,可以用来在测试/demo里
对比"不做语义边界切分,断句质量会差多少",本身就是一个很好的面试展示点)。

---

### C4. CLI 缺 `export` 子命令

**需求原文**:"CLI 子命令集(至少 `ingest` / `query` / `export`)"。

**确认(Confirmed)**:`cli.py` 的 `build_parser()` 只注册了 `ingest` 和 `search`
两个子命令(`search` 基本等价于需求里的 `query`,命名不同不算大问题,但 `export`
是另一个能力,完全没有)。

**为什么重要**:`export` 通常是"把一个 store 里的 chunk 完整导出成某种下游可消费格式"
(比如直接导出 `chunks.jsonl` 的过滤视图,或转成某个向量库的导入格式)。现在没有这个命令,
意味着"和下游检索模块对接"这条需求线只停在"下游自己去读 `chunks.jsonl`"这个最原始的
程度,CLI 没有对这件事提供任何帮助。

**怎么改**:最小实现——`doc-chunker export <store_dir> --doc-id <id> --out <file>`,
直接把 `get_by_document`(见 C2)的结果写成 JSON/JSONL 到指定路径。不需要做格式转换,
能体现"这是一个独立的、有意义的导出动作"就够。

---

### C5. `pyproject.toml` 没有声明可选依赖 extras

**需求原文**:"可选依赖的声明方式(如 extras:`pip install docchunk[nanobot]`)"。

**确认(Confirmed)**:`pyproject.toml` 只有 `[project.dependencies]`(pypdf、
openpyxl)和 `[project.entry-points."nanobot.tools"]`,没有
`[project.optional-dependencies]` 段落。"适配层可选"这件事只在 `nanobot_tool.py`
的 `try/except ImportError` 里体现,包元数据层面完全没表达出来。

**为什么重要**:这是原始需求点名要求的声明方式,而且是"包设计"这个能力项里最容易在面试里
被追问的一句话——"你怎么让用户知道 nanobot 支持是可选的?"现在的答案只能是"看
源码里的 try/except",不是"看 `pyproject.toml`"。

**怎么改**:加
```toml
[project.optional-dependencies]
nanobot = ["nanobot"]
```
即使 `nanobot` 本身不在 PyPI 上、这个 extra 实际不能被 pip 解析安装,也应该把它写出来
作为"意图声明",并在 README 里说明"当前 nanobot 通过本地路径而非 PyPI 安装,extra
仅用于表达依赖关系"。

---

## 二、Critical:已实现功能里,live 验证出的真实 bug

### C6. 中文分句在真实中文文本(句间无空格)上完全不生效

**需求原文**:"中文分句需处理全角标点"、"按段落/句子等语义边界切分,不把一句话拦腰截断"。

**确认(Confirmed,可复现)**:`chunker.py:117` 的分句正则是
`re.split(r"(?<=[.!?。!?])\s+", text)`——切分触发条件是"全角/半角标点 **后面跟着
空白字符**"。但真实中文书写习惯里,句号后面几乎从不加空格。实测:

```python
zh_text = "这是第一句用来测试中文分句的效果。这是第二句同样需要被正确切分。这是第三句继续增加长度以触发切分逻辑。这是第四句确保超过配置的字符上限。"
chunk_blocks([DocumentBlock(text=zh_text, ...)], doc_id="zh-doc",
             config=ChunkingConfig(max_chars=40, overlap_chars=5))
```

实际输出(两个 chunk):
```
chunk[0].text = "这是第一句用来测试中文分句的效果。这是第二句同样需要被正确切分。这是第三句继续增"
chunk[1].text = "三句继续增加长度以触发切分逻辑。这是第四句确保超过配置的字符上限。"
```

"第三句"被从中间硬生生切成"第三句继续增" / "三句继续增加长度..."——`_split_text` 的
正则因为没匹配到任何"标点+空格",把整段话当成一个句子处理,长度超限后直接掉进
`_hard_split()`(纯字符数切片),这正是需求里明确禁止的"拦腰截断"。这不是边缘情况,是
**中文场景下的默认行为**——只要句子之间没有空格(几乎所有真实中文文档都是这样),句子
切分器就形同虚设。

**测试覆盖状态**:全仓库没有任何一条测试用中文文本跑过 `chunk_blocks`/`_split_text`。
这个需求点从写下来到现在,从未被测试触碰过。

**怎么改**:分句正则不应该依赖 `\s+`,应该直接在标点字符后面切,不要求后面有空格:
`re.split(r"(?<=[.!?。!?…])", text)`,再把切出来的空字符串过滤掉。同时要补至少一条
中文长文本测试,断言"标点前的字符"永远和"标点"在同一个 chunk 里、不会被从字符中间切断。

---

### C7. 把不同标题下的内容合并进同一个 chunk 时,`heading_path` 只保留第一个 block 的标题——即"张冠李戴"

**确认(Confirmed,可复现)**:`chunker.py:75-94` 的 `_append_chunk()` 只用
`first = blocks[0]` 取 `heading_path`,完全不管这个 chunk 里是不是还塞了别的 block。
实测:

```python
blocks = [
    DocumentBlock(text="Tail of section A.", heading_path=["Section A"], ...),
    DocumentBlock(text="Start of section B.", heading_path=["Section B"], ...),
]
chunk_blocks(blocks, doc_id="doc-x", config=ChunkingConfig(max_chars=200, overlap_chars=10))
```

输出:
```json
{"text": "Tail of section A.\n\nStart of section B.", "heading_path": ["Section A"]}
```

这个 chunk 里明明包含"Section B"的内容,`heading_path` 却只写着"Section A"。任何
消费这个字段做"这段话属于哪个章节"判断的下游逻辑(高亮引用来源、按章节过滤检索结果等),
都会把 Section B 的内容误判成 Section A 的。

**为什么这是最该优先修的一条**:这个项目存在的理由就是"上下文感知分块,缓解断章取义"。
这个 bug 恰好是——分块器自己把跨章节的内容标注成了错误的章节。如果面试官问"你怎么保证
分块不会断章取义",而现场演示恰好踩到这个组合(两个短段落分属不同标题、又刚好能塞进
一个 chunk),会直接自我推翻这个项目的核心卖点。

**怎么改**:两个方向选一个:(a) 更保守——只要下一个 block 的 `heading_path` 和当前
buffer 不同,就强制 flush,不允许跨标题合并(简单,但可能产生更多小 chunk);
(b) 更准确——`heading_path` 记录这个 chunk 覆盖的所有不同标题(比如变成
`list[list[str]]` 或者在 `metadata` 里加 `heading_paths: [...]`),不再假设一个
chunk 只属于一个标题。方案 (a) 更符合"简单、自洽"的原则,建议优先选它。

---

### C8. nanobot 集成的"entry_points 自动发现"这条路径,从未被真正验证过一次

**确认(Confirmed)**:
```bash
pip show doc-chunker        # → WARNING: Package(s) not found
python -c "from importlib.metadata import entry_points; print(list(entry_points(group='nanobot.tools')))"
# → []
```
`doc-chunker` 包目前在这台机器上**没有被安装过**(不是 `pip install -e .`,也不是普通
安装),所以 `entry_points(group="nanobot.tools")` 查出来是空列表。而
`tests/test_cli_and_tool.py` 里对 `DocumentChunkerTool` 的"验证",做法是直接
`DocumentChunkerTool()` 实例化后调用——这完全绕开了 `pip install` → nanobot
`ToolLoader._discover_plugins()` 扫描 entry_points → 反射加载类 → `enabled()`/
`create()` → 注册进 `ToolRegistry` 这一整条真实路径。

**为什么这是最核心的一条**:D001 选"独立包 + entry_points"而不是别的方案,理由就是
"能验证真的接进了 nanobot"。现在测试证明的只是"这个类满足 `Tool` 抽象基类的接口形状",
没有证明"nanobot 真的能发现并调用它"。这是整个项目里唯一一条"必须端到端跑一次才算数"
的需求,现在恰恰是唯一没跑过的。

**怎么改(不需要发布到 PyPI)**:
1. 在项目根目录跑 `pip install -e .`(editable install),再跑上面那条
   `entry_points` 检查命令,确认这次能看到
   `EntryPoint(name='document_chunker', value='doc_chunker.nanobot_tool:DocumentChunkerTool', group='nanobot.tools')`。
2. 更进一步:写一个真正调用 nanobot 的 `ToolLoader`/`ToolRegistry`(第一轮调研里已经
   读过源码,知道类在哪)的集成测试,断言 `"document_chunker" in registry.tool_names`,
   而不是只测 `DocumentChunkerTool()` 这个类本身。这一步能不能做,取决于要不要让
   `doc-chunker` 的测试依赖 `nanobot` 这个包被安装——如果不想要这个测试依赖,至少要在
   `TESTING.md`/`README.md` 里如实写清楚"entry_points 发现路径尚未做集成测试,已知
   风险点",不要让"9 passed"给人一种"集成也验证过了"的错觉。

---

## 三、High:测试"看起来通过"但没有真正覆盖到的地方

### H1. PDF 解析测试依赖一个项目自己没有声明的库,干净环境里会静默跳过

**确认(Confirmed)**:
```bash
pip show pymupdf   # Name: PyMuPDF, Version: 1.27.1 —— 已安装
grep -A3 "^dependencies" pyproject.toml   # 只有 pypdf、openpyxl,没有 pymupdf/fitz
```
`test_parsers.py::test_parse_pdf_extracts_page_text` 用
`pytest.importorskip("fitz")` 造测试用 PDF,而 `fitz`(PyMuPDF)是这台机器上因为装了
别的东西(这个 conda 环境里恰好也装了 nanobot 的开发依赖)才存在的,**不是 doc-chunker
自己声明的依赖**。在一个只按 `pyproject.toml` 干净安装 doc-chunker 的环境里,`fitz`
不存在,`importorskip` 会让这条测试**静默跳过**,而不是失败——`pytest -q` 的输出会从
"9 passed"变成"8 passed, 1 skipped",很容易被忽略掉,而"skipped"意味着
`parse_pdf()`(用 `pypdf`,不是 `fitz`)这条真正会被用户跑到的代码路径,**在干净环境
里完全没有被测试执行过**。

**为什么重要**:招聘要求明确写着交付物要"能在干净环境跑起来",而且要求候选人展示
"验证方法论"。这正是一个"测试在我机器上是绿的,但换个干净环境会静默变弱"的经典陷阱,
如果不主动检查 verbose 输出根本发现不了。

**怎么改**:测试造 PDF 不应该依赖 `fitz`,应该直接用项目已经声明的 `pypdf`(它也有
写 PDF 的能力有限,或者更简单——用一个签入仓库的最小 PDF 样例文件,不现场生成)。或者
如果就是想测"两套 PDF 库都能兼容",把 `pymupdf` 显式加进
`[project.optional-dependencies]` 的一个 `test` extra 里,不要让它隐式存在。

---

### H2. `header_context`(D006 决策)没有变成结构化字段,只是"恰好"没丢信息

**确认(Confirmed)**:实际 ingest 一个 xlsx 文件后查看存储的 chunk:
```json
{
  "text": "Risk: Parser drift; Owner: Candidate",
  "metadata": {"block_types": ["table_row"], "block_count": 1}
}
```
`parse_xlsx()` 确实在 `DocumentBlock.metadata["headers"]` 里正确抓到了
`["Risk", "Owner"]`,但 `chunker.py` 的 `_append_chunk()` 重新构造
`metadata` 时只写了 `block_types`/`block_count`,完全丢弃了 `first.metadata`——
表头信息没有进入最终存储的 chunk 的结构化字段。**缓解因素**:`parse_xlsx()` 已经把
"列名: 值"格式化进了 `text` 本身,所以人类/LLM 读文本时不会真的看不出表头是什么;
真正缺失的是"下游代码想不解析文本、直接拿到 `chunk.metadata["header_context"]`
编程访问表头"这个能力,这是 D006 明确决定要做但没有实现的部分。

**怎么改**:`_append_chunk()` 在构造 `metadata` 时,应该把各 block 的
`metadata` 合并进去(至少把 `first.metadata` 里已有的键并进来),而不是完全用一个
新字典覆盖。

---

## 四、Medium:设计记录完整性 & 正确性的"松散地带"

### M1. `DECISIONS.md` D003–D007 和实际实现明显对不上,而且这个落差被"绕过"而不是"修正"

**确认(Confirmed)**:对照 `DECISIONS.md` 逐条核对实际代码:

| DECISIONS.md 记录的决策 | 实际代码 |
|---|---|
| D003: `doc_id = sha256(路径)[:16]` | `pipeline.py::_doc_id` 用 `sha1(...)[:10]` 且前面拼了文件名 slug,算法和长度都不一样 |
| D004: `chunk_id = f"{doc_id}:{chunk_index:06d}"`(从 0 起,6 位) | `chunker.py::_append_chunk` 用 `f"{doc_id}:{len(chunks)+1:04d}"`(从 1 起,4 位) |
| D005: `chunk_type ∈ {narrative, heading_only, table}` | `Chunk` 模型里**根本没有 `chunk_type` 字段**,只有 `metadata["block_types"]`,是完全不同的概念 |
| D006: `header_context` 通用字段 | 不存在(见 H2) |
| Chunk 完整字段清单(`char_offset`/`token_count`/`content_hash`/`element_ids`/`overlap_*` 等) | 实际 `Chunk` 只有 9 个字段,清单里列的字段几乎都没有 |

`AI_WORKFLOW.md` Session 3 里其实已经承认了这件事("`DECISIONS.md` 后半段存在一些
后追加的设计草稿与当前实现不完全一致"),但处理方式是"面试讲稿只引用当前代码,不提
这些草稿"——这解决了"面试时不说错话"的问题,但没有解决"`DECISIONS.md` 本身现在是一份
不准确的设计记录"这个问题。招聘要求明确要交付"设计决策与取舍"文档,如果面试官真的翻开
`DECISIONS.md` 对照代码看,会直接发现"写的和做的不一致",这比"没写设计文档"观感更差。

**怎么改**:不需要回改 D003–D007 的历史记录(违反"不回填修改历史决策"的约定),但应该
新增一条 D008,明确写"D003–D007 中记录的字段清单/命名方案是设计阶段的结论,第一版实现
做了进一步简化,实际字段以 `models.py` 为准,差异见 REVIEW_FINDINGS.md",把这个落差
显式承认下来,而不是留着不提。

---

### M2. `max_chars` 只是一个软上限,实际可能超出 `max_chars + overlap_chars`

**确认(Confirmed)**:`tests/test_chunker.py` 自己的断言就承认了这件事——
`config=ChunkingConfig(max_chars=62, overlap_chars=20)` 却断言
`all(len(chunk.text) <= 82 for chunk in chunks)`,82 = 62 + 20。追根溯源是
`_split_text()` 里,`current = f"{overlap} {sentence}".strip() if overlap else sentence`
这一步生成新的 `current` 后,没有再检查它自己是不是也超过 `max_chars`,把这个检查推迟到
下一轮循环——如果 `sentence` 本身接近 `max_chars`,加上 `overlap` 后,这一个 chunk
就可能达到 `max_chars + overlap_chars`。这不是致命问题,但意味着"块大小可配置"这个
需求的实际语义是"软上限、允许溢出 overlap 那么多",而这一点没有在任何文档里写明,只是
悄悄把测试断言从"严格 ≤ max_chars"改成了"≤ max_chars + overlap_chars"来迁就实现。

**怎么改**:两选一——(a) 在文档里明确写清楚这个软上限的公式,不去动实现;(b) 在
`current` 更新后立即检查长度,超了就再截一刀。(a) 成本更低,如果时间紧张选它就够。

---

### M3. `manifest.json` 顶层字段和 `documents` 列表字段冗余且会互相"打架"

**确认(Confirmed)**:`store.py::write_document` 最后这样构造 manifest:
```python
manifest = {"version": 1, "chunk_count": len(all_chunks), "documents": docs, **doc_entry}
```
`**doc_entry` 把"这次刚写入的这一个文档"的 `doc_id`/`source_file`/`chunking`/
`updated_at` 摊平到顶层,而 `chunk_count` 却是全部文档的总数。如果一个 store 里塞了
两个文档,顶层的 `doc_id`/`source_file` 只反映最后一次 ingest 的那个文档,和
`chunk_count`(全量)语义不一致,读 manifest 的人容易被顶层字段误导以为"这个 store
只有一个文档"。

**怎么改**:manifest 顶层只保留 `version`/`chunk_count`/`documents`,去掉
`**doc_entry` 的展开,单文档信息只在 `documents` 列表里出现一次。

---

### M4. 解析格式范围悄悄扩大到 `.txt`/`.md`/`.csv`,没有决策记录

**需求原文只要求** PDF/DOCX/XLSX 三种格式,但 `parsers.py` 额外实现了
`.txt`/`.md`/`.csv`,`README.md` 把它们和 PDF/DOCX/XLSX 并列写进"Supported Inputs",
只在一句话里带过"included as low-cost demo and testing formats"。`.txt` 作为内部
测试夹具的存在完全合理,但没有对应的 `DECISIONS.md` 条目说明"为什么加了这些、边界在
哪"(比如 CSV 算不算长期要维护的能力,还是纯粹为了让 demo 数据准备更方便)。

**怎么改**:加一条轻量的 DECISIONS.md 记录,说明 txt/md 是测试夹具、CSV 是否要
保留为正式支持格式,把这条"范围之外的东西"显式管理起来,而不是靠 README 里一句话带过。

---

### M5. `AI_WORKFLOW.md` 存在未记录的会话缺口,且 Session 编号重复

**确认(Confirmed)**:当前 `AI_WORKFLOW.md` 里有两个"Session 2"(一个是"第一版
doc-chunker 闭环实现",一个是"数据模型设计")。同时,仓库里存在
`BEGINNER_GUIDE.md`(1405 行)、`STUDY_PATH.md`、
`docs/superpowers/plans/2026-07-06-doc-chunker.md`、`INTERVIEW_SCRIPT.md`、
`INTERVIEW_CHECKLIST.md` 这些文件,但 `AI_WORKFLOW.md` 里找不到任何一条会话记录
描述"是谁在什么要求下产出了这些文件"——建立这套记录的初衷就是"让评审者能看到每一步
AI 做了什么、有没有被指出错误",这几份文件的产出过程目前是空白的。

**为什么值得修**:这套 `DECISIONS.md`/`AI_WORKFLOW.md` 记录本身就是你要展示的"验证
方法论"的一部分,让它保持完整、无缺口,比让它内容更多更重要。

**怎么改**:补一条 Session 记录说明这些文件的来源(哪怕只是简单一句"由另一个会话在
XX 时间生成,未逐条记录过程"),并把编号理顺(下一条新记录用 Session 4,不要再产生
第二个"Session 2")。

---

## 五、需求里被跳过、但已经诚实披露的部分(不算隐藏问题,列出来只为了完整性)

- Word 表格完全不解析(`parse_docx` 只 `iter` `w:p`,不处理 `w:tbl`)——`DESIGN.md`
  的 Known Limits 里没提这一条,但 D006 决策明确说了"MVP 只做 Excel",算是有据可查,
  只是 `DESIGN.md` 应该把这条也写进 Known Limits,现在读者只能翻 `DECISIONS.md` 才知道。
- PDF 页眉页脚过滤——原设计第 4 项要求讨论至少一个可行方案,这一项设计从未产出(候选人
  跳过了 2-5 项的设计评审直接进入实现),`parse_pdf()` 目前就是整页 `extract_text()`,
  页眉页脚会原样进入 chunk 文本。建议至少在 `DESIGN.md` 的 Known Limits 里补一句。
- DOCX 标题层级只认 `HeadingN` 系列样式名——已经在 `DESIGN.md`/`AI_WORKFLOW.md` 里
  如实披露,不需要额外处理。

---

## 六、修复优先级建议(如果时间有限,按这个顺序做)

1. **C7(heading_path 张冠李戴)** —— 直接打脸项目核心卖点,修复成本低(方案 a:
   跨标题强制 flush),必须修。
2. **C6(中文分句失效)** —— 需求明确点名的场景,修复只需要改一个正则,收益远大于成本。
3. **C8(entry_points 从未验证)** —— 花 5 分钟跑一次 `pip install -e .` +
   entry_points 检查,把"从未验证"变成"验证过",是全项目里性价比最高的一次核查。
4. **C2(get_neighbors/get_by_document)** —— 需求原文点名的方法,补起来不难,而且
   `prev_chunk_id`/`next_chunk_id` 数据已经有了,只是没有查询接口包一层。
5. 如果还有时间:C1(存储接口抽象)、C3(策略模式)、C4(export)、C5(extras)、
   H1(PDF 测试依赖问题)按顺序做。
6. 文档类问题(M1/M4/M5)成本很低,可以在代码修复间隙顺手做,不需要单独排期。

在我看来,C6/C7/C8 三条如果讲解或演示时被面试官现场问到或恰好命中,会直接动摇"这个
模块真的做到了上下文感知"和"真的接进了 nanobot"这两个最核心的宣称,优先级应该高于
C1–C5 这些"需求条目缺失但不影响已实现部分正确性"的问题。
