#!/usr/bin/env python3
"""参赛资格校验 → PASS / CONDITIONAL / BLOCKED / UNKNOWN

规则全部来自 references/annual-rules-2026.json，每条判定带官方出处。

用法:
  validate_eligibility.py --case case.json --award EFFIE_GC_MAIN
  validate_eligibility.py --case case.json --award EFFIE_GLOBAL --json

case.json 最少字段见 templates/case-profile.json，关键为:
  implementation_start, implementation_end, region, category_numbers, award_id
可选: budget_cny, brand_market_share_pct, brand_age_years, product_launch_date,
      consecutive_years, has_pilot_only, data_sources[], agencies_in_materials[]

退出码: 0=PASS, 1=CONDITIONAL/BLOCKED, 2=用法错误, 3=UNKNOWN(规则缺失)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date

import kb

PASS, CONDITIONAL, BLOCKED, UNKNOWN = "PASS", "CONDITIONAL", "BLOCKED", "UNKNOWN"


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    s = str(s).strip().replace("/", "-").replace(".", "-")
    parts = s.split("-")
    try:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 1
        return date(y, m, d)
    except (ValueError, IndexError):
        return None


class Check:
    def __init__(self, cid, title, status, detail, cite="", rule_id=""):
        self.cid, self.title, self.status = cid, title, status
        self.detail, self.cite, self.rule_id = detail, cite, rule_id

    def as_dict(self):
        return {"check": self.cid, "title": self.title, "status": self.status,
                "detail": self.detail, "citation": self.cite, "rule_id": self.rule_id}


def rulecite(award_id, rtype):
    r = kb.find_rule(award_id, rtype)
    return (kb.cite(r), r["rule_id"] if r else ""), r


def check_window(case, award_id):
    w = kb.eligibility_window(award_id)
    (cite, rid), _ = rulecite(award_id, "eligibility_window")
    if not w:
        return Check("C01", "参赛资格时间窗口", UNKNOWN, "规则库缺失资格窗口", cite, rid)
    start_in = parse_date(case.get("implementation_start"))
    end_in = parse_date(case.get("implementation_end"))
    ws, we = parse_date(w["start"]), parse_date(w["end"])
    if not start_in:
        return Check("C01", "参赛资格时间窗口", CONDITIONAL,
                     "缺少 implementation_start，无法判定", cite, rid)
    if start_in > we:
        return Check("C01", "参赛资格时间窗口", BLOCKED,
                     f"实施开始 {start_in} 晚于官方截止 {we}；2026-06-30 后才实施的营销活动不可参赛",
                     cite, rid)
    if not end_in or end_in < start_in:
        return Check("C01", "参赛资格时间窗口", CONDITIONAL, "缺实施结束日期或区间倒序", cite, rid)
    if end_in and end_in < ws:
        return Check("C01", "参赛资格时间窗口", BLOCKED,
                     f"实施结束 {end_in} 早于官方起始 {ws}，不在资格窗口内", cite, rid)
    if start_in < ws:
        return Check("C01", "参赛资格时间窗口", PASS,
                     f"活动自 {start_in} 开始（早于 {ws} 允许，但须以窗口内数据为主）", cite, rid)
    return Check("C01", "参赛资格时间窗口", PASS,
                 f"实施区间与资格窗口 {ws}~{we} 有重叠", cite, rid)


def check_region(case, award_id):
    (cite, rid), r = rulecite(award_id, "eligibility_region")
    if not r or r.get("verification_status") != "VERIFIED":
        return Check("C02", "地域口径", UNKNOWN, "规则库缺失地域规则", cite, rid)
    required = r["rule_value"]
    actual = (case.get("region") or "").upper()
    if not actual:
        return Check("C02", "地域口径", CONDITIONAL,
                     f"缺少 region；本奖项要求 {required}", cite, rid)
    ok_set = {"GREATER_CHINA"} if required == "GREATER_CHINA" else {"OVERSEAS"}
    if required == "GREATER_CHINA":
        ok_set |= {"MAINLAND", "HK", "MO", "TW", "GREATER_CHINA"}
    if required == "OVERSEAS":
        ok_set |= {"OVERSEAS", "GLOBAL", "OVERSEA"}
    if actual in ok_set:
        note = ""
        if required == "OVERSEAS":
            note = "；该奖项要求海外投放，与大中华区相反"
        return Check("C02", "地域口径", PASS, f"region={actual} 符合要求 {required}{note}",
                     cite, rid)
    return Check("C02", "地域口径", BLOCKED,
                 f"region={actual} 不符合本奖项要求 {required}"
                 + ("（本奖项须海外投放）" if required == "OVERSEAS" else ""), cite, rid)


def check_categories(case, award_id):
    (cite, rid), r = rulecite(award_id, "max_categories_per_activity")
    if not r or r.get("verification_status") != "VERIFIED":
        return Check("C03", "类别数量限制", UNKNOWN, "规则库缺失类别上限", cite, rid)
    limit = r["rule_value"]
    nums = case.get("category_numbers") or []
    if not nums:
        return Check("C03", "类别数量限制", CONDITIONAL, "尚未确定投报类别", cite, rid)
    if len(nums) > limit:
        return Check("C03", "类别数量限制", BLOCKED,
                     f"投报 {len(nums)} 个类别，超过上限 {limit}；"
                     f"官方为 1 个行业类+3 个专项类 或 4 个专项类", cite, rid)
    # industry/specialty split
    if award_id == "EFFIE_GC_MAIN":
        ind = [n for n in nums if n <= 28]
        if len(ind) > 1:
            return Check("C03", "类别数量限制", BLOCKED,
                         f"投报 {len(ind)} 个行业类（{ind}），官方规定行业类最多 1 个", cite, rid)
        return Check("C03", "类别数量限制", PASS,
                     f"{len(nums)} 个类别；行业类 {len(ind)} 个（≤1）", cite, rid)
    return Check("C03", "类别数量限制", PASS,
                 f"{len(nums)} 个类别，未超过上限 {limit}（行业类构成需按该奖项类目人工核对）",
                 cite, rid)


def check_test_project(case, award_id):
    (cite, rid), r = rulecite(award_id, "excludes_test_projects")
    if case.get("has_pilot_only"):
        return Check("C04", "非正式投放项目", BLOCKED,
                     "官方：非正式投放和实施的测试类/试点项目不具备参赛资格",
                     cite or "（来源：参赛手册 资格章节）", rid)
    return Check("C04", "非正式投放项目", PASS, "未标注为试点/测试项目",
                 cite or "（来源：参赛手册 资格章节）", rid)


def check_category_special(case, award_id):
    """Check category-specific eligibility constraints (e.g. 小预算上限, 挑战者份额)."""
    nums = case.get("category_numbers") or []
    issues, notes = [], []
    for n in nums:
        c = kb.get_category(n, award_id)
        if not c:
            notes.append(f"类别 {n} 在该奖项目录中未找到（可能为 PARTIAL 类目册），需人工核对")
            continue
        for sr in c.get("special_rules", []) or []:
            rule = sr.get("rule")
            val = sr.get("value")
            if rule == "budget_cap_cny":
                budget = case.get("budget_cny")
                scope = sr.get("scope")
                actual_scope = case.get("budget_scope")
                if actual_scope not in {"city", "province", "national"}:
                    notes.append(f"类别 {n} 缺 budget_scope，不能选择预算上限")
                    continue
                if actual_scope != scope:
                    continue
                if budget is None:
                    notes.append(f"类别 {n} 有预算上限（{scope} {val:,} 元），但未提供 budget_cny")
                elif budget > val:
                    issues.append(f"类别 {n} 预算 {budget:,} 元超过 {scope} 上限 {val:,} 元")
            elif rule == "market_share_max_pct":
                ms = case.get("brand_market_share_pct")
                if ms is None:
                    notes.append(f"类别 {n} 要求市场份额 <{val}%，但未提供 brand_market_share_pct")
                elif ms >= val:
                    issues.append(f"类别 {n} 要求份额 <{val}%，实际 {ms}%，不符合挑战者定义")
            elif rule == "brand_age_max_years":
                age = case.get("brand_age_years")
                if age is None:
                    notes.append(f"类别 {n} 要求品牌成立 ≤{val} 年，未提供 brand_age_years")
                elif age > val:
                    issues.append(f"类别 {n} 要求成立 ≤{val} 年，实际 {age} 年")
            elif rule == "product_age_max_months":
                pd = parse_date(case.get("product_launch_date"))
                if not pd:
                    notes.append(f"类别 {n} 要求新品上市 ≤{val} 个月，未提供 product_launch_date")
                else:
                    ref = parse_date(case.get("implementation_start")) or \
                        parse_date(case.get("implementation_end"))
                    if ref:
                        months = (ref.year - pd.year) * 12 + (ref.month - pd.month)
                        if months > val:
                            issues.append(
                                f"类别 {n} 要求新品上市 ≤{val} 个月，"
                                f"实际上市 {pd} 距实施 {ref} 已 {months} 个月")
                        else:
                            notes.append(
                                f"类别 {n} 新品年龄 {months} 个月（≤{val}），需在材料中证明上市日期")
            elif rule == "requires_social_benefit_link":
                if not case.get("entity_type") or case.get("social_benefit_link") is not True:
                    notes.append(f"类别 {n} 需证明商业目标与社会效益关联")
                if case.get("entity_type") and case["entity_type"] != "for_profit":
                    issues.append(
                        f"类别 {n} 要求为营利企业且将商业目标与社会效益结合；"
                        f"实际 entity_type={case['entity_type']}，应改投 92 社会公益-非营利机构")
            elif rule == "requires_non_profit":
                if not case.get("entity_type"):
                    notes.append(f"类别 {n} 缺机构类型")
                if case.get("entity_type") and case["entity_type"] == "for_profit":
                    issues.append(
                        f"类别 {n} 要求为非营利机构/协会/政府；"
                        f"营利企业应改投 91 社会公益-品牌")
            elif rule == "consecutive_years_min":
                yrs = case.get("consecutive_years")
                if yrs is None:
                    notes.append(f"类别 {n} 要求连续 ≥{val} 年，未提供 consecutive_years")
                elif yrs < val:
                    issues.append(f"类别 {n} 要求连续 ≥{val} 年，实际 {yrs} 年")
            elif rule == "sole_activity_in_period":
                if case.get("has_other_activities_in_period") is True:
                    issues.append(f"类别 {n} 要求为该品牌该投放期内唯一营销活动")
                elif case.get("has_other_activities_in_period") is not False:
                    notes.append(f"类别 {n} 缺同期唯一活动证明")
            elif rule == "dedicated_form":
                if case.get("form") != val:
                    notes.append(f"类别 {n} 需专用表 {val}")
            elif rule == "video_max_seconds":
                notes.append(f"类别 {n} 专用素材规则需人工核验")
            else:
                notes.append(f"类别 {n} 特殊规则 {rule} 尚无自动核验器，必须人工核对，不能判 PASS")
    if issues:
        return Check("C05", "类别特殊资格", BLOCKED, "；".join(issues),
                     "（来源：类别定义文件，见 categories-2026.json special_rules）")
    if notes:
        return Check("C05", "类别特殊资格", CONDITIONAL, "；".join(notes),
                     "（来源：类别定义文件）")
    return Check("C05", "类别特殊资格", PASS,
                 "已投报类别的特殊资格条件未发现冲突" if nums else "类别未定",
                 "（来源：类别定义文件）")


def check_agency_anonymity(case, award_id):
    (cite, rid), r = rulecite(award_id, "agency_anonymity_required")
    ags = case.get("agencies_in_materials") or []
    if ags:
        return Check("C06", "盲评匿名", BLOCKED,
                     f"材料中出现代理公司标识: {ags}；官方采用代理公司盲评，"
                     f"参赛表/创意材料/文件名均不得出现", cite, rid)
    return Check("C06", "盲评匿名", PASS, "未发现材料中出现代理公司名称/LOGO", cite, rid)


def check_data_source(case, award_id):
    (cite, rid), r = rulecite(award_id, "data_source_required")
    claims = case.get("claims") or []
    unsourced = [c.get("claim_id", "?") for c in claims
                 if not c.get("evidence_ids") and c.get("type") in ("FACT", "CALC")]
    if unsourced:
        return Check("C07", "数据来源完整性", CONDITIONAL,
                     f"以下事实/计算类主张未绑定证据: {unsourced[:8]}", cite, rid)
    if not case.get("data_sources") and not claims:
        return Check("C07", "数据来源完整性", CONDITIONAL,
                     "未提供任何数据来源登记；官方规定未提供来源将被取消资格", cite, rid)
    return Check("C07", "数据来源完整性", PASS, "已登记数据来源/主张证据绑定", cite, rid)


def check_year_covered(case, award_id):
    year = case.get("competition_year")
    if type(year) is not int or year != 2026:
        return Check("C00", "年度规则覆盖", UNKNOWN,
                     f"请求年度 {year}，知识库仅覆盖 2026；不得用 2026 规则判定其它年度")
    return Check("C00", "年度规则覆盖", PASS, "2026 规则已覆盖", "")


def main() -> int:
    ap = argparse.ArgumentParser(description="艾菲参赛资格校验")
    ap.add_argument("--case", required=True, help="案例 JSON 路径")
    ap.add_argument("--award", required=True, help="award_id")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    kb.require_award(args.award)
    try:
        case = json.load(open(args.case, encoding="utf-8"))
    except FileNotFoundError:
        print(f"找不到案例文件: {args.case}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"案例 JSON 解析失败: {e}", file=sys.stderr)
        return 2

    checks = [
        check_year_covered(case, args.award),
        check_window(case, args.award),
        check_region(case, args.award),
        check_categories(case, args.award),
        check_test_project(case, args.award),
        check_category_special(case, args.award),
        check_agency_anonymity(case, args.award),
        check_data_source(case, args.award),
    ]

    statuses = [c.status for c in checks]
    if BLOCKED in statuses:
        overall = BLOCKED
    elif UNKNOWN in statuses:
        overall = UNKNOWN
    elif CONDITIONAL in statuses:
        overall = CONDITIONAL
    else:
        overall = PASS

    if args.json:
        print(json.dumps({"award_id": args.award, "overall": overall,
                          "checks": [c.as_dict() for c in checks]},
                         ensure_ascii=False, indent=2))
    else:
        print(f"资格校验结果: {overall}   (奖项 {args.award})")
        print("=" * 66)
        for c in checks:
            mark = {"PASS": "OK  ", "CONDITIONAL": "COND", "BLOCKED": "STOP",
                    "UNKNOWN": "UNK "}[c.status]
            print(f"[{mark}] {c.cid} {c.title}: {c.status}")
            print(f"        {c.detail}")
            if c.cite:
                print(f"        {c.cite}")
        print("=" * 66)
        if overall == PASS:
            print("资格通过。可继续做案例价值诊断与类别匹配。")
        elif overall == CONDITIONAL:
            print("条件性通过：需补齐上述事实/材料后才能给出正式资格结论。")
        elif overall == BLOCKED:
            print("不通过：存在明确不合规条件，不得通过提高评分或包装来抵消。")
        else:
            print("无法判定：缺少必要官方规则或关键事实。禁止在此状态下宣称可参赛。")

    return 0 if overall == PASS else (3 if overall == UNKNOWN else 1)


if __name__ == "__main__":
    sys.exit(main())
