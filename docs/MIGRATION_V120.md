# V1.2.0 人机协同使用与迁移

## 本地资料工作台

Python 3.10+，依赖 requirements.txt；ffprobe/ffmpeg 用于已有素材预检/测试。显式列出已获授权的相对文件名，命令不会上传文件。

```bash
python scripts/human_review.py intake --base-dir materials brief.pptx report.pdf results.xlsx > intake.json
```

输出 files（可读状态、哈希）和 candidates（原始片段、定位、相邻上下文、提示、稳定ID）。最多每文件2000个片段，每片段20000字符，超限标记 PARTIAL；图像、图表、扫描件、嵌套元素及布局不保证提取。PDF页、DOCX段落/表行、PPTX幻灯片文本/表、XLSX行、TXT/MD/CSV/JSONL行支持有限文本提取。公式保留表达式，不作为实际结果。候选是待处理内容，不是结构化指标自动认证。

将单个完整 candidate 对象从 intake.json 保存为 candidate.json（不要改动）。实际查看原件后由人执行：

```bash
python scripts/human_review.py review --base-dir materials --candidate candidate.json --reviewer '项目负责人' --decision ACCEPT_FOR_DRAFT --note '与原件逐项核对，仍待确认数据提供者' --interpretation '销售额记录待核验' > note.json
```

可选 REJECT/NEEDS_EVIDENCE。带警示的片段不可直接接受；原件变化或候选篡改会拒绝。将 note.json 作为对象附入 case.review_notes 列表可再次校验。意见不受可信签名保护，reviewer 是自报标签，不证明身份/权限。草稿可以引用候选与原件定位，不能自动提升为 FACT 或绕过 V1.1.1 的确定性源记录规则。复杂资料仍需真实人工完成最终语义确认。

## 目标与结果

保留 V1.1.1 case 结构；增加可选目标字段 target、direction（AT_LEAST/AT_MOST）、unit、scope、period、set_date（ISO日期）、target_source（file、sha256、locator、quote）。本地比较采用保守的显式原文表达，如“示例品牌2025销售额目标至少110元，2024-12-01设定”。目标和成果独立；未达标不隐瞒、不等于自动拒绝投报。无法核对方向/时间/口径等返回 GOAL_REVIEW。年、ISO日、ISO日/ISO日范围支持时间比较；延迟成果需单独人工归因。非自动判定营销贡献。

## 审阅稿成品回查

```bash
python scripts/human_review.py export-review --case case.json --out materials/review.docx
python scripts/human_review.py compare --case case.json --base-dir materials --file review.docx
```

仅支持本工具生成的 `[字段ID] 原文` DOCX审阅稿（非官方报名表）。逐段精确比较全部字段；不允许附加段落、表格、图像、修订、字段、超链接及部分其他辅助内容。将 file/sha256 登记为 case.final_review_file，最终预检重复核验。版式、图表、复杂任意成品、匿名性和真实官方表单仍需人工审核。

## 多维预检

```bash
python scripts/validate_submission.py --case case.json --award EFFIE_GC_MAIN --base-dir materials --json
```

保留原11道本地门禁；新增原件上下文警示扫描、精确同口径记录冲突、异常标签、成果期间、目标来源/完成度、结果正文覆盖、重复字段及授权重复。`technical_status` 与 `dimensions` 分离。BLOCKED 表示阻断；NEEDS_EVIDENCE 表示缺证；HUMAN_REVIEW_REQUIRED 不是准备提交，也可能存在非阻断人工缺口。CLI 不签发成功退出码；旧集成应读取 JSON，而不是自动执行。`technical_preflight` 是仅用于历史工程诊断的内部函数，不得作为最终门禁。所有状态 submission_authorized=false。

上下文是关键词警示，不是通用语义蕴含；同口径冲突以规范化字符串及数值匹配，不能发现所有别名/单位换算/组合误导。人工复核必须检查所有原件、目标真实性、组合主张、战略与创意、归因、公开权限、真实签署、官方原文及最终提交材料。独立真实专业盲测未执行。
