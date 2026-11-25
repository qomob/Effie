#!/usr/bin/env python3
"""按该奖项真实权重计算加权分。

关键：权重从规则库读取，绝不硬编码 23.3。全球化奖/场景奖会得到不同结果。

用法:
  calculate_score.py --award EFFIE_GC_MAIN --scores scores.json
  calculate_score.py --award EFFIE_SCENARIO --scores scores.json --subcategory outdoor_media

scores.json: {"part1_challenge": 7.2, "part2_insight_strategy": 6.8,
              "part3_execution": 7.0, "part4_results": 8.5}
各分项按 10 分制打分。
"""
from __future__ import annotations

import argparse
import json
import math
import sys

import kb

PART_LABELS = {
    "part1_challenge": "第一部分 挑战、背景及目标",
    "part2_insight_strategy": "第二部分 洞察与策略",
    "part3_execution": "第三部分 策略和创意执行",
    "part4_results": "第四部分 成果",
}


def main() -> int:
    ap = argparse.ArgumentParser(description="按官方权重的加权分")
    ap.add_argument("--award", required=True)
    ap.add_argument("--scores", required=True)
    ap.add_argument("--subcategory", help="如 outdoor_media（场景奖特殊权重）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    kb.require_award(args.award)
    try:
        scores = json.load(open(args.scores, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"读取分数失败: {e}", file=sys.stderr)
        return 2

    wrule = kb.find_rule(args.award, "scoring_weights")
    if not wrule or wrule.get("verification_status")!="VERIFIED":
        print(f"规则库无 {args.award} 的评分权重，无法计算（不得用默认值代替）",
              file=sys.stderr)
        return 3
    weights = dict(wrule["rule_value"])
    used_override = False

    if args.subcategory:
        orule = kb.find_rule(args.award, "scoring_weights_override")
        if orule and orule.get("verification_status")!="VERIFIED":
            print("子类别权重未核实，拒绝计算",file=sys.stderr); return 3
        if orule:
            applies = orule["rule_value"].get("applies_to", "")
            if args.subcategory in ("outdoor_media", "户外媒体") or \
               args.subcategory in applies:
                weights = dict(orule["rule_value"]["weights"])
                used_override = True

    total = 0.0
    rows = []
    for k, w in weights.items():
        s = scores.get(k)
        if s is None:
            print(f"缺少分项 {k}", file=sys.stderr)
            return 2
        if isinstance(s,bool): return 2
        try: s = float(s)
        except (TypeError,ValueError): return 2
        if not math.isfinite(s) or not 0 <= s <= 10:
            print(f"分项 {k}={s} 超出 0-10 范围", file=sys.stderr)
            return 2
        contrib = s / 10 * w
        total += contrib
        rows.append({"part": k, "label": PART_LABELS.get(k, k),
                     "raw": s, "weight_pct": w, "weighted": round(contrib, 2)})

    src = f"（来源：{wrule['source_document']} P{wrule['source_page']}）"
    if used_override:
        orule = kb.find_rule(args.award, "scoring_weights_override")
        src += f"\n（子类别覆盖：{orule['rule_value']['applies_to']}，"
        src += f"{orule['source_document']} P{orule['source_page']}）"

    if args.json:
        print(json.dumps({"award": args.award, "weights_source": wrule["rule_id"],
                          "override_applied": used_override,
                          "rows": rows, "total": round(total, 2)},
                         ensure_ascii=False, indent=2))
    else:
        print(f"加权分计算 · {args.award}"
              + (f"（子类别 {args.subcategory}）" if used_override else ""))
        print("=" * 66)
        print(f"{'分项':32s}{'原始/10':>8s}{'权重%':>8s}{'加权':>8s}")
        for r in rows:
            print(f"{r['label']:32s}{r['raw']:>8.2f}{r['weight_pct']:>8.1f}"
                  f"{r['weighted']:>8.2f}")
        print("-" * 66)
        print(f"{'合计（百分制）':32s}{'':>16s}{total:>8.2f}")
        print("=" * 66)
        print(src)
        print("\n说明：这是内部诊断分，非官方评分，不能等同于评委打分或获奖概率。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
