# 面试检查清单

## 开场前确认

- [ ] `README.md` 能说明怎么运行。
- [ ] `DESIGN.md` 能说明架构、取舍、假设(Assumptions 一节)和一周/更长期规划。
- [ ] `TESTING.md` 有最新验证结果,以及"自动化判断 vs 人工判断"那张表。
- [ ] `AI_WORKFLOW.md` 有 AI 协作、错误修正记录。
- [ ] `DECISIONS.md` D008/D009 能讲清楚"做过又删掉"的四项功能和原因。
- [ ] `INTERVIEW_SCRIPT.md` 已读熟,不要逐字背。

## 必讲三句话

1. "我没有把它做成完整 RAG,因为题目重点是上下文感知分块和模块集成。"
2. "核心库不依赖 nanobot,nanobot 只是一个薄 Tool adapter,而且我实际验证过 entry_points 发现路径。"
3. "命中搜索后能用 `expand=neighbors`/`expand=section` 恢复上下文,不只是存了 prev/next 和 heading_path 却没人用。"

## 必演示三个证据

1. `python -m pytest tests -q` 的 `31 passed`。
2. `search ... --expand section` 前后输出对比,展示 `chunks.jsonl` 里的 `heading_path`/`prev_chunk_id`/`next_chunk_id` 是怎么被用来恢复上下文的。
3. `pyproject.toml` 里的 `[project.entry-points."nanobot.tools"]`,配上"我跑过 `pip install -e .` 验证过"这句话。

## 容易被问倒的点

- PDF 扫描件不能处理:回答 OCR out of scope。
- search 不是语义检索:回答确定性关键词是验证链路的选择,语义检索留在更长期规划里,不是没考虑过。
- 为什么没有第二个存储后端/可插拔分块策略/完整性校验/Skill 文件:回答"做过,后来对照完整原文核对发现找不到依据,删了"——见 `DECISIONS.md` D008/D009,这是加分项,不是漏项。
- Word 表格复杂结构:回答当前保留 schema 扩展空间,重点覆盖 DOCX 段落/标题和 Excel 表格。
- 重复导入同一文档会不会重复处理:回答会,当前是全量替换策略,没做变更检测(有意的取舍,`DESIGN.md` Known Limits 里写明)。

## 30 秒收尾

这个版本的价值是一个可运行、可检查、可扩展的小闭环:解析三类主流文档,保留上下文分块并能在命中后恢复上下文,本地存储可查,nanobot 有正式 Tool 接口,测试和 AI 使用记录能证明开发过程可验证——而且我对照完整需求原文做过一轮"删掉自己多做的东西",证明功能边界是主动划定的,不是堆出来的。
