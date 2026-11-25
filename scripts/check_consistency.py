#!/usr/bin/env python3
"""多版本 / 多类别事实一致性检查。

同一案例投报多个类别时，各版本共享同一事实库。本脚本检查：
  K01 同一字段在不同版本中数值不同
  K02 目标与成果跨版本漂移
  K03 时间窗口不一致
  K04 品牌/产品名称不一致
  K05 预算区间不一致
  K06 某个版本为迎合类别编造了不同目标

用法:
  check_consistency.py --versions v1.json v2.json --json
"""
from __future__ import annotations

import argparse
import json
import sys

SHARED_KEYS = [
    "brand", "product", "implementation_start", "implementation_end",
    "budget_range", "paid_media_spend_range", "region",
]
# these MUST match across versions (facts cannot differ by category)
STRICT_NUMERIC_FIELDS = ["business_goal_value", "marketing_goal_values",
                         "campaign_goal_values", "result_values"]


def load(p):
    return json.load(open(p, encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="多版本一致性检查")
    ap.add_argument("--versions", nargs="+", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    vers = []
    for p in args.versions:
        try:
            d = load(p)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"读取 {p} 失败: {e}", file=sys.stderr)
            return 2
        vers.append((p, d))

    if len(vers) < 2:
        print("至少需要 2 个版本才能比对", file=sys.stderr)
        return 2

    findings = []

    for key in SHARED_KEYS:
        vals = {}
        for p, d in vers:
            v = d.get(key)
            if v not in (None, ""):
                vals.setdefault(str(v), []).append(p)
        if len(vals) > 1:
            findings.append(("K01", "P0", key,
                             f"{key} 在不同版本不一致: {vals}",
                             "同一案例多版本必须共享同一事实；修正为统一值"))

    for key in STRICT_NUMERIC_FIELDS:
        vals = {}
        for p, d in vers:
            v = d.get(key)
            if v is None:
                continue
            norm = json.dumps(v, ensure_ascii=False, sort_keys=True) \
                if isinstance(v, (list, dict)) else str(v)
            vals.setdefault(norm, []).append(p)
        if len(vals) > 1:
            findings.append(("K02", "P0", key,
                             f"{key} 跨版本不同（疑似为迎合类别改写目标/成果）: {vals}",
                             "目标是事前事实，不得按类别改写；如需不同侧重，只改叙述不改数值"))

    # brand/product naming
    for key in ("brand", "product"):
        names = set()
        for p, d in vers:
            if d.get(key):
                names.add(str(d[key]))
        if len(names) > 1:
            findings.append(("K04", "P1", key,
                             f"{key} 名称不统一: {sorted(names)}",
                             "统一中英文名称与写法，避免影响表彰信息与排名计分"))

    # goal/result pairing integrity within each version
    for p, d in vers:
        goals = d.get("goals") or []
        results = d.get("results") or []
        gcount = len(goals)
        rcount = len(results)
        if gcount and rcount and rcount < gcount:
            findings.append(("K02", "P1", p,
                             f"目标 {gcount} 个但成果仅 {rcount} 个，存在未回应的目标",
                             "为每个目标补对应成果"))

    # category-specific tailoring: check narrative differs but facts do not
    narrs = {}
    for p, d in vers:
        n = d.get("narrative_theme")
        if n:
            narrs[p] = n
    if len(set(narrs.values())) == 1 and len(narrs) > 1:
        findings.append(("K06", "P2", "-",
                         "多个版本叙事主题完全相同，未按类别量体裁衣",
                         "官方强调需针对类别定义调整阐述重心（但不改事实）"))

    sev = {"P0": 0, "P1": 0, "P2": 0}
    for _, s, _, _, _ in findings:
        sev[s] = sev.get(s, 0) + 1

    if args.json:
        print(json.dumps({"versions": [p for p, _ in vers],
                          "findings": [{"code": c, "severity": s, "field": f,
                                        "issue": i, "fix": fx}
                                       for c, s, f, i, fx in findings],
                          "counts": sev}, ensure_ascii=False, indent=2))
    else:
        print(f"一致性检查 · {len(vers)} 个版本")
        print("=" * 74)
        if not findings:
            print("跨版本事实一致。")
        for c, s, f, i, fx in findings:
            print(f"[{s}] {c} {f}: {i}")
            print(f"      → {fx}")
        print("=" * 74)
        print(f"P0={sev.get('P0',0)}  P1={sev.get('P1',0)}  P2={sev.get('P2',0)}")

    return 1 if (sev.get("P0") or sev.get("P1")) else 0


if __name__ == "__main__":
    sys.exit(main())
