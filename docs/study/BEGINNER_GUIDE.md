# Beginner Guide: 读懂 doc-chunker 和 nanobot 集成

这份文档是给完全小白看的。目标不是让你背代码,而是让你能说清楚:

1. 这个项目到底解决什么问题。
2. 每个文件在干什么。
3. 一份文档从输入到输出经历了哪些步骤。
4. 它怎么接到 nanobot 的 Tool 系统里。
5. 为什么现在这样做,而不是直接用 Docling、Unstructured、向量数据库或 MCP。

---

## 1. 先用一句话理解项目

这个项目做的是:

> 把 PDF、Word、Excel 等文档解析成文本块,再切成带上下文信息的 chunk,保存到本地文件,并暴露给 nanobot 作为一个可调用工具。

关键词解释:

- **文档解析**: 从 `.pdf`、`.docx`、`.xlsx` 里取出文字和结构信息。
- **chunk**: 把长文档切成小片段。RAG/问答系统通常不会一次把整篇文档塞给模型,而是先找到相关片段。
- **上下文信息**: chunk 不只保存文字,还保存它来自哪里,比如第几页、哪个 sheet、前后 chunk 是谁。
- **Tool**: nanobot 给 agent 使用的外部能力。比如读文件、执行命令、搜索网页,这里新增的是 `document_chunker`。
- **adapter**: 适配层。核心 chunker 不直接依赖 nanobot,但 `doc-chunker/src/doc_chunker/nanobot_tool.py` 把它包装成 nanobot 能认识的 Tool。

---

## 2. 整体流程图

直接使用 CLI 时:

```text
你在 PowerShell 输入命令
  -> doc_chunker.cli (`doc-chunker/src/doc_chunker/cli.py`)
  -> ingest_document()
  -> parse_document()
  -> chunk_blocks()
  -> DocumentStore.write_document()
  -> doc-chunker/.doc_index/manifest.json + doc-chunker/.doc_index/chunks.jsonl
```

在 nanobot WebUI 里使用时:

```text
你在 WebUI 里发自然语言
  -> nanobot agent 判断要调用工具
  -> ToolRegistry 找到 document_chunker
  -> DocumentChunkerTool.execute()
  -> ingest_document() 或 DocumentStore.search()
  -> nanobot 把工具结果总结给你
```

区别:

- CLI 是**模块级验证**: 证明 doc-chunker 自己能跑。
- WebUI 是**系统级集成验证**: 证明 nanobot 能发现并调用它。

---

## 2.5 本模块的边界和上下游集成方式

面试或答辩时,不要只说“我写了一个文档分块工具”。更关键的是说清楚:

```text
这个模块负责什么?
它不负责什么?
它从哪里接输入?
它把结果交给谁?
它和 nanobot 的边界在哪里?
```

这就是“模块边界”和“上下游集成方式”。

### 2.5.1 一句话说清边界

`doc-chunker` 的边界可以这样理解:

> `doc-chunker` 负责把本地文档解析成统一结构,切成带上下文的 chunk,并保存成可检索的本地索引;它不负责聊天、不负责模型推理、不负责 WebUI 展示,也不负责 embedding 或向量数据库。

换成更白话的说法:

```text
nanobot 负责“和用户对话、决定什么时候用工具”。
doc-chunker 负责“把文件变成可查的文本块”。
本地索引文件负责“把结果保存下来,下次还能搜”。
```

所以它不是一个完整 RAG 系统,而是 RAG 系统里“文档处理和本地检索”的一小块。

### 2.5.2 本模块负责什么

`doc-chunker` 主要负责五件事。

第一,接收一个本地文件路径。

例如:

```powershell
python -m doc_chunker.cli ingest samples\example.txt --out .doc_index
```

这里的输入是:

```text
samples\example.txt
```

第二,根据文件类型解析内容。

这一步在 `doc-chunker/src/doc_chunker/parsers.py` 里完成。它把不同格式统一成 `DocumentBlock`:

```text
TXT/MD -> 段落 block
DOCX   -> 段落和表格 block
XLSX   -> sheet/row/cell block
PDF    -> page text block
```

第三,把 `DocumentBlock` 切成 `Chunk`。

这一步在 `doc-chunker/src/doc_chunker/chunker.py` 里完成。它关心的是:

```text
每个 chunk 不要太长
chunk 之间可以有 overlap
chunk 要保留来源信息
chunk 之间要能知道前后关系
```

第四,把 chunk 写入本地索引。

这一步在 `doc-chunker/src/doc_chunker/store.py` 里完成。结果主要落到:

```text
doc-chunker/.doc_index/manifest.json
doc-chunker/.doc_index/chunks.jsonl
```

第五,提供一个简单搜索接口。

搜索仍然在 `DocumentStore.search()` 里完成。当前版本是关键词搜索,不是 BM25,也不是向量搜索。它的目标是证明:

```text
写进去的 chunk 可以被重新读出来
用户给一个 query 后可以返回相关 chunk
返回结果里带有上下文和来源信息
```

### 2.5.3 本模块不负责什么

边界说清楚时,“不负责什么”也很重要。

`doc-chunker` 不负责 LLM 推理。它不会自己调用 OpenAI、Claude 或其他大模型。真正决定“下一步说什么”的是 nanobot agent,不是 doc-chunker。

`doc-chunker` 不负责 WebUI。它不画按钮,不管理聊天窗口,不处理用户登录,不决定前端怎么展示。WebUI 只是用户和 nanobot agent 交互的地方。

`doc-chunker` 不负责 agent 决策。用户在 WebUI 里说“帮我导入这个文档”,nanobot agent 决定要不要调用 `document_chunker`。`doc-chunker` 只是在被调用之后执行任务。

`doc-chunker` 不负责复杂检索排序。当前版本没有 BM25、embedding、reranker、向量数据库。这样做是为了让第一版足够小,重点落在:

```text
解析 -> 分块 -> 存储 -> 集成 -> 验证
```

以后要升级检索,可以替换 `DocumentStore.search()` 或新增 store 后端,不需要推翻 parser 和 chunker。

`doc-chunker` 不负责权限系统和安全沙箱。它假设调用方传入的是一个可读取的本地路径。如果路径不存在,它返回错误;但它不设计复杂的用户权限、租户隔离或远程文件下载。

### 2.5.4 上游是谁

上游就是“谁来调用 doc-chunker”。

这个项目里有两个上游入口。

第一个上游是 CLI。

对应文件:

```text
doc-chunker/src/doc_chunker/cli.py
```

CLI 的输入来自命令行参数:

```powershell
python -m doc_chunker.cli ingest samples\example.txt --out .doc_index
python -m doc_chunker.cli search .doc_index "chunker validation"
```

CLI 适合做模块级验证。也就是说,不启动 nanobot,只验证 doc-chunker 自己是否能工作。

第二个上游是 nanobot agent。

对应文件:

```text
doc-chunker/src/doc_chunker/nanobot_tool.py
```

用户不是直接调用 Python 函数,而是在 WebUI 里说自然语言。nanobot agent 判断需要工具后,通过 ToolRegistry 调用:

```python
await DocumentChunkerTool.execute(...)
```

这个入口适合做系统级集成验证。它证明:

```text
nanobot 能发现 document_chunker
nanobot 能按 schema 传参数
document_chunker 能返回结构化结果
agent 能拿结果继续回答用户
```

### 2.5.5 下游是谁

下游就是“doc-chunker 把结果交给谁”。

第一层下游是本地索引文件:

```text
doc-chunker/.doc_index/manifest.json
doc-chunker/.doc_index/chunks.jsonl
```

`manifest.json` 保存文档级信息,像一本目录:

```text
这个索引里有哪些文档?
每个文档的 doc_id 是什么?
源文件在哪里?
用了什么 parser?
切出了多少 chunk?
chunking 参数是什么?
更新时间是什么?
```

`chunks.jsonl` 保存 chunk 级信息,像真正的内容库:

```text
chunk_id
doc_id
text
locator
metadata
prev_chunk_id
next_chunk_id
```

第二层下游是 CLI 或 nanobot 收到的 JSON 结果。

CLI 会把结果打印到终端。nanobot tool 会把结果返回给 agent:

```text
DocumentChunkerTool.execute()
  -> json.dumps(payload)
  -> nanobot agent
  -> WebUI 展示或继续推理
```

注意:下游不是直接的大模型训练数据,也不是向量库。当前版本的下游就是“本地可检查文件”和“工具调用返回值”。

### 2.5.6 内部模块边界

内部边界可以按六层理解。

第一层是 parser。

文件:

```text
doc-chunker/src/doc_chunker/parsers.py
```

职责:

```text
输入: 文件路径
输出: list[DocumentBlock]
```

parser 只关心“怎么从不同文件格式里读出内容”。它不关心 chunk 大小,不关心怎么保存,也不关心 nanobot。

第二层是 model。

文件:

```text
doc-chunker/src/doc_chunker/models.py
```

职责:

```text
定义 DocumentBlock 和 Chunk 长什么样
提供 to_dict()/from_dict() 方便存储和读取
```

model 是各层之间的共同语言。parser 输出 `DocumentBlock`,chunker 输出 `Chunk`,store 保存 `Chunk`。

第三层是 chunker。

文件:

```text
doc-chunker/src/doc_chunker/chunker.py
```

职责:

```text
输入: list[DocumentBlock]
输出: list[Chunk]
```

chunker 不应该关心这个 block 原来是 PDF 还是 DOCX。它只处理统一后的 `DocumentBlock`。这就是 parser 和 chunker 分开的价值。

第四层是 store。

文件:

```text
doc-chunker/src/doc_chunker/store.py
```

职责:

```text
输入: doc_id、source_file、chunks、parser、chunking 参数
输出: manifest.json 和 chunks.jsonl
```

store 不负责解析文档,也不负责切 chunk。它只负责落盘、读取和搜索。

第五层是 pipeline。

文件:

```text
doc-chunker/src/doc_chunker/pipeline.py
```

职责:

```text
把 parser、chunker、store 串起来
```

它是主流程:

```text
ingest_document()
  -> parse_document()
  -> chunk_blocks()
  -> DocumentStore.write_document()
```

pipeline 自己不做具体解析,也不直接写 JSONL 的细节。它像一个调度员。

第六层是入口适配层。

CLI 文件:

```text
doc-chunker/src/doc_chunker/cli.py
```

nanobot Tool 文件:

```text
doc-chunker/src/doc_chunker/nanobot_tool.py
```

它们都调用同一个核心能力:

```python
ingest_document(...)
DocumentStore(...).search(...)
```

区别只是入口不同:

```text
CLI 把命令行参数转换成函数参数
nanobot adapter 把 Tool 参数转换成函数参数
```

这说明核心逻辑没有被绑死在 WebUI 或 nanobot 里。

### 2.5.7 CLI 集成链路

CLI 链路是最容易调试的一条链路。

导入文档时:

```text
PowerShell
  -> python -m doc_chunker.cli ingest ...
  -> cli.py 解析命令行参数
  -> ingest_document()
  -> parse_document()
  -> chunk_blocks()
  -> DocumentStore.write_document()
  -> manifest.json + chunks.jsonl
  -> 终端打印 JSON 结果
```

搜索时:

```text
PowerShell
  -> python -m doc_chunker.cli search ...
  -> cli.py 解析 store_dir 和 query
  -> DocumentStore(store_dir).search(query)
  -> 读取 chunks.jsonl
  -> 返回 matches
  -> 终端打印 JSON 结果
```

为什么 CLI 很重要?

因为它让你不用启动整个 nanobot,也能证明核心模块能工作。面试时这叫“降低调试范围”:

```text
如果 CLI 都跑不通,问题在 doc-chunker 内部。
如果 CLI 能跑通但 WebUI 不行,问题多半在 nanobot 集成或工具加载。
```

### 2.5.8 nanobot 集成链路

nanobot 链路比 CLI 多了一层“工具发现”和“agent 调用”。

第一步,`doc-chunker/pyproject.toml` 声明 entry point:

```toml
[project.entry-points."nanobot.tools"]
document_chunker = "doc_chunker.nanobot_tool:DocumentChunkerTool"
```

这句话的意思是:

```text
我这个 Python 包提供了一个 nanobot 工具
工具名相关入口是 document_chunker
真正的类在 doc_chunker.nanobot_tool:DocumentChunkerTool
```

第二步,把 doc-chunker 安装进 nanobot 同一个 Python 环境:

```powershell
cd D:\Lenovo\nanobot
python -m pip install -e ..\doc-chunker
```

第三步,nanobot 的 ToolLoader 读取 entry points。

对应文件:

```text
nanobot/nanobot/agent/tools/loader.py
```

它会类似这样找工具:

```python
entry_points(group="nanobot.tools")
```

第四步,nanobot 创建并注册工具。注册之后,ToolRegistry 里就能通过名字找到:

```text
document_chunker
```

第五步,agent 决定调用工具。

用户可能在 WebUI 里说:

```text
请把这个文件导入索引
```

agent 看到工具 schema 后,生成类似这样的工具参数:

```json
{
  "action": "ingest",
  "store_dir": ".ui_index",
  "path": "samples/example.txt",
  "max_chars": 1000,
  "overlap_chars": 150
}
```

第六步,`DocumentChunkerTool.execute()` 接住参数。

对应文件:

```text
doc-chunker/src/doc_chunker/nanobot_tool.py
```

它会根据 `action` 分流:

```text
action=ingest -> 调用 ingest_document()
action=search -> 调用 DocumentStore.search()
```

第七步,工具结果返回给 agent。

工具返回的是 JSON 字符串或 `ToolResult.error(...)`。agent 收到后,再把结果组织成人类能读懂的话显示在 WebUI。

### 2.5.9 为什么这种边界适合 take-home

take-home 项目通常不是要你把所有工业级能力都做完,而是看你能不能:

```text
拆清楚问题
做出能跑的最小闭环
留下可扩展位置
证明每一层都能被验证
```

这个项目的边界有几个好处。

第一,容易单独测试。

```text
parser: 输入文件,是否得到 DocumentBlock?
chunker: 输入 DocumentBlock,是否得到合理 Chunk?
store: 写入后 manifest.json 和 chunks.jsonl 是否正确?
CLI: 命令是否能跑通,输出 JSON 是否符合预期?
nanobot adapter: schema 是否正确,execute() 是否按 action 调用正确逻辑?
```

第二,未来容易替换。

如果以后想用 Docling 或 Unstructured,主要替换 parser:

```text
parse_document() 内部变强
输出仍然是 DocumentBlock
chunker/store/pipeline 基本不用动
```

如果以后想用 BM25、SQLite 或向量数据库,主要替换 store/search:

```text
DocumentStore.search() 变强
parser/chunker/nanobot adapter 不需要重写
```

如果以后想接别的 agent 框架,主要替换 adapter:

```text
核心 ingest_document() 仍然可以复用
只需要写新的 Tool 包装层
```

第三,面试时讲得清楚。

你不是在说:

```text
我堆了一堆库,然后能跑。
```

而是在说:

```text
我设计了清晰的数据契约和模块边界。
每层只做自己的事。
上游可以是 CLI 或 nanobot。
下游是本地索引和工具返回值。
未来可以替换 parser、store 或 adapter,不推翻整体结构。
```

### 2.5.10 面试时可以怎么说

可以这样回答:

> 这个模块的边界是文档处理和本地检索。上游可以是 CLI,也可以是 nanobot agent;下游是本地索引文件和工具调用结果。内部我把它拆成 parser、model、chunker、store、pipeline、adapter 几层:parser 把不同格式统一成 `DocumentBlock`,chunker 只面向统一结构生成 `Chunk`,store 负责 JSONL 落盘和搜索,pipeline 串起主流程,CLI 和 nanobot adapter 只是两个入口。这样设计的好处是每层都能单独测试,也方便以后把 parser 换成 Docling/Unstructured,或者把 store/search 换成 BM25、SQLite、向量库,而不用重写整个系统。

这段话的核心不是背术语,而是让面试官听出来:

```text
你知道自己写的模块在系统里的位置。
你知道它和 nanobot 的边界。
你知道第一版为什么简单。
你也知道以后要往哪里扩展。
```

---

## 3. 项目文件地图

### 3.1 `doc-chunker/pyproject.toml`

作用:声明这是一个 Python 包,并告诉安装器如何安装、暴露命令和暴露 nanobot 插件。

关键部分:

```toml
[project]
name = "doc-chunker"
dependencies = [
    "pypdf>=5.0.0",
    "openpyxl>=3.1.0",
]
```

含义:

- `pypdf`: 解析 PDF。
- `openpyxl`: 解析 Excel。

```toml
[project.scripts]
doc-chunker = "doc_chunker.cli:console_main"
```

含义:

- 安装后可以出现一个命令行命令 `doc-chunker`。
- 它最终会调用 `doc-chunker/src/doc_chunker/cli.py` 里的 `console_main()`。

```toml
[project.entry-points."nanobot.tools"]
document_chunker = "doc_chunker.nanobot_tool:DocumentChunkerTool"
```

含义:

- 这是和 nanobot 集成的关键。
- `nanobot.tools` 是 nanobot 约定的插件组名。
- `document_chunker` 是插件名字。
- `doc_chunker.nanobot_tool:DocumentChunkerTool` 是要加载的 Python 类。

基础概念: **entry points**

Python 官方打包规范里,entry points 是“已安装包向其他程序声明自己提供了某些可发现组件”的机制。常见用途有两个:

- `console_scripts`: 安装命令行工具。
- 自定义 group: 让应用发现插件。

nanobot 用的就是第二种。它不是 import 你本地目录,而是通过 Python 的安装元数据发现已经安装的包。所以要让 WebUI 里能用,必须把 `doc-chunker` 安装进 nanobot 同一个 Python 环境:

```powershell
cd D:\Lenovo\nanobot
python -m pip install -e ..\doc-chunker
```

---

## 4. 核心数据模型: `doc-chunker/src/doc_chunker/models.py`

文件: `doc-chunker/src/doc_chunker/models.py`

这个文件定义两个最重要的数据结构:

### 4.1 `DocumentBlock`

```python
@dataclass(frozen=True)
class DocumentBlock:
    text: str
    source_file: str
    block_type: str
    locator: dict[str, Any]
    heading_path: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
```

你可以把 `DocumentBlock` 理解成:

> 文档刚解析出来时的“原始结构块”。

例子:

PDF 第 2 页:

```json
{
  "text": "这一页的文本",
  "source_file": "a.pdf",
  "block_type": "page",
  "locator": {"page": 2}
}
```

Excel 第 5 行:

```json
{
  "text": "Risk: Parser drift; Owner: Candidate",
  "source_file": "a.xlsx",
  "block_type": "table_row",
  "locator": {"sheet": "Risks", "row": 5},
  "heading_path": ["Risks"],
  "metadata": {"headers": ["Risk", "Owner"]}
}
```

为什么需要 `DocumentBlock`?

因为不同文件格式差别很大:

- PDF 按页。
- Word 按段落/标题。
- Excel 按 sheet/行。

如果后面的 chunker 直接处理 PDF/Word/Excel,它会很乱。所以我们先把所有格式统一成 `DocumentBlock`,后面 chunker 只关心一种输入。

这叫**中间表示**。英文常叫 intermediate representation,简称 IR。

### 4.2 `Chunk`

```python
@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    source_file: str
    locator: dict[str, Any]
    heading_path: list[str]
    prev_chunk_id: str | None
    next_chunk_id: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
```

你可以把 `Chunk` 理解成:

> 最终给检索/问答使用的小片段。

它比 `DocumentBlock` 更接近下游系统需要的东西。

关键字段:

- `chunk_id`: 这个 chunk 的唯一编号,如 `example-xxx:0001`。
- `doc_id`: 属于哪个文档。
- `text`: chunk 的正文。
- `locator`: 来源位置,如页码、段落号、sheet/row。
- `heading_path`: 所在标题路径。
- `prev_chunk_id`: 上一个 chunk。
- `next_chunk_id`: 下一个 chunk。
- `metadata`: 额外信息,比如 block 类型、表头等。

为什么要有 `prev_chunk_id` / `next_chunk_id`?

因为检索时某个 chunk 命中关键词,但回答问题时可能需要它前后一点内容。前后链接让系统能找回邻近上下文。

---

## 5. 文档解析: `doc-chunker/src/doc_chunker/parsers.py`

文件: `doc-chunker/src/doc_chunker/parsers.py`

核心函数:

```python
def parse_document(path: str | Path) -> list[DocumentBlock]:
```

它根据文件后缀分发:

```python
if suffix in {".txt", ".md"}:
    return parse_text(file_path)
if suffix == ".docx":
    return parse_docx(file_path)
if suffix == ".xlsx":
    return parse_xlsx(file_path)
if suffix == ".csv":
    return parse_csv(file_path)
if suffix == ".pdf":
    return parse_pdf(file_path)
```

这叫**dispatcher**: 一个入口函数,根据类型调用不同实现。

### 5.1 TXT/MD 解析

```python
text = path.read_text(encoding="utf-8")
for i, para in enumerate([p.strip() for p in text.split("\n\n") if p.strip()], start=1):
```

含义:

- 读取纯文本。
- 用空行 `\n\n` 当段落分隔。
- 每个段落变成一个 `DocumentBlock`。

这是最简单、最适合 demo 的格式。

### 5.2 DOCX 解析

DOCX 本质上不是一个普通文本文件,而是一个 zip 包,里面有 XML。

代码:

```python
with zipfile.ZipFile(path) as zf:
    xml = zf.read("word/document.xml")
root = ET.fromstring(xml)
```

含义:

- 用 `zipfile` 打开 `.docx`。
- 读取 `word/document.xml`。
- 用 `xml.etree.ElementTree` 解析 XML。

为什么不用 `python-docx`?

第一版为了减少依赖,直接读 Office Open XML。这样足够证明段落和常见标题能提取。缺点是复杂 Word 结构处理不完整,例如复杂表格、脚注、文本框等。

标题处理:

```python
style = _paragraph_style(para)
level = _heading_level(style)
```

`_heading_level()` 会识别 `Heading1`、`Heading2` 这类样式。

如果是标题:

```python
heading_path = heading_path[: level - 1] + [text]
block_type = "heading"
```

如果是正文段落:

```python
block_type = "paragraph"
block_heading = list(heading_path)
```

含义:

- 标题会更新当前章节路径。
- 正文段落会继承当前章节路径。

例子:

```text
1. 项目介绍
这是第一段。
```

会变成:

```json
{"text": "项目介绍", "block_type": "heading", "heading_path": []}
{"text": "这是第一段。", "block_type": "paragraph", "heading_path": ["项目介绍"]}
```

### 5.3 XLSX 解析

代码使用:

```python
from openpyxl import load_workbook
wb = load_workbook(path, read_only=True, data_only=True)
```

基础概念:

- `openpyxl` 是 Python 里读写 Excel 的常用库。
- `read_only=True`: 节省内存。
- `data_only=True`: 如果单元格是公式,尽量读公式计算后的缓存值。

处理逻辑:

```python
headers = [_cell_to_text(value) for value in rows[0]]
for row_index, row in enumerate(rows[1:], start=2):
```

含义:

- 第一行当表头。
- 后面每一行变成一个 `table_row` block。

例子:

```text
Risk | Owner
Parser drift | Candidate
```

会变成:

```text
Risk: Parser drift; Owner: Candidate
```

并保存:

```json
{
  "locator": {"sheet": "Risks", "row": 2},
  "metadata": {"headers": ["Risk", "Owner"]}
}
```

为什么这样做?

表格如果只保存值,容易丢上下文。比如 `Parser drift` 本身不知道是哪一列。加上 header 后,每个 chunk 单独拿出来也能看懂。

### 5.4 PDF 解析

代码使用:

```python
from pypdf import PdfReader
reader = PdfReader(str(path))
for page_index, page in enumerate(reader.pages, start=1):
    text = (page.extract_text() or "").strip()
```

含义:

- 用 `pypdf` 读取 PDF。
- 按页提取文字。
- 每一页变成一个 `DocumentBlock`。

限制:

- 只适合“可复制文字”的 PDF。
- 扫描图片版 PDF 需要 OCR,当前没有做。

---

## 6. 分块: `doc-chunker/src/doc_chunker/chunker.py`

文件: `doc-chunker/src/doc_chunker/chunker.py`

核心入口:

```python
def chunk_blocks(
    blocks: list[DocumentBlock],
    *,
    doc_id: str,
    config: ChunkingConfig | None = None,
) -> list[Chunk]:
```

输入:

- `blocks`: parser 解析出来的 `DocumentBlock`。
- `doc_id`: 文档 ID。
- `config`: 分块配置。

输出:

- `list[Chunk]`。

### 6.1 分块配置

```python
@dataclass(frozen=True)
class ChunkingConfig:
    max_chars: int = 1000
    overlap_chars: int = 150
```

含义:

- `max_chars`: 一个 chunk 目标最大字符数。
- `overlap_chars`: 相邻 chunk 保留多少重叠文本。

为什么要 overlap?

假设原文:

```text
第一段介绍背景。第二段说明核心原因。第三段给出结论。
```

如果硬切在第二段附近,检索命中第二段时可能缺前后背景。overlap 能让相邻 chunk 有一点重复内容,减少语义断裂。

### 6.2 主循环怎么工作

核心变量:

```python
chunks: list[Chunk] = []
buffer: list[DocumentBlock] = []
buffer_text = ""
```

你可以把 `buffer` 理解成一个临时篮子:

- 每次拿一个 block。
- 如果加进去还没超过 `max_chars`,继续放。
- 如果快超过了,就把篮子里的内容变成一个 chunk。

这个动作叫 `flush()`:

```python
def flush() -> None:
    if not buffer_text.strip():
        ...
    _append_chunk(chunks, doc_id, buffer, buffer_text.strip())
```

### 6.3 如果单个 block 太长怎么办

```python
if len(text) > cfg.max_chars:
    flush()
    for part in _split_text(text, cfg.max_chars, cfg.overlap_chars):
```

含义:

- 如果一个段落/一页本身就太长,不能直接塞进一个 chunk。
- 先把前面的 buffer 存掉。
- 再用 `_split_text()` 切这个长文本。

`_split_text()` 使用正则:

```python
re.split(r"(?<=[.!?。！？])\s+", text)
```

意思是:

- 优先按句号、问号、感叹号后面的空白切。
- 同时兼容英文标点和中文标点。

这是一个轻量分句器。

不是最先进,但可解释、可测试、依赖少。

### 6.4 如果一句话自己就超长怎么办

```python
_hard_split(sentence, max_chars, overlap_chars)
```

这就是兜底硬切:

- 每 `max_chars` 切一段。
- 下一段从 `end - overlap_chars` 开始。

为什么需要兜底?

现实里可能有超长表格值、URL、没有标点的文本。没有兜底就可能生成过大的 chunk。

### 6.5 生成 chunk

```python
chunk_id = f"{doc_id}:{len(chunks) + 1:04d}"
```

例子:

```text
example-9629550649:0001
example-9629550649:0002
```

这表示:

- 来自同一个文档。
- 第 1 个、第 2 个 chunk。

`_append_chunk()` 会把第一个 block 的 `source_file`、`locator`、`heading_path` 放到 chunk 上。

`metadata` 记录:

```python
metadata={"block_types": block_types, "block_count": len(blocks)}
```

含义:

- 这个 chunk 是由哪些类型的 block 合并来的。
- 合并了几个 block。

### 6.6 链接前后 chunk

```python
prev_chunk_id=chunks[i - 1].chunk_id if i > 0 else None
next_chunk_id=chunks[i + 1].chunk_id if i + 1 < len(chunks) else None
```

这一步在 `_link_chunks()` 里做。

结果:

```json
{
  "chunk_id": "doc:0002",
  "prev_chunk_id": "doc:0001",
  "next_chunk_id": "doc:0003"
}
```

这是上下文感知的重要证据。

---

## 7. 存储: `doc-chunker/src/doc_chunker/store.py`

文件: `doc-chunker/src/doc_chunker/store.py`

核心类:

```python
class DocumentStore:
```

它负责把 chunk 写到磁盘,并能搜索。

### 7.1 存储目录

```python
self.manifest_path = self.root / "manifest.json"
self.chunks_path = self.root / "chunks.jsonl"
```

一个 store 目录里有两个文件:

```text
doc-chunker/.doc_index/
  manifest.json
  chunks.jsonl
```

### 7.2 `doc-chunker/.doc_index/manifest.json`

它是文档级摘要:

```json
{
  "version": 1,
  "chunk_count": 2,
  "doc_id": "...",
  "source_file": "...",
  "parser": "txt",
  "chunking": {
    "max_chars": 160,
    "overlap_chars": 20
  }
}
```

作用:

- 快速知道这个索引里有什么。
- 面试 demo 时方便检查。
- 后续如果扩展版本、SQLite、embedding,这里可以记录更多元数据。

### 7.3 `doc-chunker/.doc_index/chunks.jsonl`

JSONL 是 JSON Lines 的缩写。

普通 JSON:

```json
[
  {"a": 1},
  {"a": 2}
]
```

JSONL:

```json
{"a": 1}
{"a": 2}
```

也就是“一行一个 JSON 对象”。

为什么用 JSONL?

- 人可以直接打开看。
- 逐行读写简单。
- 大文件时比整个 JSON 数组更容易流式处理。
- 面试中比 SQLite 更容易展示。

### 7.4 写入逻辑

```python
existing = [chunk for chunk in self.load_chunks() if chunk.doc_id != doc_id]
all_chunks = existing + chunks
```

含义:

- 如果 store 里已经有同一个文档的旧 chunks,先删掉旧的。
- 再写入新 chunks。

这叫**全量替换**。

为什么不做增量更新?

第一版为了简单。增量更新要判断哪些段落改了、哪些 chunk 还稳定,复杂很多。全量替换更适合 48 小时闭环。

### 7.5 搜索逻辑

```python
needle = query.strip().lower()
...
if needle in haystack or all(token in haystack for token in needle.split()):
```

含义:

- 转小写。
- 如果完整 query 出现在 chunk 里,命中。
- 或者 query 拆成词后,每个词都在 chunk 里,也命中。

这不是语义搜索,只是关键词搜索。

为什么这样做?

题目不要求 embedding 和向量数据库。第一版只需要证明“chunk 能被检索出来,并带上下文返回”。

关键词匹配的弱点是"换个说法就找不到"（问"带薪休假"，chunk 里写的是"年假"，就匹配不上）；embedding 的强项恰恰是能理解这种同义表达。所以成熟系统往往两个都用（即混合检索）

---

## 8. 流水线: `doc-chunker/src/doc_chunker/pipeline.py`

文件: `doc-chunker/src/doc_chunker/pipeline.py`

核心函数:

```python
def ingest_document(path, *, store_dir, max_chars=1000, overlap_chars=150)
```

它把前面所有步骤串起来:

```python
file_path = Path(path)
if not file_path.exists():
    raise FileNotFoundError(...)
blocks = parse_document(file_path)
doc_id = _doc_id(file_path)
config = ChunkingConfig(...)
chunks = chunk_blocks(blocks, doc_id=doc_id, config=config)
store = DocumentStore(store_dir)
manifest = store.write_document(...)
return {"ok": True, ...}
```

也就是:

```text
检查文件存在
  -> 解析文档
  -> 生成 doc_id
  -> 分块
  -> 写入 store
  -> 返回 JSON 友好的结果
```

### 8.1 `doc_id` 怎么生成

```python
resolved = str(path.resolve()).encode("utf-8")
digest = hashlib.sha1(resolved).hexdigest()[:10]
stem = ...
return f"{stem}-{digest}"
```

含义:

- 用文件绝对路径做 hash。
- 取前 10 位。
- 加上文件名 stem。

例子:

```text
example-9629550649
```

为什么这样做?

- 同一路径每次导入得到同一个 `doc_id`。
- 不同路径不容易冲突。
- 文件名保留在 ID 里,人还能看懂。

注意:

这里用的是 SHA1。不是为了安全加密,只是为了生成短 ID。安全加密场景现在一般不推荐 SHA1,但这里不是密码/签名用途,风险不一样。

### 8.2 overlap 参数修正

```python
if overlap_chars >= max_chars:
    overlap_chars = max(0, max_chars // 5)
```

为什么有这段?

测试发现,如果用户把 `max_chars` 调得很小,默认 `overlap_chars=150` 可能比 `max_chars` 还大。这样配置非法。

所以这里自动收敛到合法值。

这是一个通过测试发现并修正的真实问题,可以在面试里说。

---

## 9. 命令行入口: `doc-chunker/src/doc_chunker/cli.py`

文件: `doc-chunker/src/doc_chunker/cli.py`

它让你能在 PowerShell 里直接用这个工具。

### 9.1 `argparse`

```python
parser = argparse.ArgumentParser(prog="doc-chunker")
sub = parser.add_subparsers(dest="command", required=True)
```

基础概念:

- `argparse` 是 Python 标准库,用来解析命令行参数。
- subcommand 是子命令,比如 `git add`、`git commit` 里的 `add`/`commit`。

这里有两个子命令:

```text
doc-chunker ingest ...
doc-chunker search ...
```

### 9.2 ingest 命令

```python
ingest.add_argument("path")
ingest.add_argument("--out", required=True, dest="store_dir")
ingest.add_argument("--max-chars", type=int, default=1000)
ingest.add_argument("--overlap-chars", type=int, default=150)
```

对应命令:

```powershell
python -m doc_chunker.cli ingest samples\example.txt --out .doc_index --max-chars 160 --overlap-chars 20
```

### 9.3 search 命令

```python
search.add_argument("store_dir")
search.add_argument("query")
search.add_argument("--limit", type=int, default=5)
```

对应命令:

```powershell
python -m doc_chunker.cli search .doc_index "chunker validation"
```

### 9.4 为什么 CLI 有价值

因为 CLI 不依赖 nanobot 和 LLM。

如果 CLI 都跑不通,说明核心模块有问题。

如果 CLI 跑通,WebUI 不跑,问题多半在安装、entry_points、nanobot 配置或模型是否调用工具。

所以 CLI 是定位问题的第一层。

---

## 10. nanobot 适配层: `doc-chunker/src/doc_chunker/nanobot_tool.py`

文件: `doc-chunker/src/doc_chunker/nanobot_tool.py`

这个文件的作用:

> 把我们的核心功能包装成 nanobot 能认识的 Tool。

### 10.1 导入 nanobot Tool

```python
try:
    from nanobot.agent.tools.base import Tool, ToolResult
except Exception:
    class Tool:
        pass
```

为什么有 try/except?

因为我们希望核心包即使不在 nanobot 环境里也能 import。

- 在 nanobot 环境里:使用真正的 `Tool` 和 `ToolResult`。
- 不在 nanobot 环境里:提供一个假的 fallback,避免 import 整个包时报错。

### 10.2 Tool 名字

```python
def name(self) -> str:
    return "document_chunker"
```

这就是 agent 要调用的工具名。

WebUI 里你可以提示:

```text
请使用 document_chunker 工具...
```

### 10.3 Tool 描述

```python
def description(self) -> str:
    return "Parse documents, create context-aware chunks, store them locally, and search stored chunks."
```

这段描述会进入工具 schema,让 LLM 知道这个工具能干什么。

### 10.4 Tool 参数 schema

```python
"properties": {
    "action": {"type": "string", "enum": ["ingest", "search"]},
    "store_dir": {"type": "string"},
    "path": {"type": "string"},
    "query": {"type": "string"},
    "max_chars": {"type": "integer", "minimum": 80, "default": 1000},
    "overlap_chars": {"type": "integer", "minimum": 0, "default": 150},
    "limit": {"type": "integer", "minimum": 1, "default": 5},
},
"required": ["action", "store_dir"],
"additionalProperties": False,
```

基础概念: **JSON Schema**

JSON Schema 是描述 JSON 参数长什么样的规范。

这里它告诉 nanobot/LLM:

- `action` 必须是 `"ingest"` 或 `"search"`。
- `store_dir` 必填。
- `path` 是 ingest 时用的。
- `query` 是 search 时用的。
- 不允许乱传额外参数。

### 10.5 execute()

```python
async def execute(self, **kwargs: Any) -> Any:
```

为什么是 `async`?

nanobot 的 Tool 接口要求 `execute` 是异步函数。异步函数可以被 agent loop 用 `await` 调用,方便并发和长任务管理。

里面分两种 action:

```python
if action == "ingest":
    payload = ingest_document(...)
elif action == "search":
    payload = {"ok": True, "matches": DocumentStore(...).search(...)}
```

错误处理:

```python
except Exception as exc:
    return ToolResult.error(str(exc))
```

为什么不用直接 `raise`?

nanobot 约定工具失败最好返回 `ToolResult.error(...)`,这样 agent 能收到结构化错误,而不是整个程序崩掉。

---

## 11. nanobot 本身怎么加载和调用这个工具

这里看 nanobot 源码里的三个文件。

### 11.1 Tool 基类: `nanobot/nanobot/agent/tools/base.py`

nanobot 要求每个 Tool 至少提供:

```python
@property
def name(self) -> str

@property
def description(self) -> str

@property
def parameters(self) -> dict[str, Any]

async def execute(self, **kwargs: Any) -> Any
```

我们的 `DocumentChunkerTool` 正好实现了这些。

`Tool.to_schema()` 会把 Tool 转成 OpenAI function/tool schema:

```python
return {
    "type": "function",
    "function": {
        "name": self.name,
        "description": self.description,
        "parameters": self.parameters,
    },
}
```

基础概念:

LLM 不会直接读 Python 类。agent 会把工具描述成 schema 发给模型。模型看到工具名、描述、参数结构,再决定要不要调用。

### 11.2 ToolLoader: `nanobot/nanobot/agent/tools/loader.py`

核心:

```python
eps = entry_points(group="nanobot.tools")
```

这行会读取所有已安装 Python 包里的 `nanobot.tools` entry points。

我们的 `doc-chunker/pyproject.toml` 正好声明:

```toml
[project.entry-points."nanobot.tools"]
document_chunker = "doc_chunker.nanobot_tool:DocumentChunkerTool"
```

所以安装后,ToolLoader 能发现它。

加载后会检查:

```python
isinstance(cls, type)
issubclass(cls, Tool)
not getattr(cls, "__abstractmethods__", None)
getattr(cls, "_plugin_discoverable", True)
```

意思:

- 它必须是类。
- 它必须继承 nanobot 的 Tool。
- 它不能还是抽象类。
- 它必须允许被插件发现。

然后:

```python
tool = tool_cls.create(ctx)
registry.register(tool)
```

这就把工具注册进 nanobot 的 `ToolRegistry`。

### 11.3 ToolRegistry: `nanobot/nanobot/agent/tools/registry.py`

这个类负责:

- 保存所有工具。
- 根据名字找到工具。
- 校验参数。
- 执行工具。

调用前:

```python
tool, params, error = self.prepare_call(name, params)
```

`prepare_call()` 会:

1. 检查工具名是否存在。
2. 把参数从字符串/JSON 转成 dict。
3. 按 `parameters` schema 做类型转换。
4. 校验 required、enum、minimum、additionalProperties。

执行:

```python
result = await tool.execute(**params)
```

所以 WebUI 调用链路是:

```text
LLM 决定调用 document_chunker
  -> ToolRegistry.prepare_call()
  -> DocumentChunkerTool.execute()
  -> ingest_document() / search()
  -> 返回 JSON 字符串
```

---

## 12. 如何在 nanobot WebUI 里真的用

先安装:

```powershell
cd D:\Lenovo\nanobot
python -m pip install -e .
python -m pip install -e ..\doc-chunker
```

验证 entry point:

```powershell
python -c "from importlib.metadata import entry_points; print([ep.name for ep in entry_points(group='nanobot.tools')])"
```

应该看到:

```text
['document_chunker']
```

启动:

```powershell
nanobot webui
```

在 WebUI 输入:

```text
请使用 document_chunker 工具导入 D:\Lenovo\doc-chunker\samples\example.txt,
store_dir 使用 D:\Lenovo\doc-chunker\.ui_index,
max_chars=160, overlap_chars=20。
```

然后输入:

```text
请使用 document_chunker 工具在 D:\Lenovo\doc-chunker\.ui_index 里搜索 "chunker validation",
展示匹配 chunk 的 text、locator、prev_chunk_id、next_chunk_id。
```

如果 agent 没有调用工具,你可以更直接:

```text
调用工具 document_chunker,参数:
action="ingest",
store_dir="D:\Lenovo\doc-chunker\.ui_index",
path="D:\Lenovo\doc-chunker\samples\example.txt",
max_chars=160,
overlap_chars=20。
```

---

## 13. 为什么不直接用 Docling / Unstructured

你需要能回答这个问题。

### 13.1 它们是什么

**Unstructured**

官方文档的思路是先 partition 文档,把原始文件拆成 `Title`、`NarrativeText`、`ListItem` 等元素;然后 chunking 基于这些 document elements 进行,只有单个元素太大时才做文本切分。

这和我们的项目思路非常像:

```text
DocumentBlock 约等于轻量版 document element
chunk_blocks() 约等于轻量版 element-based chunking
```

**Docling**

Docling 的路线更完整。它能把多种文档转成统一的 `DoclingDocument`,并且提供原生 chunker,包括 hierarchical chunker、hybrid chunker、line-based token chunker。Docling 的 hybrid chunker 会先基于文档结构做层级切分,再结合 tokenizer 做 split/merge。

这也和我们的方向一致:

```text
先保结构 -> 再分块 -> 保留 metadata
```

### 13.2 它们更新、更强在哪里

截至 2026 年,更成熟/更“新”的路线通常包括:

1. **结构化解析**: 不只是提取纯文本,而是提取标题、段落、表格、图片、页码、层级。
2. **布局理解**: 对 PDF 版面、表格结构、跨页表格更强。
3. **OCR / VLM**: 对扫描件、图片型 PDF 使用 OCR 或视觉模型。
4. **token-aware chunking**: 按模型 tokenizer 控制 chunk 大小,不是简单按字符数。
5. **hierarchical / hybrid chunking**: 先尊重文档结构,再处理过大/过小 chunk。
6. **table header repetition**: 表格跨 chunk 时重复表头,保证每个 chunk 自洽。

这些能力 Docling/Unstructured 比我们当前版本完整得多。

### 13.3 为什么第一版不用

因为这个 take-home 考察的是:

- 设计边界。
- 上下文感知分块思路。
- nanobot 集成方式。
- 验证方法论。

如果第一版直接接 Docling/Unstructured,风险是:

- 依赖更重,安装和环境问题更多。
- 面试时你不一定能讲清楚内部怎么分块。
- 重点会变成“我调了一个库”,而不是“我设计了模块边界”。

所以第一版选择轻量实现,但把 parser 层隔离出来。未来可以替换:

```text
parse_document()
  当前: pypdf/openpyxl/docx XML
  未来: Docling/Unstructured

chunker/store/nanobot_tool 基本不需要大改
```

面试回答:

> 我知道 Docling 和 Unstructured 是更成熟的文档解析方案,尤其适合生产级 PDF layout、OCR 和复杂表格。但第一版为了 48 小时内做出可解释、可测试的小闭环,我保留了 parser 层接口,用轻量依赖实现。后续要升级时,只需要替换 `parse_document()` 的内部实现,不需要推翻 chunker、store 和 nanobot Tool adapter。

---

## 14. 这个项目用的方法是“什么时候的”,最新方法是什么

这个问题要分层回答。

### 14.1 Python entry points

我们用的:

```python
importlib.metadata.entry_points(group="nanobot.tools")
```

这是现代 Python 打包插件发现方式。Python Packaging User Guide 说明 entry points 用于已安装包向其他代码暴露组件,应用可以用它加载插件。

这个机制的规范最早在 2017 年左右 formalize,到 2026 年仍然是 Python 生态中常见插件机制。

### 14.2 文档解析

我们用的:

- `pypdf`: PDF 文本提取。
- `openpyxl`: Excel 提取。
- zip/XML: DOCX 段落和标题提取。

这是轻量、传统、可解释的方法。

更新/更强的方法:

- Docling: 统一文档表示、layout/table 识别、OCR/VLM、原生 chunker。
- Unstructured: partition 成语义元素,再基于元素 chunk。
- MinerU、Marker、OCR/VLM pipelines: 更关注复杂 PDF 转 Markdown/结构化文本。

### 14.3 chunking

我们用的:

- block-based merge。
- max chars 控制大小。
- sentence boundary split。
- overlap。
- prev/next links。

这是经典 RAG chunking 里的基础做法。

更新/更强的方法:

- token-aware chunking: 用 embedding/generation 模型的 tokenizer 控制 token 数。
- hierarchical chunking: 按标题/章节/表格结构切。
- hybrid chunking: 先按结构切,再按 token split/merge。
- adaptive chunking: 根据文档类型和质量指标选择不同策略。

我们的实现是这些思想的轻量教学版。

### 14.4 存储和检索

我们用的:

- JSONL。
- 关键词包含搜索。

这是 demo 和小规模验证适合的方法。

更新/更强的方法:

- SQLite FTS / BM25。
- 向量数据库,如 Milvus、Qdrant、Weaviate、FAISS。
- hybrid retrieval: BM25 + embedding。
- reranking: 用 reranker 对候选 chunk 排序。

为什么现在不用?

题目明确不要求向量数据库和 embedding 训练。第一版要先证明模块边界和数据契约。

---

## 15. 运行效果怎么看

### 15.1 CLI 看核心效果

```powershell
cd D:\Lenovo\doc-chunker
$env:PYTHONPATH="src"
python -m doc_chunker.cli ingest samples\example.txt --out .doc_index --max-chars 160 --overlap-chars 20
python -m doc_chunker.cli search .doc_index "chunker validation"
Get-Content .doc_index\chunks.jsonl
```

看三个点:

1. `ok=true`: 说明运行成功。
2. `chunk_count`: 说明切了几个 chunk。
3. `doc-chunker/.doc_index/chunks.jsonl`: 看 `text`、`locator`、`prev_chunk_id`、`next_chunk_id`。

### 15.2 WebUI 看集成效果

WebUI 不是直接展示分块按钮,而是 agent 调用 Tool。

你看的是:

1. agent 是否能调用 `document_chunker`。
2. 是否生成 `nanobot/.ui_index/manifest.json` 和 `nanobot/.ui_index/chunks.jsonl`。
3. search 是否能返回 chunk。

如果 WebUI 没调用工具,先用 entry point 验证:

```powershell
python -c "from importlib.metadata import entry_points; print([ep.name for ep in entry_points(group='nanobot.tools')])"
```

如果没有 `document_chunker`,就是没安装到同一个 Python 环境。

---

## 16. 测试文件在证明什么

### 16.1 `doc-chunker/tests/test_chunker.py`

证明:

- chunk 保留 heading metadata。
- chunk 有 prev/next 链接。
- 长文本会拆分。
- overlap 生效。

### 16.2 `doc-chunker/tests/test_parsers.py`

证明:

- DOCX 能识别标题和段落。
- XLSX 能识别 sheet、row、headers。
- PDF 能提取 page text。

### 16.3 `doc-chunker/tests/test_store.py`

证明:

- chunks 能写入 JSONL。
- 能从 JSONL 读回同样的对象。
- search 能返回匹配 chunk。

### 16.4 `doc-chunker/tests/test_cli_and_tool.py`

证明:

- CLI ingest/search 能跑。
- `DocumentChunkerTool` 的 schema 和 execute 合约符合 nanobot 期望。

这组测试不是为了覆盖所有真实文档,而是证明核心契约没断。

---

## 17. 你应该怎么读代码

不要从 nanobot 全仓库开始读。按这个顺序:

1. `doc-chunker/src/doc_chunker/models.py`: 先理解数据长什么样。
2. `doc-chunker/src/doc_chunker/parsers.py`: 看不同文件如何统一成 `DocumentBlock`。
3. `doc-chunker/src/doc_chunker/chunker.py`: 看 block 如何变成 `Chunk`。
4. `doc-chunker/src/doc_chunker/store.py`: 看 chunk 如何落盘和检索。
5. `doc-chunker/src/doc_chunker/pipeline.py`: 看主流程怎么串起来。
6. `doc-chunker/src/doc_chunker/cli.py`: 看命令行怎么调用主流程。
7. `doc-chunker/src/doc_chunker/nanobot_tool.py`: 看怎么包装成 nanobot Tool。
8. `doc-chunker/pyproject.toml`: 看 entry_points 怎么声明。
9. `nanobot/nanobot/agent/tools/base.py`: 看 Tool 接口。
10. `nanobot/nanobot/agent/tools/loader.py`: 看插件发现。
11. `nanobot/nanobot/agent/tools/registry.py`: 看参数校验和执行。

读的时候每个文件只问三个问题:

1. 输入是什么?
2. 输出是什么?
3. 它为什么存在,不放在别的文件里?

---

## 18. 面试时最重要的解释

你不要说:

> 我用了 pypdf/openpyxl 写了一个 chunker。

你要说:

> 我把系统拆成 parser、chunker、store、CLI、nanobot adapter 五层。parser 把不同文档统一成 `DocumentBlock`;chunker 只处理统一结构,生成带上下文的 `Chunk`;store 用 JSONL 保存可检查结果;CLI 做模块级验证;nanobot adapter 做系统级集成。这种边界让第一版简单,同时未来可以把 parser 换成 Docling/Unstructured,把 store 换成 SQLite/向量库,而不推翻整体设计。

这句话是整个项目的灵魂。

---

## 19. 官方资料来源

- Python Packaging User Guide: Entry points specification  
  https://packaging.python.org/en/latest/specifications/entry-points/
- Docling documentation: Supported formats and chunking concepts  
  https://docling-project.github.io/docling/usage/supported_formats/  
  https://docling-project.github.io/docling/concepts/chunking/
- Unstructured documentation: Partitioning and chunking  
  https://docs.unstructured.io/open-source/core-functionality/partitioning  
  https://docs.unstructured.io/open-source/core-functionality/chunking
