# 学习路径

这是一份复习路线。你不用一次吃完整个项目,按顺序过就能建立理解。

---

## 第一轮: 只理解主流程

目标: 能说出一份文档从输入到输出发生了什么。

读这些文件:

1. `src/doc_chunker/pipeline.py`
2. `src/doc_chunker/parsers.py`
3. `src/doc_chunker/chunker.py`
4. `src/doc_chunker/store.py`

记住这条链路:

```text
ingest_document()
  -> parse_document()
  -> chunk_blocks()
  -> DocumentStore.write_document()
```

你要会说:

> `pipeline.py` 是总导演。它先检查文件,再调用 parser,再调用 chunker,最后调用 store 写入结果。

---

## 第二轮: 理解两个数据结构

读:

```text
src/doc_chunker/models.py
```

记住:

```text
DocumentBlock = 解析阶段的结构块
Chunk = 最终给检索和 nanobot 用的小片段
```

一句话:

> parser 不直接产出最终 chunk,而是先产出统一的 `DocumentBlock`,这样 PDF/Word/Excel 后面都能走同一套 chunker。

---

## 第三轮: 理解两种运行方式

### CLI

```powershell
cd D:\Lenovo\doc-chunker
$env:PYTHONPATH="src"
python -m doc_chunker.cli ingest samples\example.txt --out .doc_index --max-chars 160 --overlap-chars 20
python -m doc_chunker.cli search .doc_index "chunker validation"
```

CLI 证明:

```text
核心模块自己能跑
```

### nanobot WebUI

先安装:

```powershell
cd D:\Lenovo\nanobot
python -m pip install -e .
python -m pip install -e ..\doc-chunker
```

再启动:

```powershell
nanobot webui
```

WebUI 证明:

```text
核心模块能作为 nanobot Tool 被 agent 调用
```

---

## 第四轮: 理解 nanobot 集成

读:

1. `doc-chunker/pyproject.toml`
2. `doc-chunker/src/doc_chunker/nanobot_tool.py`
3. `nanobot/nanobot/agent/tools/base.py`
4. `nanobot/nanobot/agent/tools/loader.py`
5. `nanobot/nanobot/agent/tools/registry.py`

记住三句话:

1. `pyproject.toml` 通过 `nanobot.tools` entry point 声明插件。
2. `ToolLoader` 通过 `entry_points(group="nanobot.tools")` 发现插件。
3. `ToolRegistry` 根据工具名和 JSON Schema 校验参数,然后调用 `execute()`。

---

## 第五轮: 理解为什么这样设计

### 为什么分 parser/chunker/store?

因为职责不同:

- parser: 负责把文件格式读出来。
- chunker: 负责分块策略。
- store: 负责保存和搜索。

如果混在一个文件里,以后换 Docling、换 SQLite、换搜索方式都会互相影响。

### 为什么不用 Docling/Unstructured?

第一版是面试小闭环。轻量实现更容易解释和验证。parser 层已经隔离,以后可以替换成 Docling/Unstructured。

### 为什么不用向量库?

题目说不要求真实向量数据库。第一版用关键词 search 证明数据链路。未来可以加 BM25、SQLite FTS 或 embedding。

### 为什么不用 MCP?

MCP 是另一种远程工具协议,适合跨 client 复用。但第一版用同进程 Tool adapter 更简单,更符合 48 小时交付。

---

## 概念速查

### RAG

Retrieval-Augmented Generation,检索增强生成。先从资料库检索相关片段,再让模型基于片段回答。

### Chunk

长文档切出来的小片段。太大模型不好处理,太小会丢上下文。

### Metadata

附加信息。比如页码、表头、章节路径、来源文件。

### Parser

解析器。负责把文件转成程序能处理的数据结构。

### Store

存储层。负责保存 chunk,并提供读取/搜索。

### JSONL

JSON Lines,一行一个 JSON 对象。适合保存很多条记录。

### Entry Point

Python 包安装后写入的一种元数据。别的程序可以通过它发现插件。

### Tool

nanobot agent 能调用的外部能力。Tool 有名字、描述、参数 schema 和执行函数。

### JSON Schema

描述 JSON 参数格式的规则。比如哪个字段必填、字段是什么类型、能不能传额外字段。

### Adapter

适配层。把一个模块包装成另一个系统能使用的接口。

---

## 你面试前要能手写出的流程

```text
用户上传/指定文档
  -> parser 提取 DocumentBlock
  -> chunker 合并/切分为 Chunk
  -> store 写 manifest.json 和 chunks.jsonl
  -> CLI 或 nanobot Tool 返回结果
  -> search 从 chunks.jsonl 找匹配片段
```

---

## 最小背诵版

> 我这个项目的核心是把复杂文档先统一成 `DocumentBlock`,再分成带上下文的 `Chunk`。上下文包括来源位置、标题路径、前后 chunk 链接和 metadata。核心库不依赖 nanobot,所以可以用 CLI 和 pytest 独立验证。nanobot 集成通过 Python entry_points 暴露 `DocumentChunkerTool`,ToolLoader 发现它后注册到 ToolRegistry,agent 就能在 WebUI 里调用。第一版没用 Docling、Unstructured、向量库和 MCP,是因为 48 小时任务更需要一个可解释、可测试的小闭环;但 parser/store/adapter 的边界已经给后续升级留好了。
