# Interview Checklist

## 开场前确认

- [ ] `README.md` 能说明怎么运行。
- [ ] `DESIGN.md` 能说明架构和取舍。
- [ ] `TESTING.md` 有最新验证结果。
- [ ] `AI_WORKFLOW.md` 有 AI 协作、错误修正、过度设计裁剪记录。
- [ ] `INTERVIEW_SCRIPT.md` 已读熟,不要逐字背。

## 必讲三句话

1. "我没有把它做成完整 RAG,因为题目重点是上下文感知分块和模块集成。"
2. "核心库不依赖 nanobot,nanobot 只是一个薄 Tool adapter。"
3. "我用测试和二次源码核查验证 AI 产出,没有直接相信第一版回答。"

## 必演示三个证据

1. `python -m pytest tests -q` 的 `9 passed`。
2. `chunks.jsonl` 里的 `locator`、`prev_chunk_id`、`next_chunk_id`。
3. `pyproject.toml` 里的 `[project.entry-points."nanobot.tools"]`。

## 容易被问倒的点

- PDF 扫描件不能处理:回答 OCR out of scope。
- search 不是语义检索:回答第一版是确定性关键词验证链路,后续可加 BM25/embedding。
- JSONL 是否够用:回答第一版便于检查和测试,大规模场景加 SQLite 后端。
- Word 表格复杂结构:回答当前保留 schema 扩展空间,第一版重点覆盖 DOCX 段落/标题和 Excel 表格。

## 30 秒收尾

这个版本的价值是一个可运行、可检查、可扩展的小闭环:解析三类主流文档,保留上下文分块,本地存储可查,nanobot 有正式 Tool 接口,并且测试和 AI 使用记录能证明开发过程是可验证的。
