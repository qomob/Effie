#!/usr/bin/env python3
"""专业场景测试：12 类真实业务案例的端到端判断。

每个场景是一个合成的、结构完整的案例档案（标记 SYNTHETIC），
用真实脚本跑资格 + 指标 + 归因 + 证据 + 门禁，检验 Skill 的判断是否正确。

注意：这些案例是人工构造的测试夹具，不是真实项目、不是获奖案例。

用法:
  python3 run_scenarios.py
  python3 run_scenarios.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")

SCEN = []


def scen(sid, name, expect_elig, expect_metric_p0, note):
    SCEN.append({"id": sid, "name": name, "expect_elig": expect_elig,
                 "expect_metric_p0": expect_metric_p0, "note": note})


def base(**kw):
    d = {"competition_year": 2026, "form": "通用",
         "implementation_start": "2025-03-01", "implementation_end": "2025-12-31",
         "region": "GREATER_CHINA", "category_numbers": [1],
         "data_sources": ["brand_system"]}
    d.update(kw)
    return d


# --- S01 快消品牌整合营销 ---------------------------------------------------
S01 = base(category_numbers=[1, 46, 42], brand="FMCG-A", product="洗发水",
           goals=[{"goal_id": "G1", "type": "business", "kpi": "份额+1.5pt"},
                  {"goal_id": "G2", "type": "marketing", "kpi": "渗透率+3pt"}],
           metrics=[
               {"metric_id": "M1", "name": "市场份额", "value": "+1.5", "unit": "百分点",
                "period": "2025-03~2025-12", "baseline": "16.2%",
                "baseline_type": "category", "denominator": "品类销售额",
                "goal_id": "G1", "stated_as": "level",
                "formula": "品牌销售额/品类销售额"},
               {"metric_id": "M2", "name": "渗透率", "value": "38", "unit": "%",
                "period": "2025-03~2025-12", "baseline": "35%",
                "baseline_type": "own_history", "denominator": "目标家庭数",
                "goal_id": "G2", "stated_as": "level"}],
           evidence=[{"evidence_id": "E1", "file": "s.csv", "locator": "p1",
                      "quote": "份额16.2→17.7", "provider": "尼尔森",
                      "metric": "份额", "value": "17.7", "unit": "%",
                      "period": "2025-03~2025-12", "status": "VERIFIED",
                      "level": "third_party_research"}],
           claims=[{"claim_id": "C1", "text": "份额+1.5pt", "type": "CALC",
                    "evidence_ids": ["E1"], "value": "17.7", "unit": "%",
                    "period": "2025-03~2025-12"}],
           narrative_flags={"claims_causality": False})
scen("S01", "快消整合营销", "CONDITIONAL", 0, "46 场景营销特殊规则 scenario_based_required 尚待核验")

# --- S02 食品饮料新品上市 ---------------------------------------------------
S02 = base(category_numbers=[58, 115], brand="Drink-B", product="气泡水新品",
           product_launch_date="2025-04-15", implementation_start="2025-11-01",
           implementation_end="2025-12-31",
           goals=[{"goal_id": "G1", "type": "business", "kpi": "首年销量"},
                  {"goal_id": "G2", "type": "marketing", "kpi": "试饮率"}],
           metrics=[{"metric_id": "M1", "name": "销售额", "value": "1.8", "unit": "亿元",
                     "period": "2025-04~2025-12", "baseline_type": "none",
                     "goal_id": "G1", "stated_as": "level"}],
           narrative_flags={"claims_causality": False})
scen("S02", "食品饮料新品上市", "BLOCKED", 0,
     "115 要求新品上市≤3个月；2025-04 上市、2025-11 起实施已 7 个月 → 应拦为 BLOCKED")

# --- S03 美妆品牌年轻化 -----------------------------------------------------
S03 = base(category_numbers=[16, 32], brand="Beauty-C",
           goals=[{"goal_id": "G1", "type": "business", "kpi": "25 岁以下客群占比"},
                  {"goal_id": "G2", "type": "marketing", "kpi": "品牌联想"}],
           metrics=[{"metric_id": "M1", "name": "25岁以下客群占比", "value": "41",
                     "unit": "%", "period": "2025-03~2025-12", "baseline": "27%",
                     "baseline_type": "own_history", "denominator": "总客数",
                     "goal_id": "G2", "stated_as": "level"}],
           narrative_flags={"claims_causality": False})
scen("S03", "美妆品牌年轻化", "PASS", 0, "行业类16 + 专项32（青年营销-服务）")

# --- S04 汽车品牌营销 -------------------------------------------------------
S04 = base(category_numbers=[10], brand="Auto-D", product="新能源车型",
           goals=[{"goal_id": "G1", "type": "business", "kpi": "订单量"}],
           metrics=[{"metric_id": "M1", "name": "订单量", "value": "24000", "unit": "台",
                     "period": "2025-03~2025-12", "baseline": "15000",
                     "baseline_type": "own_history", "goal_id": "G1",
                     "stated_as": "level"}],
           narrative_flags={"claims_causality": False})
scen("S04", "汽车品牌营销", "PASS", 0,
     "注意：汽车行业类应报艾菲汽车奖，本处仅验证主奖项专项/行业判断逻辑")

# --- S05 B2B 企业营销 -------------------------------------------------------
S05 = base(category_numbers=[29], brand="B2B-E", product="工业 SaaS",
           goals=[{"goal_id": "G1", "type": "business", "kpi": "ARR 增长"},
                  {"goal_id": "G2", "type": "marketing", "kpi": "MQL 数量"}],
           metrics=[{"metric_id": "M1", "name": "MQL", "value": "4200", "unit": "个",
                     "period": "2025-03~2025-12", "baseline": "2100",
                     "baseline_type": "own_history", "goal_id": "G2",
                     "stated_as": "level"}],
           narrative_flags={"claims_causality": False})
scen("S05", "B2B 企业营销", "CONDITIONAL", 0,
     "29 类 b2b_required 尚待人工核验；ARR 目标缺成果，不是完整合格案例")

# --- S06 电商促销与生意增长 -------------------------------------------------
S06 = base(category_numbers=[61, 119], brand="EC-F",
           goals=[{"goal_id": "G1", "type": "business", "kpi": "GMV"},
                  {"goal_id": "G2", "type": "marketing", "kpi": "转化率"}],
           metrics=[{"metric_id": "M1", "name": "GMV", "value": "8.2", "unit": "亿元",
                     "period": "2025-11-01~2025-11-11", "baseline_type": "own_history",
                     "goal_id": "G1", "stated_as": "level"}],
           narrative_flags={"claims_causality": True, "has_control_or_model": False})
scen("S06", "电商促销与生意增长", "PASS", 1,
     "GMV 冒充收入 + 无对照却称因果 → 应有 P0")

# --- S07 私域运营 -----------------------------------------------------------
S07 = base(category_numbers=[106, 107], brand="Private-G",
           goals=[{"goal_id": "G1", "type": "business", "kpi": "复购率"},
                  {"goal_id": "G2", "type": "marketing", "kpi": "私域 ARPU"}],
           metrics=[{"metric_id": "M1", "name": "复购率", "value": "34", "unit": "%",
                     "period": "2025-03~2025-12", "baseline": "22%",
                     "baseline_type": "own_history", "denominator": "私域首购人数",
                     "goal_id": "G1", "stated_as": "level"},
                    {"metric_id": "M2", "name": "ARPU", "value": "218", "unit": "元",
                     "period": "2025-03~2025-12", "baseline": "165",
                     "baseline_type": "own_history", "goal_id": "G2",
                     "stated_as": "level"}],
           narrative_flags={"claims_causality": False})
scen("S07", "私域运营", "PASS", 0, "两个专项类（同赛道），组合合法")

# --- S08 社交/红人营销 ------------------------------------------------------
S08 = base(category_numbers=[110, 113], brand="Influencer-H",
           goals=[{"goal_id": "G1", "type": "business", "kpi": "带货 GMV"},
                  {"goal_id": "G2", "type": "marketing", "kpi": "品牌搜索量"}],
           metrics=[{"metric_id": "M1", "name": "带货GMV", "value": "2.1", "unit": "亿元",
                     "period": "2025-05~2025-08", "baseline_type": "own_history",
                     "goal_id": "G1", "stated_as": "level", "as_called": "销售额"},
                    {"metric_id": "M2", "name": "搜索指数", "value": "+180", "unit": "%",
                     "period": "2025-05~2025-08", "baseline_type": "own_history",
                     "goal_id": "G2", "stated_as": "growth"}],
           narrative_flags={"claims_causality": False})
scen("S08", "社交与红人营销", "PASS", 0,
     "M2 增长率缺基线（P1）+ M1 GMV 冒充销售额（P1）；无 P0")

# --- S09 公益/社会价值 ------------------------------------------------------
S09 = base(category_numbers=[91], brand="NGO-I", entity_type="non_profit",
           goals=[{"goal_id": "G1", "type": "business", "kpi": "募款额"},
                  {"goal_id": "G2", "type": "campaign", "kpi": "认知度"}],
           metrics=[{"metric_id": "M1", "name": "募款额", "value": "760", "unit": "万元",
                     "period": "2025-04~2025-05", "baseline": "500",
                     "baseline_type": "own_history", "goal_id": "G1",
                     "stated_as": "level"}],
           narrative_flags={"claims_causality": False})
scen("S09", "公益与社会价值", "BLOCKED", 0,
     "91 适用于营利企业；NGO 主体应投 92，脚本应拦为 BLOCKED 并提示改投")

# --- S10 数据智能营销 -------------------------------------------------------
S10 = base(category_numbers=[132, 133], brand="Data-J",
           goals=[{"goal_id": "G1", "type": "business", "kpi": "转化率提升"},
                  {"goal_id": "G2", "type": "marketing", "kpi": "人群精度"}],
           metrics=[{"metric_id": "M1", "name": "转化率", "value": "4.8", "unit": "%",
                     "period": "2025-03~2025-12", "baseline": "2.9%",
                     "baseline_type": "own_history", "denominator": "曝光去重人数",
                     "goal_id": "G1", "stated_as": "level",
                     "formula": "成交人数/去重触达人数"}],
           narrative_flags={"claims_causality": False})
scen("S10", "数据智能营销", "PASS", 0, "数据智能赛道 2 个类别")

# --- S11 长周期持续成功 -----------------------------------------------------
S11 = base(category_numbers=[55], form="持续成功类", brand="Legacy-K",
           consecutive_years=4,
           goals=[{"goal_id": "G1", "type": "business", "kpi": "份额维持"}],
           metrics=[{"metric_id": "M1", "name": "市场份额", "value": "23", "unit": "%",
                     "period": "2025-03~2025-12", "baseline": "21%",
                     "baseline_type": "own_history", "denominator": "品类销售额",
                     "goal_id": "G1", "stated_as": "level"}],
           narrative_flags={"claims_causality": False})
scen("S11", "长周期持续成功", "CONDITIONAL", 0, "55 连续4年但核心元素延续与专用素材规则仍须人工核验")

# --- S12 看似成功但缺乏实效（低质量） ---------------------------------------
S12 = base(category_numbers=[72], brand="Hype-L",
           goals=[{"goal_id": "G1", "type": "business", "kpi": "销售额增长"},
                  {"goal_id": "G2", "type": "campaign", "kpi": "曝光量"}],
           metrics=[{"metric_id": "M1", "name": "曝光量", "value": "35", "unit": "亿次",
                     "period": "2025-06", "goal_id": "G1", "stated_as": "level"},
                    {"metric_id": "M2", "name": "互动量", "value": "1385", "unit": "万",
                     "period": "2025-06", "goal_id": "G1", "stated_as": "level"}],
           narrative_flags={"claims_causality": True, "has_control_or_model": False})
scen("S12", "看似成功但无商业实效（低质量）", "PASS", 1,
     "只有曝光/互动回答生意目标 → 应有多项 P0/P1")


def run_one(s):
    """跑一个场景，返回该场景在各校验器上的实际结论。

    修复（P1-7）：旧版只跑 eligibility + metrics 两个校验器，却对外称
    「端到端」。现在补跑 attribution / evidence / submission 门禁，
    使「端到端」名副其实；未提供的材料类型会在结果中如实标记 skipped。
    """
    d = tempfile.mkdtemp()
    case_p = os.path.join(d, "case.json")
    json.dump(s, open(case_p, "w"), ensure_ascii=False)
    ran = []

    # eligibility
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_eligibility.py"),
                        "--case", case_p, "--award", "EFFIE_GC_MAIN", "--json"],
                       capture_output=True, text=True)
    ran.append("eligibility")
    try:
        ej = json.loads(r.stdout)
        elig = ej["overall"]
    except json.JSONDecodeError:
        elig = "ERROR"

    # metrics
    mp = os.path.join(d, "m.json")
    json.dump({"goals": s.get("goals", []), "metrics": s.get("metrics", []),
               "narrative_flags": s.get("narrative_flags", {})},
              open(mp, "w"), ensure_ascii=False)
    r2 = subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_metrics.py"),
                         "--file", mp, "--json"], capture_output=True, text=True)
    ran.append("metrics")
    try:
        mj = json.loads(r2.stdout)
        p0 = mj["counts"].get("P0", 0)
        p1 = mj["counts"].get("P1", 0)
    except json.JSONDecodeError:
        p0, p1 = -1, -1

    # attribution：仅当场景给了归因相关字段才跑
    attr = None
    if s.get("claims_causality") is not None or s.get("narrative_flags", {}).get(
            "claims_causality") is not None:
        ap = os.path.join(d, "a.json")
        json.dump({
            "claimed_conclusion": "A" if s.get("narrative_flags", {}).get(
                "claims_causality") else "C",
            "methods": s.get("methods") or ["pre_post"],
            "available_data": s.get("available_data") or [],
            "confounders_addressed": s.get("confounders_addressed") or [],
            "section_4_2_text": "x" * 100,
        }, open(ap, "w"), ensure_ascii=False)
        ra = subprocess.run([sys.executable, os.path.join(SCRIPTS, "audit_attribution.py"),
                             "--file", ap, "--json"], capture_output=True, text=True)
        ran.append("attribution")
        try:
            attr = json.loads(ra.stdout).get("counts", {})
        except json.JSONDecodeError:
            attr = {"ERROR": 1}

    # evidence：仅当场景登记了证据才跑
    ev = None
    if s.get("evidence"):
        ep = os.path.join(d, "e.json")
        json.dump({"evidence": s.get("evidence") or [],
                   "claims": s.get("claims") or [],
                   "claimed_conclusion": "A" if s.get("narrative_flags", {}).get(
                       "claims_causality") else None},
                  open(ep, "w"), ensure_ascii=False)
        re_ = subprocess.run([sys.executable, os.path.join(SCRIPTS, "verify_evidence.py"),
                              "--file", ep, "--json"], capture_output=True, text=True)
        ran.append("evidence")
        try:
            ev = json.loads(re_.stdout).get("counts", {})
        except json.JSONDecodeError:
            ev = {"ERROR": 1}

    # submission 门禁（端到端的最后一环）
    rs = subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_submission.py"),
                         "--case", case_p, "--award", "EFFIE_GC_MAIN", "--json"],
                        capture_output=True, text=True)
    ran.append("submission")
    try:
        sj = json.loads(rs.stdout)
        status = sj.get("status")
        failed_gates = sj.get("failed_gates") or []
    except json.JSONDecodeError:
        status, failed_gates = "ERROR", []

    return {
        "eligibility": elig, "p0": p0, "p1": p1,
        "attribution": attr, "evidence": ev,
        "status": status, "failed_gates": failed_gates, "ran": ran,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    # map scenario ids to their case dicts
    CASES = {"S01": S01, "S02": S02, "S03": S03, "S04": S04, "S05": S05, "S06": S06,
             "S07": S07, "S08": S08, "S09": S09, "S10": S10, "S11": S11, "S12": S12}

    out = []
    ok_all = True
    for meta in SCEN:
        sid = meta["id"]
        res = run_one(CASES[sid])
        elig, p0, p1 = res["eligibility"], res["p0"], res["p1"]
        elig_ok = (elig == meta["expect_elig"])
        # expected P0: compare presence, not exact count
        metric_ok = (p0 >= 0 and (p0 > 0) == (meta["expect_metric_p0"] > 0))
        ok = elig_ok and metric_ok and res["status"] in {"BLOCKED","NEEDS_EVIDENCE"} and bool(res["failed_gates"])
        ok_all &= ok
        out.append({"id": sid, "name": meta["name"],
                    "eligibility": elig, "expect_elig": meta["expect_elig"],
                    "p0": p0, "p1": p1, "expect_p0": meta["expect_metric_p0"],
                    "elig_ok": elig_ok, "metric_ok": metric_ok, "ok": ok,
                    "status": res["status"], "failed_gates": res["failed_gates"],
                    "ran": res["ran"],
                    "attribution": res["attribution"], "evidence": res["evidence"],
                    "note": meta["note"]})

    if args.json:
        print(json.dumps({"total": len(out),
                          "passed": sum(1 for o in out if o["ok"]),
                          "results": out}, ensure_ascii=False, indent=1))
    else:
        print("专业场景测试（12 类，全部为 SYNTHETIC 合成夹具）")
        print("=" * 82)
        for o in out:
            mark = "PASS" if o["ok"] else "FAIL"
            print(f"[{mark}] {o['id']} {o['name']}")
            print(f"       资格={o['eligibility']}（期望 {o['expect_elig']}）"
                  f"  P0={o['p0']} P1={o['p1']}（期望 P0 {'>0' if o['expect_p0'] else '=0'}）")
            print(f"       门禁状态={o['status']}"
                  + (f"  未过={o['failed_gates']}" if o['failed_gates'] else ""))
            print(f"       实际执行: {'/'.join(o['ran'])}")
            if not o["ok"]:
                print(f"       ⚠ {o['note']}")
        print("=" * 82)
        npass = sum(1 for o in out if o["ok"])
        print(f"总计 {len(out)}  通过 {npass}  失败 {len(out)-npass}")
        # 覆盖度披露：哪些校验器真的被跑到了
        allran = set()
        for o in out:
            allran |= set(o["ran"])
        print(f"覆盖校验器: {sorted(allran)}")
        if "attribution" not in allran or "evidence" not in allran:
            print("注：并非每个场景都含归因/证据材料，缺失项按场景如实跳过，不伪造通过。")

    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
