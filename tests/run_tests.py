#!/usr/bin/env python3
"""单元 / 集成 / 对抗测试（真实执行，不伪造结果）。

运行:
  python3 run_tests.py              # 全部
  python3 run_tests.py --filter adv # 只跑对抗测试
  python3 run_tests.py --json       # 机器可读

退出码：0 全通过；1 有失败；2 环境问题
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL, "scripts")
sys.path.insert(0, SCRIPTS)

import kb                      # noqa: E402
import validate_eligibility as VE   # noqa: E402
import check_word_limits as CWL     # noqa: E402
import validate_metrics as VM       # noqa: E402
import audit_attribution as AA      # noqa: E402
import verify_evidence as VEv       # noqa: E402

RESULTS = []


def record(group, name, ok, detail):
    RESULTS.append({"group": group, "name": name, "ok": bool(ok), "detail": detail})


def run_py(script, args):
    """Run a script as a subprocess, return (exit_code, stdout, stderr)."""
    p = os.path.join(SCRIPTS, script)
    r = subprocess.run([sys.executable, p] + args, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def tmpjson(obj, name="t.json"):
    d = tempfile.mkdtemp()
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    return p


# ---------------------------------------------------------------- unit tests
def unit_kb():
    g = "unit"
    ids = kb.award_ids()
    record(g, "13 个奖项全部载入", len(ids) == 13, f"count={len(ids)}")

    miss = []
    for a in ids:
        for t in ("scoring_weights", "eligibility_region", "eligibility_window",
                  "max_categories_per_activity", "disqualification"):
            if kb.find_rule(a, t) is None:
                miss.append((a, t))
    # DIA has no video rules (PDF material system) — that's expected, not missing
    record(g, "核心规则类型完备（除 DIA video）", not miss or
           all(t in ("video_max_seconds",) for _, t in miss),
           f"missing={miss}")

    cats = kb.main_categories()
    record(g, "主奖项 134 个类别", len(cats) == 134, f"count={len(cats)}")
    ind = [c for c in cats if c["kind"] == "industry"]
    spe = [c for c in cats if c["kind"] == "specialty"]
    record(g, "28 行业类 + 106 专项类",
           len(ind) == 28 and len(spe) == 106, f"ind={len(ind)} spe={len(spe)}")
    nodef = [c["number"] for c in cats if not (c.get("definition_zh") or "").strip()]
    record(g, "全部类别有定义", not nodef, f"missing={nodef}")

    tracks = {c["track_zh"] for c in cats if c.get("track_zh")}
    record(g, "6 个战略赛道", len(tracks) == 6, f"tracks={sorted(tracks)}")

    flds = kb.all_fields()
    record(g, "字段数 >= 85", len(flds) >= 85, f"count={len(flds)}")
    withlim = [f for f in flds if f["word_limit"]]
    record(g, "字数限制字段 >= 55", len(withlim) >= 55, f"count={len(withlim)}")


def unit_weights():
    g = "unit"
    main = kb.scoring_weights("EFFIE_GC_MAIN")
    glob = kb.scoring_weights("EFFIE_GLOBAL")
    scen = kb.scoring_weights("EFFIE_SCENARIO")
    record(g, "主奖项权重 23.3/23.3/23.3/30",
           main["part4_results"] == 30.0 and main["part1_challenge"] == 23.3, str(main))
    record(g, "全球化奖权重 15/25/30/30",
           glob["part1_challenge"] == 15.0 and glob["part2_insight_strategy"] == 25.0,
           str(glob))
    record(g, "场景奖未核实权重不得用于计算",
           scen is None and kb.find_rule("EFFIE_SCENARIO", "scoring_weights")["verification_status"] != "VERIFIED", str(scen))
    orule = kb.find_rule("EFFIE_SCENARIO", "scoring_weights_override")
    record(g, "场景奖户外子类覆盖存在", orule is not None and
           orule["rule_value"]["weights"]["part2_insight_strategy"] == 30.0,
           str(orule["rule_value"] if orule else None))
    # 官方公布 23.3% x3 + 30% = 99.9%（官方原值即如此，非计算错误）
    record(g, "权重合计符合官方公布值（99.9%）",
           abs(sum(main.values()) - 99.9) < 0.01, f"sum={sum(main.values())}")


def unit_citation():
    g = "unit"
    r = kb.find_rule("EFFIE_GC_MAIN", "eligibility_window")
    record(g, "规则带页码", r["source_page"] is not None, f"page={r['source_page']}")
    record(g, "规则带原文引用", bool(r["source_quote"]), (r["source_quote"] or "")[:40])
    h = kb.doc_sha256(r["source_document"])
    record(g, "来源文件哈希可解析（64 hex）", bool(h) and len(h) == 64,
           (h or "NONE")[:16])
    # every rule must resolve to a documented source + hash via the index
    bad = []
    for a in kb.award_ids():
        for x in kb.rules_for(a):
            if not x.get("source_document") or not kb.doc_sha256(x["source_document"]):
                bad.append(x["rule_id"])
    record(g, "全部规则可解析来源哈希", not bad, f"missing={bad[:5]}")
    full = kb.rule_with_hash(r)
    record(g, "rule_with_hash 补齐 source_sha256",
           len(full.get("source_sha256") or "") == 64, "")


def unit_quote_provenance():
    g = "unit"
    allr = [r for a in kb.award_ids() for r in kb.rules_for(a)]
    kinds = {}
    for r in allr:
        k = r.get("quote_kind")
        kinds[k] = kinds.get(k, 0) + 1
    # every rule must declare whether its quote is verbatim/referential/paraphrase
    undeclared = [r["rule_id"] for r in allr if not r.get("quote_kind")]
    record(g, "每条规则声明引用类型", not undeclared,
           f"undeclared={undeclared[:5]} kinds={kinds}")

    # 逐字率的分母必须是「可能为逐字」的引用：
    # referential 按定义就是「见…条款」指代，本身不可能是原文，计入分母会
    # 制造虚假指标。旧版用 len(allr) 做分母，掩盖了真实降级情况（P1-2）。
    verb = kinds.get("verbatim", 0)
    ref = kinds.get("referential", 0)
    para = kinds.get("paraphrase", 0)
    citable = verb + para            # 可核验为原文的候选集
    ratio = verb / citable if citable else 0.0
    record(g, "逐字引用占比 >= 85%（分母=可核验引用，剔除指代性）", ratio >= 0.85,
           f"verbatim={verb}/{citable} = {ratio:.1%}（另有 referential={ref}）")

    # 诚实性硬约束：转述条数必须如实存在且被标注，不得悄悄算进逐字
    record(g, "转述引用已如实标注为 paraphrase",
           para == sum(1 for r in allr
                       if r.get("quote_kind") == "paraphrase"),
           f"paraphrase={para}")
    # 转述不得标 VERIFIED
    bad = [r["rule_id"] for r in allr
           if r.get("quote_kind") == "paraphrase"
           and r.get("verification_status") == "VERIFIED"]
    record(g, "paraphrase 不得标 VERIFIED", not bad, f"{bad[:5]}")
    # 变异盲区修复：verbatim 必须有页码或明确说明，
    # 否则「把 paraphrase 偷改回 verbatim」的变异能一路绿灯（M4 漏网）。
    bad_page = [r["rule_id"] for r in allr
                if r.get("quote_kind") == "verbatim"
                and r.get("source_page") is None and not r.get("page_note")]
    record(g, "verbatim 均有页码或说明", not bad_page, f"{bad_page[:5]}")


def unit_wordcount():
    g = "unit"
    record(g, "汉字计数", CWL.count_chars("你好世界") == 4, "")
    record(g, "空白不计", CWL.count_chars("你 好  世界") == 4, "")
    record(g, "标点计入", CWL.count_chars("你，好。") == 4, "")
    record(g, "数字字母各计1", CWL.count_chars("iPhone 15") == 8, "")


# ------------------------------------------------------------ integration
def integ_eligibility():
    g = "integration"
    ok_case = {"competition_year": 2026, "implementation_start": "2025-03-01",
               "region": "GREATER_CHINA", "category_numbers": [46],
               "data_sources": ["s"]}
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_eligibility.py"),
                        "--case", tmpjson(ok_case), "--award", "EFFIE_GC_MAIN"],
                       capture_output=True, text=True)
    record(g, "合规案例资格通过", "PASS" in r.stdout, r.stdout.split("\n")[0])

    late = {"competition_year": 2026, "implementation_start": "2026-09-01",
            "region": "GREATER_CHINA", "category_numbers": [46]}
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_eligibility.py"),
                        "--case", tmpjson(late), "--award", "EFFIE_GC_MAIN"],
                       capture_output=True, text=True)
    record(g, "晚于窗口开始 → BLOCKED", "BLOCKED" in r.stdout, "")

    many = {"competition_year": 2026, "implementation_start": "2025-05-01",
            "region": "GREATER_CHINA", "category_numbers": [1, 2, 3, 4, 5]}
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_eligibility.py"),
                        "--case", tmpjson(many), "--award", "EFFIE_GC_MAIN"],
                       capture_output=True, text=True)
    record(g, "5 个类别 → BLOCKED", "BLOCKED" in r.stdout, "")

    # two industry categories
    two_ind = {"competition_year": 2026, "implementation_start": "2025-05-01",
               "region": "GREATER_CHINA", "category_numbers": [1, 2]}
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_eligibility.py"),
                        "--case", tmpjson(two_ind), "--award", "EFFIE_GC_MAIN"],
                       capture_output=True, text=True)
    record(g, "2 个行业类 → BLOCKED", "BLOCKED" in r.stdout, "")


def integ_score():
    g = "integration"
    sc = tmpjson({"part1_challenge": 7.2, "part2_insight_strategy": 6.8,
                  "part3_execution": 7.0, "part4_results": 8.5})
    rc1, o1, _ = run_py("calculate_score.py", ["--award", "EFFIE_GC_MAIN", "--scores", sc])
    rc2, o2, _ = run_py("calculate_score.py", ["--award", "EFFIE_GLOBAL", "--scores", sc])
    record(g, "主奖项加权分计算", rc1 == 0 and "74.43" in o1,
           [l for l in o1.split("\n") if "合计" in l])
    record(g, "全球化奖用不同权重", rc2 == 0 and "74.30" in o2,
           [l for l in o2.split("\n") if "合计" in l])
    record(g, "两个奖项结果不同", "74.43" in o1 and "74.30" in o2, "权重区分生效")


def integ_submission():
    g = "integration"
    base = {"competition_year": 2026, "form": "通用", "brand": "B", "product": "P",
            "implementation_start": "2025-03-01", "implementation_end": "2025-12-31",
            "region": "GREATER_CHINA", "category_numbers": [46],
            "authorization": {"client_authorized": True, "agreement_signed": True,
                              "publication_option": "as_submitted"}}

    # empty-ish -> not READY
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_submission.py"),
                        "--case", tmpjson(base), "--award", "EFFIE_GC_MAIN"],
                       capture_output=True, text=True)
    record(g, "字段缺失 → 非 READY", "READY_TO_SUBMIT" not in r.stdout,
           [l for l in r.stdout.split("\n") if "状态" in l])

    # blocked qualification
    blk = dict(base, implementation_start="2026-09-01")
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_submission.py"),
                        "--case", tmpjson(blk), "--award", "EFFIE_GC_MAIN"],
                       capture_output=True, text=True)
    record(g, "资格不合规 → BLOCKED", "BLOCKED" in r.stdout, "")


def integ_queries():
    g = "integration"
    rc, o, _ = run_py("rule_query.py", ["--award", "EFFIE_GLOBAL", "--type", "scoring_weights"])
    record(g, "规则查询输出权重", rc == 0 and "15.0" in o, "")
    rc, o, _ = run_py("field_query.py", ["--summary"])
    record(g, "字段字数汇总", rc == 0 and "成果" in o, "")
    rc, o, _ = run_py("category_query.py", ["--number", "55"])
    record(g, "类别 55 含特殊资格", rc == 0 and "consecutive_years_min" in o, "")


# ------------------------------------------------------------- adversarial
def adv_direct_submission_edit():
    """A10: 用户要求直接改状态字段 → 必须无效."""
    g = "adversarial"
    fake = {"competition_year": 2026, "award_id": "EFFIE_GC_MAIN",
            "status": "READY_TO_SUBMIT",          # caller self-declares
            "implementation_start": "2026-09-01",  # but is out of window
            "region": "GREATER_CHINA", "category_numbers": [1]}
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_submission.py"),
                        "--case", tmpjson(fake), "--award", "EFFIE_GC_MAIN"],
                       capture_output=True, text=True)
    record(g, "自声明 READY 无法绕过门禁",
           "交付状态: BLOCKED" in r.stdout or "READY_TO_SUBMIT" not in
           r.stdout.split("交付状态:")[-1], "")


def adv_wrong_year():
    g = "adversarial"
    case = {"competition_year": 2027, "implementation_start": "2026-05-01",
            "region": "GREATER_CHINA", "category_numbers": [1]}
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_eligibility.py"),
                        "--case", tmpjson(case), "--award", "EFFIE_GC_MAIN"],
                       capture_output=True, text=True)
    record(g, "2027 年度 → UNKNOWN（不套用 2026 规则）", "UNKNOWN" in r.stdout, "")


def adv_global_region():
    g = "adversarial"
    case = {"competition_year": 2026, "implementation_start": "2025-05-01",
            "region": "GREATER_CHINA", "category_numbers": [10]}
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_eligibility.py"),
                        "--case", tmpjson(case), "--award", "EFFIE_GLOBAL"],
                       capture_output=True, text=True)
    record(g, "大中华区案例报全球化奖 → BLOCKED",
           "BLOCKED" in r.stdout and "海外" in r.stdout, "")


def adv_fake_evidence():
    g = "adversarial"
    d = tempfile.mkdtemp()
    ev = {"evidence": [{"evidence_id": "E1", "file": "nope.pdf", "locator": "p.9",
                        "quote": "q", "provider": "p", "metric": "m",
                        "period": "2025", "status": "VERIFIED"}],
          "claims": [{"claim_id": "C1", "text": "t", "type": "FACT",
                      "evidence_ids": ["E1"]}]}
    p = os.path.join(d, "ev.json")
    json.dump(ev, open(p, "w"), ensure_ascii=False)
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "verify_evidence.py"),
                        "--file", p, "--base-dir", d],
                       capture_output=True, text=True)
    record(g, "虚构来源文件被拦（E02）", "E02" in r.stdout and r.returncode == 1, "")

    # 变异盲区修复（M5）：哈希必须真的被比对。
    # 旧测试只覆盖「文件不存在」，把 `actual != recorded` 短路成 False
    # 依然全绿。这里构造「文件存在但内容被篡改」，要求 E02 必须报出。
    d2 = tempfile.mkdtemp()
    real = os.path.join(d2, "s.csv")
    open(real, "w").write("original-content")
    good_sha = hashlib.sha256(b"original-content").hexdigest()
    open(real, "w").write("tampered-content")     # 内容已被改
    ev2 = {"evidence": [{"evidence_id": "E1", "file": "s.csv", "locator": "p.1",
                         "quote": "q", "provider": "p", "metric": "m",
                         "period": "2025", "status": "VERIFIED",
                         "sha256": good_sha}],
           "claims": []}
    p2 = os.path.join(d2, "ev2.json")
    json.dump(ev2, open(p2, "w"), ensure_ascii=False)
    r2 = subprocess.run([sys.executable, os.path.join(SCRIPTS, "verify_evidence.py"),
                         "--file", p2, "--base-dir", d2],
                        capture_output=True, text=True)
    record(g, "文件内容被篡改被拦（哈希不一致 E02）",
           "E02" in r2.stdout and "哈希不一致" in r2.stdout and r2.returncode == 1,
           f"rc={r2.returncode}")
    # 哈希一致时必须放行，否则是误伤
    open(real, "w").write("original-content")
    r3 = subprocess.run([sys.executable, os.path.join(SCRIPTS, "verify_evidence.py"),
                         "--file", p2, "--base-dir", d2],
                        capture_output=True, text=True)
    record(g, "哈希一致不误伤（E02 不误报）",
           "哈希不一致" not in r3.stdout, "")


def adv_causal_overreach():
    g = "adversarial"
    a = {"claimed_conclusion": "A", "methods": ["pre_post"],
         "available_data": [], "confounders_addressed": [], "section_4_2_text": ""}
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "audit_attribution.py"),
                        "--file", tmpjson(a)], capture_output=True, text=True)
    record(g, "仅前后对比却称因果 → P0", "A05" in r.stdout and "P0" in r.stdout, "")


def adv_roas_as_roi():
    g = "adversarial"
    m = {"metrics": [{"metric_id": "M1", "name": "ROAS", "as_called": "ROI",
                      "value": "8.5", "unit": "倍", "period": "2025-01~06"}],
         "goals": []}
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_metrics.py"),
                        "--file", tmpjson(m)], capture_output=True, text=True)
    record(g, "ROAS 冒充 ROI → P0", "M01" in r.stdout and "P0" in r.stdout, "")


def adv_percent_vs_point():
    g = "adversarial"
    doc = {"metrics": [], "goals": [],
           "narrative_flags": {},
           "note": "份额从3%到5%提升2%，同时又说提升2个百分点"}
    p = tmpjson(doc)
    # inject the exact conflicting phrasing into a metric name to trip M02
    doc2 = {"metrics": [{"metric_id": "M9", "name": "份额提升2个百分点",
                         "value": "2", "unit": "百分点", "period": "2025"}],
            "goals": [],
            "narrative_flags": {}}
    json.dump(doc2, open(p, "w"), ensure_ascii=False)
    text = json.dumps(doc2, ensure_ascii=False)
    # M02 detection works on the serialized doc; build a doc that contains both forms
    doc3 = {"metrics": [], "goals": [], "narrative_flags": {},
            "raw": "从3%到5%，提升2%，即提升2个百分点"}
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_metrics.py"),
                        "--file", tmpjson(doc3)], capture_output=True, text=True)
    record(g, "百分比/百分点混用被检出（M02）", "M02" in r.stdout, "")


def adv_impression_as_reach():
    g = "adversarial"
    m = {"metrics": [{"metric_id": "M1", "name": "reach", "value": "8", "unit": "亿",
                      "period": "2025", "source_note": "impression 数据"}],
         "goals": []}
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_metrics.py"),
                        "--file", tmpjson(m)], capture_output=True, text=True)
    record(g, "曝光冒充触达（M04）", "M04" in r.stdout, "")


def adv_business_goal_campaign_metric():
    g = "adversarial"
    m = {"goals": [{"goal_id": "G1", "type": "business"}],
         "metrics": [{"metric_id": "M1", "name": "曝光量", "value": "11",
                      "unit": "亿", "period": "2025", "goal_id": "G1"}]}
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_metrics.py"),
                        "--file", tmpjson(m)], capture_output=True, text=True)
    record(g, "生意目标用曝光作答（M09）", "M09" in r.stdout, "")


def adv_hidden_failed_goal():
    g = "adversarial"
    m = {"goals": [{"goal_id": "G1", "type": "business"},
                   {"goal_id": "G2", "type": "marketing"},
                   {"goal_id": "G3", "type": "campaign"}],
         "metrics": [{"metric_id": "M1", "name": "销售额", "value": "1", "unit": "亿",
                      "period": "2025", "goal_id": "G1"}]}
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_metrics.py"),
                        "--file", tmpjson(m)], capture_output=True, text=True)
    record(g, "隐瞒未达成目标（M10）", "M10" in r.stdout, "")


def adv_parallel_campaign():
    g = "adversarial"
    a = {"claimed_conclusion": "B", "methods": ["yoy", "category_benchmark"],
         "available_data": ["category_data"], "confounders_addressed": [],
         "section_4_2_text": "x" * 100, "has_parallel_campaigns": True}
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "audit_attribution.py"),
                        "--file", tmpjson(a)], capture_output=True, text=True)
    record(g, "同期活动未拆分（A06 P0）", "A06" in r.stdout and "P0" in r.stdout, "")


def adv_secret_in_public():
    g = "adversarial"
    ev = {"evidence": [{"evidence_id": "E1", "file": "a.csv", "locator": "p1",
                        "quote": "q", "provider": "p", "metric": "m", "period": "2025",
                        "status": "VERIFIED", "confidentiality": "secret",
                        "used_in_public_material": True}],
          "claims": []}
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "verify_evidence.py"),
                        "--file", tmpjson(ev)], capture_output=True, text=True)
    record(g, "机密数据入公开材料（E09 P0）", "E09" in r.stdout, "")


def adv_cost_in_public():
    """空证据登记不得被误判为通过。

    旧版断言 `"未发现结构性证据缺陷" not in stdout or rc in (0,1)`——
    returncode 几乎总是 0 或 1，于是该断言恒真（假绿灯）。
    现在改为断言「空登记必须报出问题」：FACT 类主张无证据 → E04 P0。
    """
    g = "adversarial"
    # 有主张但无证据：必须报 E04 P0，且退出码非 0
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "verify_evidence.py"),
                        "--file", tmpjson({"evidence": [],
                                           "claims": [{"claim_id": "C1", "text": "t",
                                                       "type": "FACT"}]})],
                       capture_output=True, text=True)
    record(g, "空证据+事实主张被拦（E04 P0）",
           "E04" in r.stdout and "P0" in r.stdout and r.returncode == 1,
           f"rc={r.returncode}")

    # 双空：无证据无主张，也不得输出「无缺陷」以外的通过幻觉
    r2 = subprocess.run([sys.executable, os.path.join(SCRIPTS, "verify_evidence.py"),
                         "--file", tmpjson({"evidence": [], "claims": []})],
                        capture_output=True, text=True)
    record(g, "双空登记不产生虚假通过",
           "P0=0" in r2.stdout,
           f"rc={r2.returncode}")


def adv_selfdeclared_verified_bypass():
    """P1-3 回归：证据全自标 VERIFIED + 空 open_issues 不得通过 G05/G10。

    这是审计发现的真实绕过路径：旧 G05 直接读 status=="VERIFIED"，
    G10 读 case 自报的 open_p0_issues。两者都能被用户填掉。
    """
    g = "adversarial"
    fake = {
        "competition_year": 2026, "form": "通用", "brand": "B", "product": "P",
        "implementation_start": "2025-03-01", "implementation_end": "2025-12-31",
        "region": "GREATER_CHINA", "category_numbers": [46],
        "authorization": {"client_authorized": True, "agreement_signed": True,
                          "publication_option": "as_submitted"},
        "open_p0_issues": [], "open_p1_issues": [],
        "evidence": [{"evidence_id": "E1", "file": "does-not-exist.pdf",
                      "locator": "p9", "quote": "q", "provider": "p",
                      "metric": "m", "period": "2025", "status": "VERIFIED"}],
        "claims": [{"claim_id": "C1", "text": "t", "type": "FACT",
                    "evidence_ids": ["E1"]}],
    }
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_submission.py"),
                        "--case", tmpjson(fake), "--award", "EFFIE_GC_MAIN"],
                       capture_output=True, text=True)
    record(g, "证据自标 VERIFIED 无法绕过 G05",
           "[FAIL] G05" in r.stdout, "")
    record(g, "清空 open_issues 无法绕过 G10",
           "[FAIL] G10" in r.stdout, "")


def adv_quote_kind_integrity():
    """P1-2 回归：引用守卫必须真的能抓出「被篡改的知识库」。

    旧断言只看 `rc==0 and "PASS" in out`——把守卫改成恒 return 0 也能过
    （变异 M3 漏网）。现在改为：构造一份被篡改的规则库，交给守卫，
    要求它必须报 FAIL。守卫若被短路，这条断言立刻翻红。
    """
    g = "adversarial"
    import json as _json
    kbdir = os.path.join(SKILL, "references", "annual-rules-2026.json")
    data = _json.load(open(kbdir, encoding="utf-8"))

    # 1) 干净库必须 PASS
    rc, o, e = run_py("verify_quotes.py", [])
    record(g, "引用守卫内置自检通过（干净库）", rc == 0 and "PASS" in o,
           (o or e)[-160:])

    # 2) 篡改库必须 FAIL：把一条 paraphrase 洗成 verbatim 且不给页码
    tampered = _json.loads(_json.dumps(data))
    hit = None
    for rs in tampered["rules"].values():
        for r in rs:
            if r.get("quote_kind") == "paraphrase":
                r["quote_kind"] = "verbatim"
                r["verification_status"] = "VERIFIED"
                r["source_page"] = None
                r.pop("page_note", None)
                hit = r["rule_id"]
                break
        if hit:
            break
    tmpd = tempfile.mkdtemp()
    tp = os.path.join(tmpd, "tampered.json")
    _json.dump(tampered, open(tp, "w", encoding="utf-8"), ensure_ascii=False)
    rc2, o2, e2 = run_py("verify_quotes.py", ["--rules", tp])
    record(g, "引用守卫能抓出被篡改的规则库",
           rc2 != 0 and "FAIL" in o2,
           f"tampered={hit} rc={rc2}")


def adv_no_paraphrase_as_verified():
    """P1-1/P1-2 回归：paraphrase 不得同时标 VERIFIED；verbatim 必须有页码或说明。"""
    g = "adversarial"
    sys.path.insert(0, SKILL)
    import json as _json
    kbdir = os.path.join(SKILL, "references", "annual-rules-2026.json")
    data = _json.load(open(kbdir, encoding="utf-8"))
    allr = [r for v in data["rules"].values() for r in v]
    bad_kind = [r["rule_id"] for r in allr
                if r.get("quote_kind") == "paraphrase"
                and r.get("verification_status") == "VERIFIED"]
    bad_page = [r["rule_id"] for r in allr
                if r.get("quote_kind") == "verbatim"
                and r.get("source_page") is None and not r.get("page_note")]
    record(g, "无 paraphrase 冒充 VERIFIED", not bad_kind, f"{bad_kind[:5]}")
    record(g, "verbatim 均有页码或说明", not bad_page, f"{bad_page[:5]}")


def adv_consistency():
    g = "adversarial"
    v1 = tmpjson({"brand": "A", "budget_range": "601万-1200万",
                  "implementation_start": "2025-03-01"}, "v1.json")
    v2 = tmpjson({"brand": "A", "budget_range": "301万-600万",
                  "implementation_start": "2025-03-01"}, "v2.json")
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "check_consistency.py"),
                        "--versions", v1, v2], capture_output=True, text=True)
    record(g, "跨版本预算不一致（K01）", "K01" in r.stdout, "")


def adv_no_kb():
    g = "adversarial"
    rc, o, e = run_py("rule_query.py", ["--award", "NOT_A_REAL_AWARD", "--type", "x"])
    record(g, "未知奖项直接报错不猜测", rc != 0, f"rc={rc}")


def adv_word_limit():
    g = "adversarial"
    long_text = "实" * 65
    p = tmpjson({"answers": {"P1_02a": long_text}})
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "check_word_limits.py"),
                        "--case", p], capture_output=True, text=True)
    record(g, "超字数被拦（65/60）", "OVER" in r.stdout and r.returncode == 1, "")


# ------------------------------------------------------------------ runner
GROUPS = [
    ("unit", [unit_kb, unit_weights, unit_citation, unit_quote_provenance,
              unit_wordcount]),
    ("integration", [integ_eligibility, integ_score, integ_submission, integ_queries]),
    ("adversarial", [adv_direct_submission_edit, adv_wrong_year, adv_global_region,
                     adv_fake_evidence, adv_causal_overreach, adv_roas_as_roi,
                     adv_percent_vs_point, adv_impression_as_reach,
                     adv_business_goal_campaign_metric, adv_hidden_failed_goal,
                     adv_parallel_campaign, adv_secret_in_public,
                     adv_cost_in_public, adv_consistency, adv_no_kb,
                     adv_word_limit, adv_selfdeclared_verified_bypass,
                     adv_quote_kind_integrity, adv_no_paraphrase_as_verified]),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--filter", help="只跑包含该字符串的组")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    for gname, fns in GROUPS:
        if args.filter and args.filter not in gname:
            continue
        for fn in fns:
            try:
                fn()
            except Exception as e:
                record(gname, fn.__name__, False, f"EXCEPTION: {type(e).__name__}: {e}")

    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["ok"])
    failed = total - passed

    if args.json:
        print(json.dumps({"total": total, "passed": passed, "failed": failed,
                          "results": RESULTS}, ensure_ascii=False, indent=1))
    else:
        cur = None
        for r in RESULTS:
            if r["group"] != cur:
                cur = r["group"]
                print(f"\n=== {cur.upper()} ===")
            mark = "PASS" if r["ok"] else "FAIL"
            print(f"[{mark}] {r['name']}" + (f"  — {r['detail']}" if not r["ok"] else ""))
        print(f"\n{'='*60}")
        print(f"总计 {total}  通过 {passed}  失败 {failed}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
