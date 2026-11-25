# 工作流：案例资料理解与事实提取（case-intake）

**对应模块**：M01　**触发**：用户提供 Brief / 报告 / 数据 / 素材，要求整理或开始报奖

## 目标

把零散材料变成结构化 Case Profile，并**明确区分事实与缺口**。这一步做不好，后面全是虚构。

## 步骤

### 1. 清点材料

对每份材料记录：

```
文件名 | 类型 | 日期 | 提供方 | 是否原始数据 | 可读性
```

可读性分三档：
- `READABLE`：文本可提取
- `IMAGE_ONLY`：扫描件/截图，需人工或 OCR（说明不确定性）
- `UNREADABLE`：无法解析（明确告知，不得假装读过）

### 2. 抽取七类信息

| 类别 | 要抽取什么 | 常见缺失 |
|---|---|---|
| 品牌与生意 | 品牌定位、品类、份额、历史表现 | 份额与品类基准 |
| 挑战 | 商业问题、结构性障碍 | 只有"竞争激烈" |
| 目标 | 商业/营销/战役目标 + KPI + 基准 + 立项时间 | 立项时间戳 |
| 受众 | 人口/行为/媒体/现有vs新 | 行为与媒体画像 |
| 洞察与策略 | 洞察来源、策略内核 | 洞察推导过程 |
| 执行 | 创意、渠道、触点、预算、优化动作 | 渠道选择理由 |
| 成果 | 各层指标、周期、对照、来源 | 品类对照、归因 |

### 3. 六态标注（强制）

每条信息必须打标：

```
[FACT]     有材料支持 → 记 evidence 引用
[CLAIM]    用户声明 → 标"（待证）"
[CALC]     计算得出 → 附公式
[INFERENCE] 专业推断 → 标"推断："
[RECOMMENDATION] 建议 → 标"建议："
[UNKNOWN]  未知 → 进缺口清单
```

**禁止**把 CLAIM 写成 FACT，把 INFERENCE 写成已经发生的事。

### 4. 输出 Case Profile

用 `templates/case-profile.json`。核心字段：

```json
{
  "brand": "", "product": "", "category_numbers": [],
  "implementation_start": "", "implementation_end": "", "region": "GREATER_CHINA",
  "budget_range": "",
  "challenge": {"text": "", "status": "FACT|CLAIM"},
  "goals": [{"type": "business|marketing|campaign", "kpi": "",
             "baseline": "", "target": "", "status": ""}],
  "audience": {"core": "", "extended": "", "status": ""},
  "insight": {"text": "", "source_type": "research|data|analysis|inspiration",
              "status": ""},
  "strategy": {"core": "", "status": ""},
  "execution": {"touchpoints": [], "budget_split": {}, "optimizations": []},
  "results": [{"metric": "", "value": "", "unit": "", "period": "",
               "baseline": "", "status": ""}],
  "evidence": [], "claims": [],
  "gaps": []
}
```

### 5. 生成补充资料清单（按部门分工）

| 需要什么 | 找谁要 | 为什么必须要 |
|---|---|---|
| 品类基准数据 | 客户市场部 / 第三方（欧睿、尼尔森、平台行业报告） | 没有基准，挑战难度不可评估 |
| 立项文件与目标设定时间 | 客户品牌负责人 | 证明目标不是事后倒推 |
| 原始销售/CRM 导出 | 客户数据团队 | 支撑成果数字 |
| 媒介投放明细 | 媒介代理 | 投资概览与触点 |
| 洞察调研原始报告 | 策略部 / 调研公司 | 支撑 2.2 |
| 创意出街物料与授权 | 创意部 / 法务 | 创意材料 + 公开授权 |
| 竞品情报 | 策略部 | 1.1 竞争背景 |

### 6. 交付

- Case Profile（JSON）
- 缺口清单（按部门）
- 一句结论：**目前材料足以支撑到哪个阶段**（诊断 / 类别匹配 / 全稿 / 不可）

## 红线

- 不得替用户"补全"缺失数据
- 不得把"我们觉得"写进 FACT
- 材料读不了就说读不了

## V1.2.0 原件处理优先路径

先按 `docs/MIGRATION_V120.md` 使用 `human_review.py intake` 生成原件候选，保留页/行/段/幻灯片定位、哈希和上下文。对非结构化材料可以基于候选开展草稿咨询、事实待核和补证工作；不要要求客户重新制作原始JSON，也不得将AI转录当作原件。人工意见通过 `review` 保存为仅供草稿的本地记录，并可在 `case.review_notes` 重新校验。来源身份、数据真实性、组合语义始终需要人工复核。未解析图像和公式不得视为已读或已核验。
