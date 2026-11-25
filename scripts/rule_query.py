#!/usr/bin/env python3
"""查询 2026 官方规则条目，一律带出处。

用法:
  rule_query.py --award EFFIE_GC_MAIN --type scoring_weights
  rule_query.py --award EFFIE_GLOBAL --list-types
  rule_query.py --award EFFIE_SCENARIO --all
  rule_query.py --awards            # 列出全部奖项
"""
from __future__ import annotations

import argparse
import json
import sys

import kb


def main() -> int:
    ap = argparse.ArgumentParser(description="查询 2026 艾菲规则")
    ap.add_argument("--award", help="award_id，如 EFFIE_GC_MAIN")
    ap.add_argument("--type", help="rule_type，如 scoring_weights")
    ap.add_argument("--all", action="store_true", help="输出该奖项全部规则")
    ap.add_argument("--list-types", action="store_true", help="列出该奖项可用 rule_type")
    ap.add_argument("--awards", action="store_true", help="列出全部奖项")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = ap.parse_args()

    if args.awards:
        for a in kb.awards():
            print(f"{a['award_id']:20s} {a['award_name_zh']:14s} "
                  f"rules={a['rules']:3d} region={a['region_scope']}")
        return 0

    if not args.award:
        ap.print_help()
        return 2
    kb.require_award(args.award)

    if args.list_types:
        types = sorted({r["rule_type"] for r in kb.rules_for(args.award)})
        for t in types:
            n = sum(1 for r in kb.rules_for(args.award) if r["rule_type"] == t)
            print(f"{t:40s} x{n}")
        return 0

    if args.all:
        payload = kb.rules_for(args.award)
    elif args.type:
        payload = [r for r in kb.rules_for(args.award) if r["rule_type"] == args.type]
        if not payload:
            print(f"[MISSING] {args.award} 无 rule_type={args.type} 的规则。"
                  f"\n可用类型见 --list-types", file=sys.stderr)
            return 1
    else:
        ap.print_help()
        return 2

    payload = [kb.rule_with_hash(r) for r in payload]

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    for r in payload:
        print(f"■ {r['rule_type']}  [{r['rule_id']}]")
        print(f"  值: {json.dumps(r['rule_value'], ensure_ascii=False)}")
        page = r.get("source_page")
        print(f"  来源: {r['source_document']} P{page}" if page
              else f"  来源: {r['source_document']}（无页码，禁止编造页码）")
        qk = r.get("quote_kind", "")
        if qk == "verbatim":
            print(f"  原文（可加引号引用）: {r['source_quote']}")
        elif qk == "referential":
            print(f"  指代性引用（须改写为转述，不得冒充原文）: {r['source_quote']}")
        else:
            print(f"  转述（来源文档无此原句，不得加引号称官方原文）: {r['source_quote']}")
        print(f"  状态: {r['verification_status']} / {r['enforcement_level']}")
        if r.get("verification_status") == "UNVERIFIED":
            print("  ⚠ 该规则未通过原文核验，不得用于正式资格判定；须回官方文件核对。")
        if r.get("citation_issue"):
            print(f"  引用提示: {r['citation_issue']}")
        if r.get("page_note"):
            print(f"  页码说明: {r['page_note']}")
        h = r.get("source_sha256") or ""
        if h:
            print(f"  引用类型: {qk}   文件哈希: {h[:16]}…")
        if r.get("note"):
            print(f"  说明: {r['note']}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
