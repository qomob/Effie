# 示例：完整走一遍

> 本例使用 `example-case.json`（**SYNTHETIC 合成数据**，非真实项目）。

## 1. 查规则（带出处）

```bash
python3 scripts/rule_query.py --award EFFIE_GC_MAIN --type scoring_weights
python3 scripts/rule_query.py --award EFFIE_GC_MAIN --type eligibility_window
```

## 2. 查类别

```bash
python3 scripts/category_query.py --number 42     # 情感营销
python3 scripts/category_query.py --number 46     # 场景营销
python3 scripts/category_query.py --search 情感
```

## 3. 资格校验

```bash
python3 scripts/validate_eligibility.py \
  --case examples/example-case.json --award EFFIE_GC_MAIN
```

预期：`PASS`（时间窗口、地域、类别数量、特殊资格全过）

## 4. 指标口径审计

```bash
python3 - <<'PY' > /tmp/m.json
import json
c=json.load(open("examples/example-case.json"))
json.dump({"goals":c["goals"],"metrics":c["metrics"],
           "narrative_flags":c["narrative_flags"]},open("/dev/stdout","w"),ensure_ascii=False)
PY
python3 scripts/validate_metrics.py --file /tmp/m.json
```

## 5. 归因审查

```bash
python3 - <<'PY' > /tmp/a.json
import json
c=json.load(open("examples/example-case.json"))
json.dump(c["attribution"],open("/dev/stdout","w"),ensure_ascii=False)
PY
python3 scripts/audit_attribution.py --file /tmp/a.json
```

预期：B 级声明，证据可支撑 B 级，无 P0。

## 6. 证据审计

```bash
python3 - <<'PY' > /tmp/e.json
import json
c=json.load(open("examples/example-case.json"))
json.dump({"evidence":c["evidence"],"claims":c["claims"]},open("/dev/stdout","w"),ensure_ascii=False)
PY
python3 scripts/verify_evidence.py --file /tmp/e.json --base-dir ./materials
```

> 没有 `materials/` 目录时会跳过 E02 哈希校验，并明确提示"未执行"。

## 7. 加权分

```bash
echo '{"part1_challenge":7.5,"part2_insight_strategy":7.0,
       "part3_execution":7.2,"part4_results":7.8}' > /tmp/s.json
python3 scripts/calculate_score.py --award EFFIE_GC_MAIN --scores /tmp/s.json
```

## 8. 提交门禁

```bash
python3 scripts/validate_submission.py \
  --case examples/example-case.json --award EFFIE_GC_MAIN
```

此例缺 `answers`（书面参赛表正文），会停在 `NEEDS_INFORMATION`——
这是正确行为：**没有正文就不可能 READY**。

## 9. 全量测试

```bash
python3 tests/run_all.py
```
