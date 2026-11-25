# 使用指南

## 安装

把 `effie-entry-expert/` 整个目录放到 WorkBuddy 的技能目录：

```
~/.workbuddy/skills/effie-entry-expert/
├── SKILL.md
├── references/
├── scripts/
└── ...
```

或项目级：`{项目}/.workbuddy/skills/effie-entry-expert/`

**依赖**：Python ≥ 3.9，仅标准库，无需 pip 安装。

## 快速开始

直接说需求，不需要记命令：

| 你说 | 它会做 |
|---|---|
| "这个项目值得报艾菲吗" | 案例价值诊断 |
| "这 20 个项目该报哪些" | 年度海选 + 预算建议 |
| "适合投哪些类别" | 类别匹配（七维核验） |
| "帮我写参赛表" | 四支柱全稿 |
| "这是我写好的参赛表，帮我改" | 逐字段修订 + 变更记录 |
| "站评委角度挑毛病" | 六视角独立评审 |
| "这些数据能证明有效吗" | 实效与归因审计 |
| "会不会被取消资格" | 资格校验 |
| "帮我做案例视频脚本" | 分镜 + 旁白 + 合规检查 |
| "项目还没开始，怎么规划" | 证据预埋方案 |
| "材料齐了能不能交" | 10 项门禁验收 |

## 必须先说清的三件事

1. **报哪个奖项**——13 个奖项规则不同（全球化奖要求海外投放、权重也不同）
2. **哪一年**——只支持 2026
3. **投什么类别**——没定类别无法判资格

## 命令行直接调用（进阶）

```bash
cd ~/.workbuddy/skills/effie-entry-expert

# 看有哪些奖项
python3 scripts/rule_query.py --awards

# 查某奖项的评分权重（带出处）
python3 scripts/rule_query.py --award EFFIE_GLOBAL --type scoring_weights

# 查某类别定义与特殊资格
python3 scripts/category_query.py --number 55

# 搜类别
python3 scripts/category_query.py --search 私域

# 查某部分的字段与字数
python3 scripts/field_query.py --part 4

# 字数总览
python3 scripts/field_query.py --summary
```

## 典型流程：从零到可提交

### 第 1 步：确认资格

```bash
# 先建一个最小的案例档案
cat > my-case.json <<'EOF'
{
  "competition_year": 2026,
  "award_id": "EFFIE_GC_MAIN",
  "implementation_start": "2025-03-01",
  "implementation_end": "2025-12-31",
  "region": "GREATER_CHINA",
  "category_numbers": [55]
}
EOF

python3 scripts/validate_eligibility.py --case my-case.json --award EFFIE_GC_MAIN
```

**看到 BLOCKED 就停。** 先解决合规问题，别急着写稿。

### 第 2 步：定类别

```bash
python3 scripts/category_query.py --candidates my-case.json
python3 scripts/category_query.py --number 55    # 逐个查定义
```

召回结果只是候选。要结合类别定义、特殊资格、证据需求判断。

### 第 3 步：整理证据

用 `templates/evidence-register.csv` 登记每个数字的来源。

```bash
python3 scripts/verify_evidence.py --file evidence.json --base-dir ./materials
```

### 第 4 步：写稿

用 `templates/entry-form.md` 作为骨架。每段标注事实等级。

### 第 5 步：核算

```bash
python3 scripts/check_word_limits.py --case my-case.json
python3 scripts/validate_metrics.py --file metrics.json
python3 scripts/audit_attribution.py --file attribution.json
```

### 第 6 步：验收

```bash
python3 scripts/validate_submission.py --case my-case.json --award EFFIE_GC_MAIN
```

只有输出 `READY_TO_SUBMIT` 才是真的准备好了。

## 常见问题

### Q: 为什么它说我的案例不能报？

看 `validate_eligibility.py` 的输出，每条都有官方出处。最常见的三个原因：
1. 实施时间不在 2025-01-01 ~ 2026-06-30
2. 类别投多了（最多 4 个，行业类最多 1 个）
3. 类别特殊资格不符（如小预算超限、挑战者份额≥15%）

### Q: 能不能直接帮我标成"可提交"？

不能。状态由脚本算。这跟你自己的利益一致——被取消资格不退报名费。

### Q: 为什么它老是让我补数据？

艾菲九条取消资格里有一条是"数据没有可追溯的来源"。
没来源的数据写进去，风险是被取消资格，不是扣分。

### Q: 它给的分数能预测获奖吗？

不能。那是内部诊断分，用来看短板在哪，不是预测。

### Q: 全球化奖和其他奖有什么不同？

三处硬差异：
1. 要求**海外**投放（不是大中华区）
2. 权重 15/25/30/30（不是 23.3/23.3/23.3/30）
3. 材料是"案例阐述 PDF + 投放素材"（不是视频+平面）

### Q: 支持 2027 年吗？

不支持。知识库是 2026 快照。问 2027 会明确说"未覆盖"，不会套用 2026 规则。

### Q: 我的数据会不会被上传？

不会。所有脚本都在本地跑，不联网。但注意不要把含客户数据的文件提交到公开仓库。

## 目录说明

| 目录 | 内容 |
|---|---|
| `SKILL.md` | 入口，含任务路由与铁律 |
| `references/` | 规则库、类别库、字段库、专业方法论 |
| `workflows/` | 12 种任务的详细流程 |
| `scripts/` | 13 个校验脚本 |
| `schemas/` | JSON Schema |
| `templates/` | 交付模板 |
| `examples/` | 合成示例 + 走查 |
| `tests/` | 72 项测试 + 5 个变异测试 |
| `docs/` | 架构、覆盖、测试、审计、就绪度 |

## 免责

**本技能为独立营销案例评估与报奖辅助工具，不代表艾菲奖组委会**，
与其无隶属、授权、认证、合作或背书关系。
不承诺获奖，不代为提交或付款。官方规则可能变更，正式提交前请核对官网。
