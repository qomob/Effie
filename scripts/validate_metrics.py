#!/usr/bin/env python3
"""指标口径审计（M05）：找出经不起追问的数字。

检查项:
  M01 ROI / ROAS 混用
  M02 百分比 vs 百分点
  M03 增长率缺基线/绝对值（低基数风险）
  M04 曝光冒充触达
  M05 统计周期缺失或前后不一致
  M06 无基准（既无品类也无历史对照）
  M07 虚假精确性（过度小数位）
  M08 分母/样本口径缺失
  M09 成果指标层级与目标层级不匹配
  M10 选择性披露（成果数远少于/多于目标数）

用法:
  validate_metrics.py --file metrics.json
  validate_metrics.py --file metrics.json --json

metrics.json:
{
  "goals": [{"goal_id":"G1","type":"business|marketing|campaign","kpi":"...","baseline":"..."}],
  "metrics": [
    {"metric_id":"M1","name":"新客占比","value":"51","unit":"%","period":"2025-03~2025-06",
     "baseline":"34%","baseline_type":"own_history|category|campaign", "formula":"...",
     "denominator":"总客数", "source":"brand_sales_system","goal_id":"G1",
     "stated_as":"growth|level|sum"}
  ],
  "narrative_flags": {"claims_roi": true, "claims_causality": true, "uses_impressions_as_reach": true}
}
"""
from __future__ import annotations

import argparse
import json
import re
import sys


class Finding:
    def __init__(self, code, severity, metric_id, msg, fix):
        self.code, self.severity = code, severity
        self.metric_id, self.msg, self.fix = metric_id, msg, fix

    def d(self):
        return {"code": self.code, "severity": self.severity,
                "metric_id": self.metric_id, "issue": self.msg, "fix": self.fix}


def main() -> int:
    ap = argparse.ArgumentParser(description="营销指标口径审计")
    ap.add_argument("--file", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        doc = json.load(open(args.file, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"读取失败: {e}", file=sys.stderr)
        return 2

    metrics = doc.get("metrics") or []
    goals = doc.get("goals") or []
    flags = doc.get("narrative_flags") or {}
    F: list[Finding] = []

    for m in metrics:
        mid = m.get("metric_id", "?")
        name = (m.get("name") or "").lower()
        value = str(m.get("value", ""))
        unit = (m.get("unit") or "").lower()
        period = m.get("period")
        baseline = m.get("baseline")
        btype = (m.get("baseline_type") or "").lower()
        formula = m.get("formula")
        denom = m.get("denominator")

        # M01 ROI/ROAS
        if "roi" in name and "roas" not in name:
            if not formula:
                F.append(Finding("M01", "P1", mid,
                                 f"{m.get('name')} 未说明分子是利润还是销售额，无法区分 ROI 与 ROAS",
                                 "写明 ROI=(增量利润-投入)/投入 或改称 ROAS=销售额/媒体费"))
        if "roas" in name and "roi" in (m.get("as_called") or "").lower():
            F.append(Finding("M01", "P0", mid,
                             "把 ROAS 称作 ROI 是实质性错误，会被评委质疑数据严谨性",
                             "改称 ROAS，并注明不含利润与制作人力"))

        # M03 growth without baseline
        if m.get("stated_as") == "growth":
            if not baseline:
                F.append(Finding("M03", "P1", mid,
                                 "给出增长率但未给基线值，无法判断是否为低基数效应",
                                 "补基线绝对值与本期的绝对增量"))
            if not re.search(r"\d", value):
                F.append(Finding("M03", "P2", mid, "增长数值缺失", "补具体数值"))

        # M12 GMV used as revenue (must be flagged: GMV != revenue)
        if "gmv" in name and m.get("used_as") in ("revenue", "sales", "income") \
           or ("gmv" in name and (m.get("as_called") or "").lower() in
               ("销售额", "收入", "revenue", "sales")):
            F.append(Finding("M12", "P1", mid,
                             "GMV 被当作销售额/收入使用；GMV 含未付款与退货",
                             "改用退货后净收入，或明确标注为 GMV 并说明未扣退货"))

        # M04 impressions as reach
        if "reach" in name and "impression" in (m.get("source_note") or "").lower():
            F.append(Finding("M04", "P1", mid,
                             "以曝光数当作去重触达", "改用平台去重触达口径，或明确标注为曝光次数"))

        # M05 period
        if not period:
            F.append(Finding("M05", "P1", mid,
                             "未标注统计周期；官方要求所有成果注明时间框架",
                             "补 period（起止日期）"))
        elif isinstance(period, str) and "+" in period:
            F.append(Finding("M05", "P2", mid,
                             f"周期表述不明确: {period}", "写成明确的起止日期"))

        # M06 baseline
        if not baseline and m.get("goal_id"):
            F.append(Finding("M06", "P2", mid,
                             "成果未给任何对照基准（自身历史/品类/竞品）",
                             "补品类基准或品牌历史值，否则无法评估量级意义"))

        # M07 false precision
        mm = re.search(r"(\d+)\.(\d{3,})", value)
        if mm:
            F.append(Finding("M07", "P2", mid,
                             f"精度过高（{value}），超出数据本身可信精度",
                             "按数据源精度保留 1 位小数或取整"))

        # M08 denominator
        if unit in ("%", "percent", "百分点") and not denom:
            F.append(Finding("M08", "P2", mid,
                             "百分比指标未说明分母/样本口径", "补 denominator"))

    # M02 百分点 vs 百分比 (narrative level)
    txt = json.dumps(doc, ensure_ascii=False)
    if re.search(r"提升\s*\d+(\.\d+)?\s*个?百分点", txt) and \
       re.search(r"从\s*\d+(\.\d+)?%.{0,6}到\s*\d+(\.\d+)?%.{0,10}提升\s*\d+(\.\d+)?%", txt):
        F.append(Finding("M02", "P0", "-",
                         "同一处同时出现'百分点'与'百分比'表述，存在混用",
                         "统一为百分点（比例差）或百分比（相对增长），全文一致"))

    # M09 goal/metric level mismatch
    LEVELS = {"awareness": {"impression", "reach", "曝光", "触达"},
              "attitude": {"engagement", "互动", "likes"},
              "behavior": {"conversion", "转化", "purchase", "购买"},
              "business": {"revenue", "sales", "销售额", "share", "份额", "profit", "毛利"}}
    gmap = {g.get("goal_id"): (g.get("type") or "") for g in goals}
    for m in metrics:
        gid = m.get("goal_id")
        if not gid or gid not in gmap:
            continue
        gtype = gmap[gid]
        nm = (m.get("name") or "").lower()
        if gtype == "business" and any(k in nm for k in LEVELS["awareness"]):
            F.append(Finding("M09", "P1", m.get("metric_id", "?"),
                             f"目标是生意层，但成果指标是传播层（{m.get('name')}）",
                             "改给销售额/份额/毛利/新客等生意指标，传播指标放战役层"))

    # M10 selective disclosure
    if goals and metrics:
        gids = {g.get("goal_id") for g in goals}
        covered = {m.get("goal_id") for m in metrics if m.get("goal_id") in gids}
        missing = gids - covered
        if missing:
            F.append(Finding("M10", "P1", "-",
                             f"以下目标无对应成果: {sorted(missing)}；官方要求目标与成果一一对应",
                             "为目标逐项补成果，或删去无法交付成果的目标"))

    # narrative causal overreach
    if flags.get("claims_causality") and not flags.get("has_control_or_model"):
        F.append(Finding("M11", "P0", "-",
                         "声称因果贡献，但未提供对照实验/增量测试/计量模型",
                         "降级为'相关性'表述，或补 4.2 的替代解释排除"))

    # severity roll-up
    sev = {"P0": 0, "P1": 0, "P2": 0}
    for f in F:
        sev[f.severity] = sev.get(f.severity, 0) + 1

    if args.json:
        print(json.dumps({"findings": [f.d() for f in F], "counts": sev},
                         ensure_ascii=False, indent=2))
    else:
        print(f"指标口径审计 · {len(metrics)} 个指标 / {len(goals)} 个目标")
        print("=" * 72)
        if not F:
            print("未发现口径问题（注意：本脚本只做机械规则，语义问题仍需人工判断）")
        for f in F:
            print(f"[{f.severity}] {f.code} {f.metric_id}: {f.msg}")
            print(f"      → {f.fix}")
        print("=" * 72)
        print(f"P0={sev.get('P0',0)}  P1={sev.get('P1',0)}  P2={sev.get('P2',0)}")
        if sev.get("P0"):
            print("存在 P0 级数据问题，第四部分不得定稿。")

    return 1 if (sev.get("P0") or sev.get("P1")) else 0


if __name__ == "__main__":
    sys.exit(main())
