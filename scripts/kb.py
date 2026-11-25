#!/usr/bin/env python3
"""Shared knowledge-base access layer for Effie Entry Expert scripts.

All scripts import from here so that rule/category/field lookup is consistent
and every returned rule carries its official source citation.
"""
from __future__ import annotations

import json
import os
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "references")

_CACHE: dict[str, Any] = {}


def _load(name: str) -> Any:
    if name not in _CACHE:
        path = os.path.join(REF, name)
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"知识库文件缺失: {path}\n请确认 {REF} 下有 annual-rules-2026.json / "
                f"categories-2026.json / entry-fields-2026.json")
        with open(path, encoding="utf-8") as fh:
            _CACHE[name] = json.load(fh)
    return _CACHE[name]


def annual_rules() -> dict:
    return _load("annual-rules-2026.json")


def categories() -> dict:
    return _load("categories-2026.json")


def fields() -> dict:
    return _load("entry-fields-2026.json")


def awards() -> list[dict]:
    return annual_rules()["awards"]


def award_ids() -> list[str]:
    return [a["award_id"] for a in awards()]


def get_award(award_id: str) -> dict | None:
    for a in awards():
        if a["award_id"] == award_id:
            return a
    return None


def rules_for(award_id: str) -> list[dict]:
    return annual_rules()["rules"].get(award_id, [])


def find_rule(award_id: str, rule_type: str) -> dict | None:
    """Return the first VERIFIED rule of a type for an award."""
    for r in rules_for(award_id):
        if r["rule_type"] == rule_type and r["verification_status"] == "VERIFIED":
            return r
    # fall back to any status so caller can report UNVERIFIED explicitly
    for r in rules_for(award_id):
        if r["rule_type"] == rule_type:
            return r
    return None


def rule_value(award_id: str, rule_type: str, default=None):
    r = find_rule(award_id, rule_type)
    return r["rule_value"] if r and r.get("verification_status") == "VERIFIED" else default


def scoring_weights(award_id: str) -> dict | None:
    return rule_value(award_id, "scoring_weights")


def eligibility_window(award_id: str) -> dict | None:
    return rule_value(award_id, "eligibility_window")


def disqualifications(award_id: str) -> list[dict]:
    out = []
    for r in rules_for(award_id):
        if r["rule_type"] == "disqualification":
            out.append({
                "code": r["rule_value"]["code"],
                "desc": r["rule_value"]["desc"],
                "page": r["source_page"],
                "quote": r["source_quote"],
            })
    return out


def max_categories(award_id: str) -> int | None:
    return rule_value(award_id, "max_categories_per_activity")


def main_categories() -> list[dict]:
    return categories()["main_award"]["categories"]


def get_category(number: int, award_id: str = "EFFIE_GC_MAIN") -> dict | None:
    if award_id == "EFFIE_GC_MAIN":
        for c in main_categories():
            if c["number"] == number:
                return c
        return None
    other = categories()["other_awards"].get(award_id)
    if not other:
        return None
    for c in other["categories"]:
        if c["number"] == number:
            return c
    return None


def all_fields(form: str | None = None) -> list[dict]:
    fs = fields()["fields"]
    if form:
        return [f for f in fs if f["form"] == form]
    return fs


def field_by_id(fid: str) -> dict | None:
    for f in all_fields():
        if f["field_id"] == fid:
            return f
    return None


def doc_sha256(doc: str) -> str | None:
    """Source-file hash, stored once per document (not per rule)."""
    return annual_rules().get("document_sha256_index", {}).get(doc)


def rule_with_hash(rule: dict) -> dict:
    """Attach the document hash so callers get a complete citation record."""
    if not rule:
        return rule
    out = dict(rule)
    out["source_sha256"] = doc_sha256(rule.get("source_document", ""))
    return out


def cite(rule: dict) -> str:
    """Human-readable citation string for a rule.

    无页码时不得省略提示——否则模型会自行编造页码（P1-1）。
    转述类引用额外标注，避免被当成官方原文加引号。
    """
    if not rule:
        return "（无来源）"
    page = rule.get("source_page")
    base = (f"（来源：{rule['source_document']} P{page}）" if page
            else f"（来源：{rule['source_document']}，无页码）")
    kind = rule.get("quote_kind")
    if kind == "referential":
        return base + "［指代性引用，须改写成转述］"
    if kind == "paraphrase":
        return base + "［转述，非官方原句］"
    return base


def require_award(award_id: str) -> dict:
    a = get_award(award_id)
    if a is None:
        raise SystemExit(
            f"未知奖项 award_id={award_id}\n可用: {', '.join(award_ids())}")
    return a
