#!/usr/bin/env python3
"""逐字段字数核算 + 超限定位。

计数口径（保守，与官方"字"对齐）：
  - 每个汉字计 1
  - 每个全角标点计 1
  - 每个 ASCII 数字/字母计 1
  - 空白不计
  - 英文单词按字符计
官方未定义精确口径，本脚本对超限给出"保守判定"，并在接近上限时预警。

用法:
  check_word_limits.py --case case.json
  check_word_limits.py --case case.json --json --form 持续成功类
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata

import kb

WARN_RATIO = 0.95   # 达到 95% 上限时预警


def count_chars(text: str) -> int:
    """Conservative official-style character count."""
    n = 0
    for ch in text:
        if ch.isspace():
            continue
        n += 1
    return n


def count_han_only(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def main() -> int:
    ap = argparse.ArgumentParser(description="参赛表字数核查")
    ap.add_argument("--case", required=True, help="案例 JSON（含 answers: {field_id: text}）")
    ap.add_argument("--form", default="通用", help="通用 / 持续成功类")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        case = json.load(open(args.case, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"读取案例失败: {e}", file=sys.stderr)
        return 2

    answers = case.get("answers") or {}
    if not answers:
        print("案例中无 answers 字段", file=sys.stderr)
        return 2

    rows, over, near, unknown = [], [], [], []
    for fdef in kb.all_fields(form=args.form):
        fid = fdef["field_id"]
        text = answers.get(fid)
        if text is None:
            if fdef["required"]:
                rows.append({"field": fid, "label": fdef["label_zh"],
                             "status": "MISSING_REQUIRED", "count": 0,
                             "limit": fdef["word_limit"]})
            continue
        limit = fdef["word_limit"]
        cnt = count_chars(str(text))
        if limit is None:
            rows.append({"field": fid, "label": fdef["label_zh"],
                         "status": "NO_LIMIT", "count": cnt, "limit": None,
                         "han": count_han_only(str(text))})
            continue
        if cnt > limit:
            status = "OVER"
            over.append((fid, fdef["label_zh"], cnt, limit, cnt - limit))
        elif cnt >= limit * WARN_RATIO:
            status = "NEAR_LIMIT"
            near.append((fid, fdef["label_zh"], cnt, limit))
        else:
            status = "OK"
        rows.append({"field": fid, "label": fdef["label_zh"], "status": status,
                     "count": cnt, "limit": limit, "han": count_han_only(str(text))})

    # unknown field ids
    known = {f["field_id"] for f in kb.all_fields()}
    for fid in answers:
        if fid not in known:
            unknown.append(fid)

    missing_required = [r["field"] for r in rows if r["status"] == "MISSING_REQUIRED"]
    fail = bool(over) or bool(unknown)

    if args.json:
        print(json.dumps({"form": args.form, "over": [list(x) for x in over],
                          "near_limit": [list(x) for x in near],
                          "missing_required": missing_required,
                          "unknown_fields": unknown, "rows": rows},
                         ensure_ascii=False, indent=2))
    else:
        print(f"字数核查 · 表单={args.form}")
        print("=" * 70)
        for r in rows:
            if r["status"] == "OK":
                continue
            limit = r["limit"] if r["limit"] is not None else "-"
            print(f"[{r['status']:16s}] {r['field']:14s} {r['label'][:26]:28s} "
                  f"{r['count']:>5}/{limit}")
        if not over and not near and not missing_required and not unknown:
            print("全部字段在限内。")
        print("=" * 70)
        if over:
            print(f"超限 {len(over)} 处：")
            for fid, label, cnt, limit, diff in over:
                print(f"  - {fid} {label}：{cnt}/{limit}，超 {diff} 字 → 先删冗余修饰，保留数据与因果")
        if missing_required:
            print(f"必填缺失 {len(missing_required)} 处: {missing_required}")
        if unknown:
            print(f"未知字段 ID（拼写错误？）: {unknown}")

    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
