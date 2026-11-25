# Effie Entry Expert · 艾菲奖报名顾问

> **独立第三方报奖辅助工具，非艾菲官方产品。** 不承诺获奖，不代为提交或付款。

懂品牌、懂策略、懂创意、懂数据、懂实效，**并且敢说"这个案例不该报"**的报奖顾问。

## 它解决什么

| 真实痛点 | 它怎么做 |
|---|---|
| 官方规则散在 13 份手册里，容易记错 | 487 条规则结构化，每条带页码原文，可查可引 |
| 大中华区/全球化奖地域口径相反、权重也不同 | 按 `award_id` 分区存储，禁止跨奖项套用 |
| 134 个类别，容易投错 | 类别定义全文 + 22 条特殊资格约束 + 七维匹配流程 |
| 字数超限被系统截断 | 89 字段、60 处限制，精确核算 |
| 数据和结论编造风险 | 证据登记 + 哈希校验 + 主张绑定 + 九项审计 |
| 相关性说成因果被评委识破 | 归因等级判定，越级即 P0 |
| 不合格案例硬要报 | 10 道门禁，状态由脚本算，改不了 |

## 快速开始

```bash
# 查规则（带出处）
python3 scripts/rule_query.py --award EFFIE_GC_MAIN --type scoring_weights

# 查类别
python3 scripts/category_query.py --number 55

# 资格预检
python3 scripts/validate_eligibility.py --case my-case.json --award EFFIE_GC_MAIN

# 提交验收
python3 scripts/validate_submission.py --case my-case.json --award EFFIE_GC_MAIN
```

日常使用只需自然语言："这项目值得报艾菲吗""适合投哪些类别""这些数据能证明有效吗"。

详见 `docs/USER_GUIDE.md`。

## 内容规模

| 项 | 数量 |
|---|---|
| 官方文件读取 | 81 份 / 771 页 PDF / 57.9 万汉字（100% 覆盖） |
| 规则条目 | 487 条（13 奖项；411 条逐字原文带页码，37 条转述已标注，39 条指代性引用） |
| 参赛类别 | 134 个（28 行业 + 106 专项 + 6 赛道），含官方定义全文 + 37 条特殊资格（覆盖 19 类） |
| 参赛表字段 | 89 个（60 处字数限制） |
| 校验脚本 | 13 个 |
| 工作流 | 12 种 |
| 测试 | 72 项（全部真实执行通过）+ 5 个变异测试全部捕获 |

## 核心设计原则

1. **能算的不用猜** — 字数、日期、权重、哈希、状态机全部由代码完成
2. **规则必须带出处** — 查不到就说查不到，不编造
3. **状态不可手改** — `READY_TO_SUBMIT` 只能由校验脚本产出
4. **事实与建议分离** — `FACT/CLAIM/CALC/INFERENCE/RECOMMENDATION/UNKNOWN` 六态标注
5. **相关性不说成因果** — 归因分级，越级即 P0 缺陷

## 当前状态

**BETA**

- ✅ 72 项工程测试全部通过（本地真实执行，证据等级 E2）
- ✅ 引用真实性已核验并**如实分层**：411 条逐字（带页码）/ 37 条转述（标 UNVERIFIED）/ 39 条指代性
- ✅ 5 个变异测试全部捕获（证明测试非恒真）
- ⚠️ 真实宿主触发测试未执行
- ❌ 模型 A/B/C 对照实验未执行（环境限制，已标记 `MODEL_EVALUATION_NOT_EXECUTED`）
- ❌ 真实客户案例验证未执行（全部为合成夹具）

**不宣称"生产就绪"。** 详见 `docs/PRODUCTION_READINESS.md`。

## 已知限制

1. 知识库仅覆盖 **2026** 竞赛年度
2. 主奖项类别完整；6 个专项奖项类目册 PARTIAL，7 个奖项无类别文件
3. 汽车奖官方仅列 8 条取消资格（非九条）
4. 主观判断（洞察是否独到、创意是否打动人）无法用脚本验证
5. `verify_quotes.py` 默认只做包内自检；逐字核验需自备官方语料（`--corpus`）
6. 本工具为独立辅助工具，**不代表艾菲奖组委会**

## 文档

- `docs/DELIVERY_REPORT.md` — 交付报告（全部真实数字）
- `docs/TEST_REPORT.md` — 64 项测试结果
- `docs/ADVERSARIAL_AUDIT.md` — 独立对抗式审计
- `docs/SOURCE_COVERAGE.md` — 81 份官方资料覆盖
- `docs/PRODUCTION_READINESS.md` — 就绪度与限制
- `docs/MODEL_EVALUATION.md` — 模型评估状态
- `docs/USER_GUIDE.md` — 使用指南
- `docs/ARCHITECTURE.md` — 架构与取舍

## 版本

v1.0.1 · 见 `CHANGELOG.md`

## 授权

见 `LICENSE` 与 `THIRD_PARTY_NOTICES.md`。官方规则的知识产权归艾菲奖组委会，
本 Skill 仅以结构化摘要 + 来源索引方式引用，不随包分发官方原件。
