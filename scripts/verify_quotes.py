#!/usr/bin/env python3
"""引用真实性核验：规则里的 source_quote 是否真的出现在对应官方语料中。

这是防止"AI 编造引用"的守卫。结果分类：
  VERBATIM    原文整条逐字存在于语料     → 可标原文引用
  REFERENTIAL 指代性引用（「见…条款」）   → 必须改写成转述
  PARAPHRASE  语料中存在但非逐字         → 必须标为转述，不得当原文
  MISSING     完全找不到                 → 严重缺陷，不得引用

判定标准（v1.2.0 起）：**整条归一化后必须出现在语料中**才判 VERBATIM。
旧版取 quote 中段 12 字做包含判断，会把「跨奖项统一措辞的转述」误判为原文
（实测 8 条），已废弃。

用法:
  verify_quotes.py --corpus /path/to/corpus
  verify_quotes.py                       # 内置语料指纹自检（无需外部语料）
  verify_quotes.py --corpus ... --min-verbatim 0.90
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter

REFERENTIAL = re.compile(r"^（?见[^）]*）?$|^（.*）$")


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def load_corpus_index(here: str) -> dict | None:
    """读取包内的语料指纹索引（不含原文，仅哈希与统计）。"""
    p = os.path.join(here, "..", "references", "corpus-index.json")
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))


def selfaudit(rules: list[dict], index: dict | None) -> tuple[int, list[str]]:
    """无外部语料时的自检：核对计数与声明是否自洽。

    这不是逐字核验（做不到，语料不随包分发），只是防止
    「声明 verbatim 的数量」与「实际标注」矛盾，以及残留已知缺陷。
    """
    problems: list[str] = []
    kinds = Counter(r.get("quote_kind") for r in rules)
    declared = (index or {}).get("counts", {})

    if declared:
        for k, v in declared.items():
            if kinds.get(k, 0) != v:
                problems.append(f"quote_kind={k} 声明 {v} 条，实际 {kinds.get(k, 0)} 条")
    # 硬约束：paraphrase 不得同时标 VERIFIED
    for r in rules:
        if r.get("quote_kind") == "paraphrase" and r.get("verification_status") == "VERIFIED":
            problems.append(f"{r['rule_id']}: paraphrase 却标 VERIFIED")
    # 硬约束：verbatim 必须有页码或有明确说明
    for r in rules:
        if r.get("quote_kind") == "verbatim" and r.get("source_page") is None \
                and not r.get("page_note"):
            problems.append(f"{r['rule_id']}: verbatim 无页码且无说明")
    return len(problems), problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", help="语料目录（doc 名 + .txt）；省略则做内置自检")
    ap.add_argument("--rules", default=None)
    ap.add_argument("--min-verbatim", type=float, default=0.90)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    rules_path = args.rules or os.path.join(here, "..", "references",
                                            "annual-rules-2026.json")
    data = json.load(open(rules_path, encoding="utf-8"))
    rules = [r for a in data["rules"].values() for r in a]

    # ---- 模式 1：无外部语料 → 内置自检（可在用户侧运行，证明包内自洽） ----
    if not args.corpus:
        index = load_corpus_index(here)
        n_bad, problems = selfaudit(rules, index)
        out = {
            "mode": "selfaudit",
            "corpus_available": index is not None,
            "corpus_fingerprint": (index or {}).get("fingerprint"),
            "total_rules": len(rules),
            "quote_kind": dict(Counter(r.get("quote_kind") for r in rules)),
            "problems": problems[:30],
            "problem_count": n_bad,
            "ok": n_bad == 0,
            "note": ("内置自检只验证包内自洽（计数、状态一致性、页码说明），"
                     "不做逐字比对——官方语料不随包分发。"
                     "需要逐字核验请用 --corpus 指向自备语料。"),
        }
        if args.json:
            print(json.dumps(out, ensure_ascii=False, indent=1))
        else:
            print("引用守卫 · 内置自检（无外部语料）")
            print("=" * 66)
            print(f"规则总数        : {out['total_rules']}")
            print(f"引用类型分布    : {out['quote_kind']}")
            print(f"语料指纹        : {out['corpus_fingerprint'] or '未提供'}")
            print(f"问题数          : {n_bad}")
            for p in problems[:10]:
                print(f"  ✗ {p}")
            print("=" * 66)
            print("PASS（包内自洽）" if n_bad == 0 else "FAIL")
            print("注：内置自检不等于逐字核验。逐字核验请加 --corpus（需自备官方语料）。")
        return 0 if n_bad == 0 else 1

    # ---- 模式 2：有外部语料 → 严格逐条核验 ----
    cache: dict[str, str] = {}

    def corpus(doc: str) -> str:
        if doc not in cache:
            p = os.path.join(args.corpus, doc + ".txt")
            cache[doc] = norm(open(p, errors="replace").read()) if os.path.exists(p) else ""
        return cache[doc]

    verbatim = referential = paraphrase = nocorpus = 0
    problems = []
    for r in rules:
        q = r.get("source_quote") or ""
        if len(q) < 6:
            continue
        c = corpus(r["source_document"])
        if not c:
            nocorpus += 1
            problems.append({"rule_id": r["rule_id"], "status": "NO_CORPUS"})
            continue
        qn = norm(q)
        if REFERENTIAL.match(qn):
            referential += 1
            continue
        if qn in c:                      # 整条命中才算 verbatim
            verbatim += 1
        else:
            paraphrase += 1
            problems.append({"rule_id": r["rule_id"], "status": "NOT_VERBATIM",
                             "quote": q[:80], "doc": r["source_document"],
                             "page": r.get("source_page")})

    checked = verbatim + paraphrase
    ratio = verbatim / checked if checked else 0.0
    # 只有「标了 verbatim 却对不上」才算缺陷；标 paraphrase 是诚实降级
    mislabelled = [r for r in rules
                   if r.get("quote_kind") == "verbatim"
                   and norm(r.get("source_quote")) not in corpus(r["source_document"])]
    ok = ratio >= args.min_verbatim and nocorpus == 0 and not mislabelled

    out = {"mode": "strict", "checked": checked, "verbatim": verbatim,
           "referential": referential, "paraphrase": paraphrase,
           "no_corpus": nocorpus, "verbatim_ratio": round(ratio, 3),
           "threshold": args.min_verbatim, "ok": ok,
           "mislabelled_verbatim": [r["rule_id"] for r in mislabelled],
           "problems": problems[:50]}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print(f"引用核验 · 共 {checked} 条可核验引用")
        print("=" * 66)
        print(f"逐字命中 VERBATIM       : {verbatim}")
        print(f"指代性   REFERENTIAL    : {referential}")
        print(f"非逐字   PARAPHRASE     : {paraphrase}")
        print(f"无语料   NO_CORPUS      : {nocorpus}")
        print(f"逐字率                  : {ratio:.1%}（阈值 {args.min_verbatim:.0%}）")
        if mislabelled:
            print(f"\n标 verbatim 但原文对不上（必须为 0）: {len(mislabelled)}")
            for r in mislabelled[:10]:
                print(f"  ✗ {r['rule_id']}")
        print("=" * 66)
        print("PASS" if ok else "FAIL —— 存在伪逐字或无语料，需降级为转述标注")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
