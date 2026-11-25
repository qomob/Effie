#!/usr/bin/env python3
"""类别查询与匹配（M04）。

注意：类别匹配不能只靠关键词相似度。本脚本只做**候选召回 + 硬条件过滤**，
最终匹配结论必须由专业判断给出（语义契合度、策略机制、成果类型、证据需求）。

用法:
  category_query.py --number 55
  category_query.py --search 私域
  category_query.py --track 电竞营销赛道
  category_query.py --award EFFIE_PRA --list
  category_query.py --candidates case.json      # 候选召回
"""
from __future__ import annotations

import argparse
import json
import re
import sys

import kb

STOP = set("的了是在和与及对为以于其这那有会可要就都而及等")


def bigrams(s: str) -> set[str]:
    s = re.sub(r"[^\u4e00-\u9fff]", "", s)
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else {s}


def show(c: dict, verbose=True):
    print(f"■ {c['number']:>3d}. {c['name_zh']}  /  {c.get('name_en') or ''}")
    print(f"    类型: {c.get('kind', '?')}  "
          f"板块: {c.get('section_zh', '')}"
          + (f"  赛道: {c['track_zh']}" if c.get("track_zh") else ""))
    if verbose:
        d = (c.get("definition_zh") or "").strip()
        if not d:
            print("    定义: [MISSING] 该类别定义未抽取到")
        else:
            for line in d.split("\n"):
                print(f"    {line}")
        if c.get("definition_shared_with"):
            print(f"    ※ 定义与类别 {c['definition_shared_with']} 共用")
        for sr in c.get("special_rules") or []:
            print(f"    ⚠ 特殊资格: {sr.get('rule')} = {sr.get('value')} "
                  f"({sr.get('note', '')})")
        if c.get("judging_dimensions"):
            print(f"    判断维度: {', '.join(c['judging_dimensions'])}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description="艾菲类别查询/召回")
    ap.add_argument("--number", type=int)
    ap.add_argument("--search")
    ap.add_argument("--track")
    ap.add_argument("--award", default="EFFIE_GC_MAIN")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--candidates", help="案例 JSON，输出候选类别")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not kb.get_award(args.award) or args.top<1:
        print('未知奖项或非法 top',file=sys.stderr); return 2
    other=kb.categories()['other_awards'].get(args.award)
    pool=kb.main_categories() if args.award=='EFFIE_GC_MAIN' else (other or {}).get('categories',[])
    if args.number is not None:
        c = kb.get_category(args.number, args.award)
        if not c:
            print(f"[MISSING] {args.award} 中未找到类别 {args.number}")
            other = kb.categories()["other_awards"].get(args.award)
            if other and other.get("verification_status") != "VERIFIED":
                print(f"  注意：{args.award} 类目册为 PARTIAL，请核对官方类别定义文件")
            return 3
        print(json.dumps(c, ensure_ascii=False, indent=2) if args.json else "")
        if not args.json:
            show(c)
        return 0

    if args.list:
        other = kb.categories()["other_awards"].get(args.award)
        if args.award == "EFFIE_GC_MAIN":
            cats = kb.main_categories()
            print(f"EFFIE_GC_MAIN 共 {len(cats)} 个类别"
                  f"（行业 28 / 专项 106，含 6 个战略赛道）")
        elif other:
            cats = other["categories"]
            print(f"{args.award} 已抽取 {len(cats)} 个类别"
                  f"（官方声明 {other.get('official_count_claimed')}；"
                  f"状态 {other.get('verification_status')}）")
            if other.get("limitation"):
                print(f"⚠ {other['limitation']}")
        else:
            print(f"{args.award} 无类别底册（手册未随附类别定义文件），"
                  f"须让用户查阅官方类别文件")
            return 3
        for c in cats:
            tr = f"[{c.get('track_zh')}]" if c.get("track_zh") else ""
            defn = "有定义" if (c.get("definition_zh") or "").strip() else "无定义"
            print(f"  {c['number']:>3d}  {c['name_zh']}{tr}  [{defn}]")
        return 0

    if not pool:
        print(f'{args.award} 无可用类别底册；不得借用主奖项类别',file=sys.stderr); return 3
    if args.award!='EFFIE_GC_MAIN' and (other or {}).get('verification_status')!='VERIFIED':
        print(f'注意：{args.award} 类别覆盖不完整，仅供召回，须查官方原文。',file=sys.stderr)
    if args.track:
        cats = [c for c in pool if c.get("track_zh") == args.track]
        if not cats:
            tracks = sorted({c["track_zh"] for c in pool if c.get("track_zh")})
            print(f"未找到赛道 {args.track}。可用: {tracks}")
            return 3
        print(f"赛道 {args.track}（{len(cats)} 个类别）")
        for c in cats:
            show(c, verbose=False)
        return 0

    if args.search:
        terms = bigrams(args.search)
        scored = []
        for c in pool:
            name_hay = c["name_zh"] + (c.get("name_en") or "")
            def_hay = c.get("definition_zh") or ""
            score = 0
            if args.search in name_hay:
                score += 100            # name hit dominates
            score += len(terms & bigrams(name_hay)) * 10
            score += len(terms & bigrams(def_hay))
            if score:
                scored.append((score, c))
        scored.sort(key=lambda x: (-x[0], x[1]["number"]))
        if not scored:
            print("无匹配类别。")
            return 3
        print(f"搜索「{args.search}」→ {len(scored)} 个候选（按相关度）")
        print("※ 关键词相关 ≠ 类别适配；须结合类别定义与资格条件判断\n")
        for sc, c in scored[:args.top]:
            print(f"  [{sc:2d}] {c['number']:>3d} {c['name_zh']}"
                  + (f"  「{c['track_zh']}」" if c.get("track_zh") else ""))
        return 0

    if args.candidates:
        try:
            case = json.load(open(args.candidates, encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"读取失败: {e}", file=sys.stderr)
            return 2
        text = " ".join(str(case.get(k, "")) for k in
                        ("summary", "challenge", "strategy", "outcome",
                         "industry", "audience", "mechanism"))
        if not text.strip():
            print("案例缺少 summary/challenge/strategy/outcome 等字段，无法召回")
            return 2
        terms = bigrams(text) - STOP
        scored = []
        for c in pool:
            hay = c["name_zh"] + (c.get("name_en") or "") + (c.get("definition_zh") or "")
            hb = bigrams(hay)
            overlap = len(terms & hb)
            if overlap == 0:
                continue
            # normalise by definition length so long defs don't win by size
            score = overlap / max(len(hb), 1) ** 0.5
            scored.append((round(score, 2), c))
        scored.sort(key=lambda x: -x[0])
        print(f"候选类别召回（{len(scored)} 个命中，Top {args.top}）")
        print("※ 这是召回，不是匹配结论。必须逐项核对类别定义/资格/证据需求后决定。\n")
        for sc, c in scored[:args.top]:
            special = " ⚠有特殊资格" if c.get("special_rules") else ""
            print(f"  {sc:5.2f}  {c['number']:>3d} {c['name_zh']}{special}")
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
