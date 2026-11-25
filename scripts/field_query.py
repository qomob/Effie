#!/usr/bin/env python3
"""参赛表字段查询：字数上限、图表上限、必填性、官方提问原文。

用法:
  field_query.py --part 4
  field_query.py --id P1_01
  field_query.py --limits              # 只列有字数限制的字段（写稿用）
  field_query.py --summary             # 各部分字数总量
"""
from __future__ import annotations

import argparse
import json
import sys

import kb


def main() -> int:
    ap = argparse.ArgumentParser(description="参赛表字段查询")
    ap.add_argument("--part", help="部分编号：0/1/2/3/3i/4/pub 或中文名片段")
    ap.add_argument("--id")
    ap.add_argument("--form", default="通用")
    ap.add_argument("--limits", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    fs = kb.all_fields(form=args.form) if args.form != "all" else kb.all_fields()

    if args.id:
        f = kb.field_by_id(args.id)
        if not f:
            print(f"未找到字段 {args.id}")
            return 3
        print(json.dumps(f, ensure_ascii=False, indent=2) if args.json else "")
        if not args.json:
            print(f"■ {f['field_id']}  {f['label_zh']}")
            print(f"  部分: {f['part_name']}   必填: {'是' if f['required'] else '否'}")
            print(f"  字数上限: {f['word_limit'] if f['word_limit'] else '无'}")
            print(f"  图表上限: {f['chart_limit'] if f['chart_limit'] else '无'}")
            if f.get("official_prompt"):
                print(f"  官方提示: {f['official_prompt']}")
            print(f"  来源: {f['source_document']}")
        return 0

    if args.summary:
        from collections import defaultdict
        agg = defaultdict(lambda: {"fields": 0, "with_limit": 0, "max_chars": 0})
        for f in kb.all_fields():
            k = f["part_name"]
            agg[k]["fields"] += 1
            if f["word_limit"]:
                agg[k]["with_limit"] += 1
                # count max-possible (all optional goals filled)
                agg[k]["max_chars"] += f["word_limit"]
        print(f"{'部分':24s}{'字段数':>6s}{'有限字段':>8s}{'字数上限合计':>12s}")
        print("-" * 54)
        for k, v in agg.items():
            print(f"{k:24s}{v['fields']:>6d}{v['with_limit']:>8d}{v['max_chars']:>12d}")
        total = sum(v["max_chars"] for v in agg.values())
        print("-" * 54)
        print(f"{'合计（含全部选填目标）':24s}{'':>14s}{total:>12d}")
        print("\n注：选填目标#2/#3 若不填，实际字数上限低于上表。")
        return 0

    if args.limits:
        for f in fs:
            if f["word_limit"]:
                ch = f" / {f['chart_limit']}图" if f["chart_limit"] else ""
                print(f"{f['field_id']:14s} {f['label_zh'][:30]:32s} "
                      f"≤{f['word_limit']:>4d}字{ch}")
        return 0

    if args.part:
        sel = [f for f in fs if str(f["part"]) == args.part
               or args.part in f["part_name"]]
        if not sel:
            parts = sorted({f"{f['part']}={f['part_name']}" for f in fs})
            print(f"未匹配部分 {args.part}。可用: {parts}")
            return 3
        for f in sel:
            wl = f"≤{f['word_limit']}字" if f["word_limit"] else "无字数限制"
            cl = f"，≤{f['chart_limit']}图" if f["chart_limit"] else ""
            req = "必填" if f["required"] else "选填"
            print(f"{f['field_id']:14s} {f['label_zh'][:34]:36s} {wl}{cl}  [{req}]")
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
