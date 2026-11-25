#!/usr/bin/env python3
"""证据登记与真实性审计（M06）。

不是"检查字段有没有填"，而是:
  E01 证据必填字段完整性
  E02 文件哈希与实际文件是否一致
  E03 引用位置是否存在（页码/工作表/锚点可定位）
  E04 主张是否绑定证据，证据是否真的支持该主张
  E05 数值/单位/周期/对象一致性
  E06 同一 evidence_id 是否冒充多个独立来源
  E07 证据之间是否互相矛盾
  E08 证据强度是否足以支撑结论层级
  E09 保密/公开状态与材料类型是否冲突

用法:
  verify_evidence.py --file evidence.json --base-dir /path/to/materials
  verify_evidence.py --file evidence.json --json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

REQUIRED_EV_FIELDS = [
    "evidence_id", "file", "locator", "quote", "provider",
    "metric", "period", "status",
]

VALID_STATUS = {"VERIFIED", "PARTIALLY_SUPPORTED", "USER_ASSERTED",
                "UNVERIFIED", "CONTRADICTED", "MISSING", "PENDING_LOCAL_CHECK"}

STRENGTH_BY_LEVEL = {
    "audited": 5, "experiment": 5, "model": 4,
    "third_party_research": 4, "platform_data": 3,
    "internal_system": 2, "internal_ppt": 1,
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def audit(doc: dict, base_dir: str | None = None) -> list[tuple]:
    """对证据登记文档做九项审计，返回 findings 列表。

    抽成独立函数，供 validate_submission.py 的 G05 门禁复核调用——
    门禁不得采信 case 里自报的 evidence[].status。
    """
    evidence = {e.get("evidence_id"): e for e in (doc.get("evidence") or [])}
    claims = doc.get("claims") or []
    findings = []

    def add(code, sev, target, issue, fix):
        findings.append((code, sev, target, issue, fix))

    # ---- E01 required fields ---------------------------------------------
    for eid, e in evidence.items():
        miss = [f for f in REQUIRED_EV_FIELDS if not e.get(f)]
        if miss:
            add("E01", "P1", eid, f"证据记录缺必填字段: {miss}",
                "补齐后执行真实文件核验，不能自标认证")
        st = e.get("status")
        if st not in VALID_STATUS:
            add("E01", "P1", eid, f"非法 status={st}", f"应为 {sorted(VALID_STATUS)} 之一")
        if st == "VERIFIED" and miss:
            add("E10", "P0", eid,
                "标记 VERIFIED 但关键字段缺失——登记不等于验证",
                "字段不全只能标 UNVERIFIED")

    # ---- E02 hash check ---------------------------------------------------
    if base_dir:
        for eid, e in evidence.items():
            fn = e.get("file")
            if not fn:
                continue
            path = os.path.realpath(os.path.join(base_dir, fn))
            if os.path.isabs(fn) or os.path.commonpath([os.path.realpath(base_dir),path]) != os.path.realpath(base_dir):
                add("E02", "P0", eid, "文件路径逃逸", "使用材料目录内相对路径")
                continue
            if not os.path.isfile(path):
                add("E02", "P0", eid, f"引用的文件不存在: {fn}",
                    "确认真实文件；虚构来源属重大缺陷")
                continue
            recorded = e.get("sha256")
            if recorded:
                actual = sha256_file(path)
                if actual != recorded:
                    add("E02", "P0", eid,
                        f"文件哈希不一致（记录 {recorded[:12]}… 实际 {actual[:12]}…）",
                        "文件已被修改或记录错误；须重新核验内容")

    # ---- E03 locator -----------------------------------------------------
    for eid, e in evidence.items():
        loc = str(e.get("locator") or "")
        if loc and not any(ch.isdigit() for ch in loc):
            add("E03", "P2", eid, f"引用位置不具体: {loc}",
                "给出页码/工作表+单元格/时间码")

    # ---- E04 claim binding ------------------------------------------------
    for c in claims:
        cid = c.get("claim_id")
        if not cid:
            add("E04", "P1", "-", "存在无 claim_id 的主张", "每条主张须有唯一 ID")
            continue
        ev_ids = c.get("evidence_ids") or []
        if not ev_ids:
            if c.get("type") in ("FACT", "CALC"):
                add("E04", "P0", cid,
                    f"{c.get('type')} 类主张未绑定任何证据",
                    "绑定真实证据；未证声明/推断仅放草稿，不进入正式登记")
            continue
        for ev in ev_ids:
            if ev not in evidence:
                add("E04", "P0", cid, f"绑定了不存在的 evidence_id={ev}",
                    "修正绑定或补登该证据")
        if c.get("supports") is False:
            add("E04", "P0", cid, "所绑证据不支持该主张（supports=false）",
                "换用真正支持该主张的证据，或改写主张")

    # ---- E05 consistency -------------------------------------------------
    for c in claims:
        cid = c.get("claim_id", "?")
        for ev in (c.get("evidence_ids") or []):
            e = evidence.get(ev)
            if not e:
                continue
            for fld in (("scope",) if c.get("type")=="CALC" else ("value", "unit", "period", "scope")):
                cv, ev_v = c.get(fld), e.get(fld)
                if cv and ev_v and str(cv) != str(ev_v):
                    add("E05", "P1", cid,
                        f"{fld} 不一致：主张={cv} 证据={ev_v}",
                        "以原始证据为准修正主张，或说明换算关系")

    # ---- E06 one source masquerading as many -----------------------------
    file_count = {}
    for e in evidence.values():
        if e.get("status") in ("VERIFIED", "PARTIALLY_SUPPORTED"):
            file_count[e.get("file")] = file_count.get(e.get("file"), 0) + 1
    for fn, n in file_count.items():
        if n >= 3:
            add("E06", "P2", fn,
                f"同一文件被登记为 {n} 条独立证据",
                "若主张'多来源印证'则不成立；须说明是否为同一数据的不同呈现")

    # ---- E07 contradictions ----------------------------------------------
    for c in claims:
        cid = c.get("claim_id", "?")
        vals = set()
        for ev in (c.get("evidence_ids") or []):
            e = evidence.get(ev) or {}
            if e.get("value") is not None:
                vals.add(str(e.get("value")))
            if e.get("status") == "CONTRADICTED":
                add("E07", "P0", cid, f"证据 {ev} 被标为 CONTRADICTED",
                    "披露冲突并在 4.2 说明，或改用一致数据")
        if len(vals) > 1 and c.get("type")!="CALC":
            add("E07", "P0", cid, f"多条证据数值互相矛盾: {sorted(vals)}",
                "确定唯一口径，其余删除或注明差异原因")

    # ---- E08 evidence strength -------------------------------------------
    if doc.get("claimed_conclusion") in ("A", "B"):
        levels = {e.get("level") for e in evidence.values()
                  if e.get("status") == "VERIFIED"}
        strengths = [STRENGTH_BY_LEVEL.get(str(l).lower(), 0) for l in levels]
        if strengths and max(strengths) <= 2:
            add("E08", "P1", "-",
                "声称因果/较强贡献，但已核验证据最高仅为内部系统/PPT 级",
                "补第三方数据或实验，否则降级表述")

    # ---- E09 confidentiality ---------------------------------------------
    for eid, e in evidence.items():
        if e.get("confidentiality") in ("high", "secret") and \
           e.get("used_in_public_material"):
            add("E09", "P0", eid,
                "高保密数据被用于公开材料（创意视频/平面/案例概述/实效性声明）",
                "公开材料不得含机密；改用百分比/指数表达")

    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description="证据审计")
    ap.add_argument("--file", required=True, help="证据登记 JSON")
    ap.add_argument("--base-dir", default=None, help="原始材料所在目录（用于哈希校验）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        doc = json.load(open(args.file, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"读取失败: {e}", file=sys.stderr)
        return 2

    evidence = {e.get("evidence_id"): e for e in (doc.get("evidence") or [])}
    claims = doc.get("claims") or []
    findings = audit(doc, args.base_dir)
    # Strict local content audit complements historical structural diagnostics.
    import integrity
    strict_errors, matched, _ = integrity.evidence_audit(doc, args.base_dir)
    for error in strict_errors:
        findings.append(("E11", "P1", "-", error, "补原始文件、定位、哈希和主张绑定"))

    sev = {"P0": 0, "P1": 0, "P2": 0}
    for _, s, _, _, _ in findings:
        sev[s] = sev.get(s, 0) + 1

    if args.json:
        print(json.dumps({
            "evidence_count": len(evidence), "claim_count": len(claims),
            "findings": [{"code": c, "severity": s, "target": t,
                          "issue": i, "fix": f} for c, s, t, i, f in findings],
            "counts": sev,
            "local_matches": len(matched),
            "source_authenticity_verified": False,
            "hash_checked": bool(matched),
        }, ensure_ascii=False, indent=2))
    else:
        print(f"证据审计 · 证据 {len(evidence)} 条 / 主张 {len(claims)} 条")
        if args.base_dir:
            print(f"哈希校验目录: {args.base_dir}")
        else:
            print("未提供 --base-dir，本地证据契约未完成，不能通过")
        print("=" * 76)
        if not findings:
            print("本地结构与内容匹配检查未发现问题；来源真实性及语义仍须人工核验。")
        for c, s, t, i, f in findings:
            print(f"[{s}] {c} {t}: {i}")
            print(f"      → {f}")
        print("=" * 76)
        print(f"P0={sev.get('P0',0)}  P1={sev.get('P1',0)}  P2={sev.get('P2',0)}")
        if sev.get("P0"):
            print("存在 P0 级证据问题：不得声称'证据已验证'，也不得进入 READY_FOR_HUMAN_REVIEW。")

    return 1 if (sev.get("P0") or sev.get("P1")) else 0


if __name__ == "__main__":
    sys.exit(main())
