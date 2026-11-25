#!/usr/bin/env python3
"""营销归因审查（M07）：判断"营销是否真的贡献了成果"。

检查:
  A01 是否声明了因果结论却无归因方法
  A02 所用归因方法是否与数据能力匹配（不可越级）
  A03 是否排查了 14 类替代解释
  A04 4.2 字段是否填写并量化
  A05 是否把相关性写成因果
  A06 是否遗漏同期其它营销活动
  A07 自然增长/季节/价格/铺货 是否被扣除

用法:
  audit_attribution.py --file attribution.json
"""
from __future__ import annotations

import argparse
import json
import sys

# 14 替代解释（与 references/attribution-methodology.md 对齐）
CONFOUNDERS = [
    ("seasonality", "季节性"),
    ("category_growth", "行业整体增长"),
    ("product_upgrade", "产品升级/换代"),
    ("price_promo", "降价与促销"),
    ("channel_expansion", "渠道扩张"),
    ("distribution", "铺货率变化"),
    ("competitor_exit", "竞品退出/失误"),
    ("price_change", "价格变化"),
    ("macro", "宏观环境"),
    ("brand_history", "品牌历史趋势"),
    ("organic_growth", "自然增长"),
    ("parallel_campaigns", "同期其它营销活动"),
    ("measurement_change", "统计口径变更"),
    ("data_quality", "数据质量"),
]

METHOD_STRENGTH = {
    "pre_post": 1, "yoy": 2, "category_benchmark": 3, "control_group": 4,
    "ab_test": 5, "geo_test": 5, "did": 4, "holdout": 5, "mmm": 3,
}

METHOD_REQUIREMENTS = {
    "did": ["panel_data", "parallel_trend_check"],
    "holdout": ["random_assignment", "sufficient_sample"],
    "ab_test": ["random_assignment", "sufficient_sample"],
    "geo_test": ["region_independence", "no_spillover"],
    "mmm": ["multi_period", "multi_channel", "collinearity_check"],
    "control_group": ["comparable_group"],
    "category_benchmark": ["category_data"],
}

MAX_CLAIM_BY_STRENGTH = {5: "A", 4: "A", 3: "B", 2: "C", 1: "C", 0: "D"}
# A is strongest. Rank so we can compare claimed vs allowed correctly.
RANK = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}


def main() -> int:
    ap = argparse.ArgumentParser(description="营销归因审查")
    ap.add_argument("--file", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        doc = json.load(open(args.file, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"读取失败: {e}", file=sys.stderr)
        return 2

    methods = [m.lower() for m in (doc.get("methods") or [])]
    data = set(doc.get("available_data") or [])
    handled = set(doc.get("confounders_addressed") or [])
    claimed = (doc.get("claimed_conclusion") or "").upper()  # A-E
    section42 = doc.get("section_4_2_text") or ""
    parallel = doc.get("has_parallel_campaigns")
    findings = []

    if claimed not in RANK:
        findings.append(("A00", "P1", "缺有效归因等级", "明确 A-E 等级"))
    # A01
    if claimed in ("A", "B") and not methods:
        findings.append(("A01", "P0",
                         "声称存在营销贡献/因果，但未说明任何归因方法",
                         "补方法与前提，或把结论降为 C 级（仅相关性）"))

    # A02 method prerequisites
    best = 0
    for m in methods:
        s = METHOD_STRENGTH.get(m, 0)
        if m not in METHOD_STRENGTH:
            findings.append(("A02", "P1", f"未知方法 {m}", "使用受支持方法"))
        if all(req in data for req in METHOD_REQUIREMENTS.get(m, [])):
            best = max(best, s)
        for req in METHOD_REQUIREMENTS.get(m, []):
            if req not in data:
                findings.append(("A02", "P1",
                                 f"方法 {m} 缺少前提数据/检验: {req}",
                                 f"补 {req}，否则不得使用 {m} 的结论口径"))
    allowed = MAX_CLAIM_BY_STRENGTH.get(best, "D")
    if claimed and claimed in RANK and allowed in RANK:
        if RANK[claimed] > RANK[allowed]:
            # claimed is stronger than evidence allows -> overreach
            findings.append(("A05", "P0",
                             f"结论声称 {claimed} 级，但现有方法最高只能支撑 {allowed} 级（因果越级）",
                             f"下调至 {allowed} 级；这是最容易被评委识破的过度归因"))
        elif RANK[claimed] < RANK[allowed]:
            findings.append(("A02", "P2",
                             f"结论声明 {claimed} 级，弱于声明方法理论上限的 {allowed} 级",
                             f"证据足够时可提升至 {allowed} 级，不必过度保守"))

    # A03 confounders
    missing = [zh for k, zh in CONFOUNDERS if k not in handled]
    if len(missing) > 8:
        findings.append(("A03", "P1",
                         f"仅排查 {len(handled)}/{len(CONFOUNDERS)} 类替代解释；未排查: "
                         + "、".join(missing[:10]),
                         "在 4.2 逐项说明影响或说明为何不适用"))
    elif missing:
        findings.append(("A03", "P2",
                         f"未排查: " + "、".join(missing),
                         "补 4.2 说明或标注不适用"))

    # A04 section 4.2
    if not section42.strip():
        findings.append(("A04", "P1",
                         "4.2 字段为空；官方明确要求阐述其它影响因素",
                         "主动列出替代因素及其量化影响，展示已排除"))
    elif len(section42.strip()) < 60:
        findings.append(("A04", "P2",
                         "4.2 内容过短，难以体现归因思考",
                         "至少覆盖 3 类主要替代因素"))

    # A06 parallel campaigns
    if parallel is True and "parallel_campaigns" not in handled:
        findings.append(("A06", "P0",
                         "存在同期其它营销活动但未排查，归因结论不成立",
                         "拆分各活动贡献，或改用可分离的测量设计"))

    # A07 natural growth
    if "organic_growth" not in handled:
        findings.append(("A07", "P1",
                         "未扣减自然增长，无法判断增量是否来自营销",
                         "用活动前趋势外推基线并扣除"))

    sev = {"P0": 0, "P1": 0, "P2": 0}
    for _, s, _, _ in findings:
        sev[s] = sev.get(s, 0) + 1

    if args.json:
        print(json.dumps({
            "claimed": claimed, "allowed_by_evidence": allowed,
            "methods": methods, "confounders_covered": len(handled),
            "confounders_total": len(CONFOUNDERS),
            "findings": [{"code": c, "severity": s, "issue": i, "fix": f}
                         for c, s, i, f in findings],
            "counts": sev,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"归因审查 · 声称级别={claimed or '未声明'} / 声明方法理论上限={allowed} 级")
        print(f"方法: {methods or '无'}")
        print(f"替代因素排查: {len(handled)}/{len(CONFOUNDERS)}")
        print("=" * 74)
        if not findings:
            print("未发现结构性归因缺陷。")
        for c, s, i, f in findings:
            print(f"[{s}] {c}: {i}")
            print(f"      → {f}")
        print("=" * 74)
        print(f"P0={sev.get('P0',0)}  P1={sev.get('P1',0)}  P2={sev.get('P2',0)}")
        if sev.get("P0"):
            print("存在 P0 级归因问题：第四部分不得声称因果，须先修数据或降级表述。")

    return 1 if (sev.get("P0") or sev.get("P1")) else 0


if __name__ == "__main__":
    sys.exit(main())
