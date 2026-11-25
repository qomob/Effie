# V1.1 输入迁移（不兼容 V1.0.6 自动提交状态）

保留旧 JSON 字段；下面为新增预检契约。读取 `examples/example-case.json` 时请注意它是旧版不完整的合成演示，不能作为通过样例。实际可运行正例由 `tests/test_integrity_v11.py` 在临时目录构造。

- `competition_year`: 显式整数 2026；`award_id` 必须与命令相同；`category_numbers` 单个有效整数；`form` 通用；起止日期完整；`has_pilot_only` 明确布尔值。
- `evidence[]`: 唯一 evidence_id、相对 file、实际 sha256、locator、quote、provider、metric、period、scope、status (`PENDING_LOCAL_CHECK` 或旧 `VERIFIED`，均需重查)、confidentiality (`low/medium/high/secret`)、publication_cleared 布尔值。原文必须位于指定位置；文本 `L1-L3`，PDF `p.1`，DOCX `paragraph:1`，XLSX `Sheet1!A1:B2`（多个单元格用 ` | ` 拼接）。引用必须是实际抽取字符串，不是模型重写。超100 MiB、外部路径、扫描图片、公式缓存和未知格式阻断。
- `claims[]`: 唯一 claim_id、type（FACT/CALC/CLAIM/INFERENCE）、text、evidence_ids、period、scope。FACT 的文本必须等于一条完整引用；数字声明需 value、unit 且数字在文本中。CALC 还需 `calculation: {"operation":"difference","operands":[{"evidence_id":"E1","value":"100"},{"evidence_id":"E2","value":"50"}]}`，仅允许 difference/sum/ratio/percentage/growth_pct；十进制计算，不执行任意公式。CLAIM/INFERENCE 需 reasoning，语义判断必须人工复核。数值出现并不证明其含义正确。
- `answers`: 官方 field_id → 非占位文本；`answer_bindings`: field_id → 按正文顺序的 claim_id 数组。按空格拼接归一化后须与字段全文完全一致（包括选填字段）。不得只给几个登记主张并额外追加正文。实际最终上传文件仍必须人工反向检查。
- `goals[]`: 唯一 goal_id、kpi、type；`metrics[]`: 唯一 metric_id、goal_id、claim_id、name、value、unit、period、scope、source、denominator；每个目标至少一个绑定成果。保留原 baseline/stated_as 等旧审计字段，不删除未达目标。
- `attribution`: claimed_conclusion A–E、methods、available_data、confounders_addressed、has_parallel_campaigns、section_4_2_text（与 P4_04 相同）、evidence_ids。A/B 强贡献主张暂不通过自动预检；人工验证真实识别设计，禁止仅为通过降低结论等级。
- `creative_video`/`creative_print[]`: 每个实际 file + sha256 + has_agency_name=false；本版检查 MP4、JPEG/PNG。实际匿名性仍人工确认。
- `authorization`: client_authorized、agreement_signed、publication_option（目前仅 as_submitted）、client_authorization_file、signed_agreement_file（各含 file、sha256）。文件存在不等于签署有效。高保密或无公开权限证据阻断；编辑公开版暂不支持预检。
- `versions`: 必须为空，其他类别单独跑；人工跨版本核实。`open_p0_issues`/`open_p1_issues` 有未决项阻断，但空数组不是合格证明。

旧 `schemas/*.json` 为历史基础结构，V1.1 的完整运行契约由 `scripts/integrity.py` 和 `validate_submission.py` 强制检查；尚未重构所有独立 JSON Schema。脚本失败/异常不许包装为通过。测试正例仅证明路径可达，绝非真实参赛材料。
