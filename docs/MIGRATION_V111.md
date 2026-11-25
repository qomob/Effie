# V1.1.1 输入与运行契约（相对 V1.1.0 有破坏性变更）

V1.1.0 迁移文档移至 `history-v1.1.0/`，基础文件、权限、表单、素材、归因与状态约束仍适用；冲突处以本版为准。仅 2026 继承快照、主奖项通用单类别支持自动预检，所有其他路径仅咨询。不要把本地匹配当作语义或真实性证明。

## 原始证据
- 必须提供实际材料、SHA-256、合法相对路径、原始定位以及**完整定位内容**的引用（空白归一化）。不得只截取有利子句。支持文本 L1/L1-L3，PDF p.1，DOCX paragraph:1，XLSX Sheet1!A1:B2（非公式）。扫描件及无法可靠抽取、复杂页面、表格及自然语言改写须人工处理。
- `evidence[]`：evidence_id、file、sha256、locator、quote、provider、metric、period、scope、status（PENDING_LOCAL_CHECK 或继承 VERIFIED，但重新核验）、confidentiality、publication_cleared。可选 value/unit/baseline/denominator/baseline_period 不得与解析原件冲突。
- 数值记录自动预检优先支持实际来源导出的单条 JSON 记录（如 TXT 中一行），其原文须精确具备以下字段。以下**仅为合成契约示例**，不能将人工或模型转录伪装为原始材料：
```json
{"scope":"示例品牌","period":"2025","metric":"销售额","value":"100","unit":"元","denominator":"全渠道","baseline":"90","baseline_period":"2024","provider":"SYNTHETIC"}
```
- 也支持完整紧凑单条中文事实（如 `示例品牌2025年销售额100元`），但因缺少分母、基线、来源字段，不可单独支撑正式 KPI 门禁。对于非结构化数字、非阿拉伯数字、复杂表格或多指标同句，不能承诺解析或普遍语义验证；保留原件并走人工审查。来源字段、基线和分母是原始记录所载内容，并非对真实性的独立认证。

## 正式主张与草稿
- `claims[]` 仅 FACT/CALC；任何 CLAIM、INFERENCE 或未证假设均留在独立 `draft_hypotheses`，不得绑定 `answers`。不可为通过而改标签或删事实。
- FACT 只绑定唯一证据。数字需 `metric`、`period`、`scope`、`unit`、`value` 对应原始记录；`text` 使用 `integrity.render_fact(record)` 的确定性表达。非数值只允许完整原文且体现声明的主体与期间；仍需人工审查语义。例：`示例品牌，2025，销售额为100元（分母：全渠道；基线：2024 90元）`。
- CALC 仅支持两个不同证据记录的 `difference` 与 `growth_pct`。操作数必须同主体、指标、单位、分母和来源，当前期的基线时间/数值须等于第二条记录。增长率基线须大于零，比例指标差值/增长不自动通过。`calculation.operands` 顺序为当期、基期；`metric` 为原指标+差值/增长率；text 严格为 `主体，当期相对基期，指标差值为数值单位` 或增长率对应文本。精度容差为绝对 0.000001。其他算式转人工，不执行自由公式。
- 所有 `answers` 仍按 `answer_bindings` 逐字段拼接完整登记主张。预检不判断字段业务质量、组合语义或最终上传文件内容；必须人工复核。

## 指标
`goals[].kpi` 为指标名称（目标数值另记，不把目标值塞入名称）。`metrics[]` 除原有 metric_id/goal_id/claim_id/name/value/unit/period/scope/source/denominator 外，必须填写 `baseline`、`baseline_period` 并与原始结构化记录一致。指标名称须与绑定主张及目标 KPI 一致。每个目标必须有对应结果；未达目标不得删减。没有合理基线、不同语言/口径的映射、复杂因果估计等转人工，禁止补造。

## 其他约束
- 资格：开始日期晚于资格截止直接 BLOCKED，即便缺结束日期；其他缺失日期仍待确认。类别未覆盖不借用主奖项；权重未核实不计算。
- 授权：实际文件需解析为非加密、有页面的 PDF 或 DOCX 文档；仍需验证身份、签署、范围与权利。不存在自动签发 READY_TO_SUBMIT 的入口。
- 既有旧版 JSON Schema 只作基础/历史数据结构；完整新约束由运行时检查实现，不宣称已完成全量 Schema 强制迁移。
- 真实商业评审、自由语义蕴含、数据真实性、最终文件反查、正式公开权限及官方规则原件须由人工核查。

## 测试
`python tests/run_all.py --json` 统一入口。测试需 Python 3.10+、requirements.txt、ffmpeg/ffprobe。真实客户材料不能用于未经授权测试。测试正向案例仅验证本地契约可达，不是可报名案例。
