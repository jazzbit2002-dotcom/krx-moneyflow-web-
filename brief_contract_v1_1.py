#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F29 US macro brief contract validator v1.1.

Base contract: server macro_prompt_v7.txt (17,229 B, sha 5f4d65cb...).
Adds fail-closed validation + digest usage enforcement (audit requirement).

Canonical files are never modified; this module only reads and validates.
"""

import json
import os
import re
import hashlib
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

SCHEMA_VERSION = "us_macro_brief_v1"
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "us_macro_brief_v1_1.schema.json")
VALID_STATUS = ("baseline_only", "ready")
DISCLAIMER = (
    "이 글은 시장 구조를 분석한 참고 자료이며 투자 권유가 아닙니다. "
    "투자 판단과 그 결과에 대한 책임은 본인에게 있습니다."
)

TOP_KEYS = ["schema_version", "as_of", "headline", "deck", "key_points", "sections",
            "watchpoints", "social_summary", "email_subject", "email_preview", "disclaimer"]

SECTION_IDS = ["conclusion", "breadth", "size_style", "rates_vol", "commodities",
               "semis_sectors", "rotation", "value_chain_radar", "next_session"]
ALWAYS_REQUIRED = ["conclusion", "next_session"]
DIGEST_REQUIRED = ["rotation", "value_chain_radar"]
COMPARISON_ONLY = ["size_style", "rates_vol", "commodities", "semis_sectors"]

LIMITS = {
    "headline": (12, 60), "deck": (30, 160), "key_point": (12, 120),
    "section_title": (2, 30), "section_body": (60, 900), "watchpoint": (15, 200),
    "social_summary": (80, 240), "email_subject": (10, 50), "email_preview": (30, 120),
}
ARTICLE_LEN = {"baseline_only": (1000, 1600), "ready": (1500, 2500)}

FORBIDDEN = ["매수 추천", "매도 신호", "목표가", "손절", "순유입", "순유출",
             "진입", "청산", "예측", "적중", "신뢰도", "적중률"]
INTERNAL = ["F29", "briefing-context", "market_internals", "market_close_snapshot",
            "market_close_comparison", "lifecycle", "freshness", "theme_flow", "intraday",
            "moneyflow_digest", "stock_radar", "value_chains", "horizon_leaders",
            "theme_ranking", "strength_quality", "d_score", "d_rank"]
MONEY_METAPHOR = ["돈이 몰렸", "돈이 빠졌", "돈이 퍼졌", "돈이 이동", "자금이 유입",
                  "수급이 들어", "자금이 빠져", "자금 유입"]
BAD_PHRASE = ["공식 종가", "settlement", "확정 종가", "공식 일일"]
JARGON = ["밸류체인", "로테이션"]

DERIVED_FIELDS = ["headline", "deck", "key_points", "social_summary",
                  "email_subject", "email_preview"]

_NUM = re.compile(r"(-?\d+(?:\.\d+)?)\s*(%p|%|bp|포인트|억|배)?")


def schema_errors(brief: Mapping[str, Any]) -> List[str]:
    """Validate against the canonical JSON Schema file (Draft 2020-12).

    The dependency is mandatory: a missing module must fail the run, never
    silently skip schema validation.
    """
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        raise RuntimeError(
            "jsonschema dependency missing - install with: "
            "pip install jsonschema --break-system-packages")
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        schema = json.load(fh)
    validator = Draft202012Validator(schema)
    out: List[str] = []
    for err in sorted(validator.iter_errors(brief), key=lambda e: list(e.path)):
        loc = "/".join(str(x) for x in err.path) or "(root)"
        out.append("schema: %s at %s" % (err.message, loc))
    return out


class ValidationResult(object):
    def __init__(self):
        self.violations: List[str] = []
        self.warnings: List[str] = []
        self.section_ids: List[str] = []
        self.article_chars = 0
        self.social_chars = 0
        self.email_chars = 0
        self.digest_usage = "SKIPPED_MISSING"
        self.brief_sha256 = ""
        self.schema_validation = "NOT_RUN"
        self.field_scan: Dict[str, List[str]] = {}

    @property
    def ok(self) -> bool:
        return not self.violations

    def fail(self, msg: str) -> None:
        self.violations.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def to_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "violations": self.violations, "warnings": self.warnings,
                "section_ids": self.section_ids, "article_chars": self.article_chars,
                "social_chars": self.social_chars, "email_chars": self.email_chars,
                "digest_usage": self.digest_usage, "brief_sha256": self.brief_sha256,
                "schema_validation": self.schema_validation,
                "field_scan": self.field_scan}


class ContractParseError(ValueError):
    """Raised when the raw response violates the output-format contract."""


def parse_response(raw: str) -> Mapping[str, Any]:
    """Strict parse. The v7 contract forbids code fences, preamble and trailing text."""
    t = (raw or "").strip()
    if not t:
        raise ContractParseError("empty response")
    if t.startswith("```") or t.endswith("```"):
        raise ContractParseError("markdown code fence is a contract violation")
    if not t.startswith("{"):
        raise ContractParseError("response must start with a JSON object")
    dec = json.JSONDecoder()
    obj, end = dec.raw_decode(t)
    if t[end:].strip():
        raise ContractParseError("trailing text after JSON object")
    if not isinstance(obj, dict):
        raise ContractParseError("top level must be a JSON object")
    return obj


def canonical_bytes(obj: Mapping[str, Any]) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def number_tokens(text: str) -> Set[Tuple[str, str]]:
    """Normalized (value, unit) pairs. 1bp != 1% != 1.3%p."""
    out: Set[Tuple[str, str]] = set()
    for m in _NUM.finditer(text or ""):
        val, unit = m.group(1), (m.group(2) or "")
        try:
            f = float(val)
        except ValueError:
            continue
        norm = ("%g" % f)
        out.add((norm, unit))
    return out


def _collect_strings(obj: Any, out: List[str]) -> None:
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_strings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_strings(v, out)


MAX_TOTAL_TICKERS = 8


def ticker_aliases(context: Mapping[str, Any]) -> Dict[str, Set[str]]:
    """ticker -> {ticker, korean name, ...} for bidirectional body matching."""
    out: Dict[str, Set[str]] = {}

    def add(tk: Any, *names: Any) -> None:
        if not tk:
            return
        key = str(tk).upper()
        bucket = out.setdefault(key, {key})
        for n in names:
            if n and isinstance(n, str) and n.strip():
                bucket.add(n.strip())

    g = context.get("moneyflow_digest") or {}
    for bucket in (g.get("stock_radar") or {}).values():
        if isinstance(bucket, list):
            for it in bucket:
                if isinstance(it, dict):
                    add(it.get("ticker"), it.get("name"), it.get("name_ko"))
    for key in ("leaders", "exits", "watching"):
        for it in (context.get(key) or []):
            if isinstance(it, dict):
                add(it.get("ticker"), it.get("name"), it.get("name_ko"))
    return out


def mentioned_tickers(text: str, aliases: Mapping[str, Set[str]]) -> Set[str]:
    found: Set[str] = set()
    for tk, names in aliases.items():
        for n in names:
            if n and n in (text or ""):
                found.add(tk)
                break
    return found


def mentioned_themes(text: str, allowed: Set[str]) -> Set[str]:
    """Longest-first matching so that 반도체장비 does not also count as 반도체."""
    body = text or ""
    found: Set[str] = set()
    for th in sorted(allowed, key=len, reverse=True):
        if th and th in body:
            found.add(th)
            body = body.replace(th, "\x00" * len(th))
    return found


def allowed_tickers(context: Mapping[str, Any]) -> Set[str]:
    out: Set[str] = set()
    g = context.get("moneyflow_digest") or {}
    radar = g.get("stock_radar") or {}
    for bucket in radar.values():
        if isinstance(bucket, list):
            for it in bucket:
                if isinstance(it, dict) and it.get("ticker"):
                    out.add(str(it["ticker"]).upper())
    for key in ("leaders", "exits", "watching"):
        for it in (context.get(key) or []):
            if isinstance(it, dict) and it.get("ticker"):
                out.add(str(it["ticker"]).upper())
    return out


def allowed_themes(context: Mapping[str, Any]) -> Set[str]:
    out: Set[str] = set()
    g = context.get("moneyflow_digest") or {}
    tr = g.get("theme_ranking") or {}
    for bucket in tr.values():
        if isinstance(bucket, list):
            for it in bucket:
                if isinstance(it, dict) and it.get("theme"):
                    out.add(str(it["theme"]))
    hz = g.get("horizon_leaders") or {}
    for bucket in hz.values():
        if isinstance(bucket, list):
            out.update(str(x) for x in bucket)
    for vc in (g.get("value_chains") or []):
        if isinstance(vc, dict):
            if vc.get("group"):
                out.add(str(vc["group"]))
            if vc.get("lead"):
                out.add(str(vc["lead"]))
            for m in (vc.get("members") or []):
                if isinstance(m, dict) and m.get("theme"):
                    out.add(str(m["theme"]))
    sq = g.get("strength_quality")
    if isinstance(sq, dict) and sq.get("theme"):
        out.add(str(sq["theme"]))
    for it in (context.get("theme_flow") or []):
        if isinstance(it, dict) and it.get("theme"):
            out.add(str(it["theme"]))
    for key in ("leaders", "exits", "watching"):
        for it in (context.get(key) or []):
            if isinstance(it, dict) and it.get("theme"):
                out.add(str(it["theme"]))
    return out


def digest_is_usable(context: Mapping[str, Any]) -> Tuple[bool, str]:
    g = context.get("moneyflow_digest")
    if not isinstance(g, dict) or not g:
        return False, "SKIPPED_MISSING"
    tr = (g.get("theme_ranking") or {}).get("top") or []
    hz = g.get("horizon_leaders") or {}
    radar = g.get("stock_radar") or {}
    has_any = bool(tr) or bool(hz.get("d7") or hz.get("d90")) or \
        any(bool(v) for v in radar.values() if isinstance(v, list))
    if not has_any:
        return False, "SKIPPED_MISSING"
    own = (g.get("freshness") or {}).get("state") if isinstance(g.get("freshness"), dict) else None
    if own is not None and own != "fresh":
        return False, "SKIPPED_STALE"
    return True, "REQUIRED"


def _len_check(res: ValidationResult, label: str, value: Any, key: str) -> None:
    lo, hi = LIMITS[key]
    if not isinstance(value, str) or not value.strip():
        res.fail("%s: empty or not a string" % label)
        return
    n = len(value)
    if n < lo or n > hi:
        res.fail("%s: length %d out of range %d-%d" % (label, n, lo, hi))


def article_text(brief: Mapping[str, Any]) -> str:
    """Reader-exposed article text: deck + key_points + section bodies + watchpoints."""
    parts: List[str] = []
    if isinstance(brief.get("deck"), str):
        parts.append(brief["deck"])
    for kp in (brief.get("key_points") or []):
        if isinstance(kp, str):
            parts.append(kp)
    for s in (brief.get("sections") or []):
        if isinstance(s, dict) and isinstance(s.get("body"), str):
            parts.append(s["body"])
    for w in (brief.get("watchpoints") or []):
        if isinstance(w, str):
            parts.append(w)
    return "".join(parts)


def field_texts(brief: Mapping[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k in ("headline", "deck", "social_summary", "email_subject",
              "email_preview", "disclaimer"):
        if isinstance(brief.get(k), str):
            out[k] = brief[k]
    for i, kp in enumerate(brief.get("key_points") or []):
        if isinstance(kp, str):
            out["key_points[%d]" % i] = kp
    for s in (brief.get("sections") or []):
        if isinstance(s, dict):
            sid = s.get("id") or "?"
            if isinstance(s.get("title"), str):
                out["sections.%s.title" % sid] = s["title"]
            if isinstance(s.get("body"), str):
                out["sections.%s.body" % sid] = s["body"]
    for i, w in enumerate(brief.get("watchpoints") or []):
        if isinstance(w, str):
            out["watchpoints[%d]" % i] = w
    return out


def validate_brief(brief: Mapping[str, Any], context: Mapping[str, Any],
                   comparison_status: str, expected_as_of: str) -> ValidationResult:
    res = ValidationResult()
    if not isinstance(brief, dict):
        res.fail("brief is not a JSON object")
        return res
    res.brief_sha256 = hashlib.sha256(canonical_bytes(brief)).hexdigest()

    # --- JSON Schema (mandatory, fail-closed) ---
    try:
        errs = schema_errors(brief)
        res.schema_validation = "DRAFT202012"
        for e in errs:
            res.fail(e)
    except RuntimeError as exc:
        res.schema_validation = "DEPENDENCY_MISSING"
        res.fail(str(exc))
    except Exception as exc:
        res.schema_validation = "ERROR"
        res.fail("schema validation error: %s" % exc.__class__.__name__)

    # --- comparison_status must be explicit ---
    if comparison_status not in VALID_STATUS:
        res.fail("comparison_status must be exactly 'baseline_only' or 'ready' "
                 "(got %r)" % (comparison_status,))

    # --- top-level keys ---
    keys = set(brief.keys())
    missing = [k for k in TOP_KEYS if k not in keys]
    extra = sorted(keys - set(TOP_KEYS))
    if missing:
        res.fail("missing top-level key(s): %s" % ", ".join(missing))
    if extra:
        res.fail("unexpected top-level key(s): %s" % ", ".join(extra))

    if brief.get("schema_version") != SCHEMA_VERSION:
        res.fail("schema_version must equal '%s'" % SCHEMA_VERSION)
    if expected_as_of and brief.get("as_of") != expected_as_of:
        res.fail("as_of '%s' != expected '%s'" % (brief.get("as_of"), expected_as_of))
    if brief.get("disclaimer") != DISCLAIMER:
        res.fail("disclaimer must match the canonical sentence exactly")

    # --- scalar field lengths ---
    _len_check(res, "headline", brief.get("headline"), "headline")
    _len_check(res, "deck", brief.get("deck"), "deck")
    _len_check(res, "social_summary", brief.get("social_summary"), "social_summary")
    _len_check(res, "email_subject", brief.get("email_subject"), "email_subject")
    _len_check(res, "email_preview", brief.get("email_preview"), "email_preview")

    kps = brief.get("key_points")
    if not isinstance(kps, list) or len(kps) != 3:
        res.fail("key_points must be exactly 3 items")
    else:
        for i, kp in enumerate(kps):
            _len_check(res, "key_points[%d]" % i, kp, "key_point")

    wps = brief.get("watchpoints")
    if not isinstance(wps, list) or not (1 <= len(wps) <= 3):
        res.fail("watchpoints must have 1-3 items")
    else:
        for i, w in enumerate(wps):
            _len_check(res, "watchpoints[%d]" % i, w, "watchpoint")

    aliases = ticker_aliases(context)
    ok_th_all = allowed_themes(context)

    # --- sections ---
    secs = brief.get("sections")
    if not isinstance(secs, list) or not (4 <= len(secs) <= 8):
        res.fail("sections must have 4-8 items")
        secs = secs if isinstance(secs, list) else []
    ids: List[str] = []
    tick_all: Set[str] = set()
    theme_all: Set[str] = set()
    for i, s in enumerate(secs):
        if not isinstance(s, dict):
            res.fail("sections[%d] is not an object" % i)
            continue
        skeys = set(s.keys())
        want = {"id", "title", "body", "tickers", "themes"}
        if skeys != want:
            res.fail("sections[%d] keys must be exactly %s (got %s)"
                     % (i, sorted(want), sorted(skeys)))
        sid = s.get("id")
        if sid not in SECTION_IDS:
            res.fail("sections[%d].id '%s' not in allowed list" % (i, sid))
        else:
            ids.append(sid)
        _len_check(res, "sections[%s].title" % sid, s.get("title"), "section_title")
        _len_check(res, "sections[%s].body" % sid, s.get("body"), "section_body")
        body = s.get("body") if isinstance(s.get("body"), str) else ""

        tk = s.get("tickers")
        if not isinstance(tk, list) or len(tk) > 4:
            res.fail("sections[%s].tickers must be a list of at most 4" % sid)
            tk = tk if isinstance(tk, list) else []
        declared: Set[str] = set()
        for t in tk:
            if not isinstance(t, str) or not re.match(r"^[A-Z][A-Z0-9.\-]{0,9}$", t):
                res.fail("sections[%s].tickers has invalid ticker '%s'" % (sid, t))
            else:
                declared.add(t)
                tick_all.add(t)
        seen = mentioned_tickers(body, aliases)
        for t in sorted(declared - seen):
            res.fail("sections[%s]: ticker %s declared but not mentioned in body "
                     "(neither symbol nor name)" % (sid, t))
        for t in sorted(seen - declared):
            res.fail("sections[%s]: body mentions %s but tickers array omits it" % (sid, t))

        th = s.get("themes")
        if not isinstance(th, list) or len(th) > 6:
            res.fail("sections[%s].themes must be a list of at most 6" % sid)
            th = th if isinstance(th, list) else []
        dec_th: Set[str] = set()
        for t in th:
            if not isinstance(t, str) or not t.strip():
                res.fail("sections[%s].themes has empty value" % sid)
            else:
                dec_th.add(t)
                theme_all.add(t)
        for t in sorted(dec_th):
            if t not in body:
                res.fail("sections[%s]: theme '%s' declared but not discussed in body"
                         % (sid, t))
        if ok_th_all:
            for t in sorted(mentioned_themes(body, ok_th_all) - dec_th):
                res.fail("sections[%s]: body discusses theme '%s' but themes array omits it"
                         % (sid, t))

    if len(tick_all) > MAX_TOTAL_TICKERS:
        res.fail("total unique tickers %d exceeds max %d"
                 % (len(tick_all), MAX_TOTAL_TICKERS))

    if len(ids) != len(set(ids)):
        res.fail("duplicate section id(s): %s"
                 % ", ".join(sorted({x for x in ids if ids.count(x) > 1})))
    res.section_ids = ids

    for need in ALWAYS_REQUIRED:
        if need not in ids:
            res.fail("required section missing: %s" % need)

    status = comparison_status if comparison_status in VALID_STATUS else "baseline_only"
    if status == "baseline_only":
        bad = [x for x in ids if x in COMPARISON_ONLY]
        if bad:
            res.fail("baseline_only must not include comparison sections: %s"
                     % ", ".join(bad))
    elif status == "ready":
        if not (6 <= len(ids) <= 8):
            res.fail("ready status requires 6-8 sections (got %d)" % len(ids))

    # --- digest usage enforcement ---
    usable, state = digest_is_usable(context)
    res.digest_usage = state
    if usable:
        miss = [x for x in DIGEST_REQUIRED if x not in ids]
        if miss:
            res.fail("digest present but required section(s) missing: %s" % ", ".join(miss))
            res.digest_usage = "FAIL"
        else:
            g = context.get("moneyflow_digest") or {}
            bodies = {s.get("id"): (s.get("body") or "")
                      for s in secs if isinstance(s, dict)}
            hz = g.get("horizon_leaders") or {}
            d7 = [str(x) for x in (hz.get("d7") or [])]
            d90 = [str(x) for x in (hz.get("d90") or [])]
            rot = bodies.get("rotation", "")
            if d7 and d90:
                if not (any(x in rot for x in d7) and any(x in rot for x in d90)):
                    res.fail("rotation.body must reference both short-term (d7) and "
                             "long-term (d90) leading themes")
                    res.digest_usage = "FAIL"
            vcr = bodies.get("value_chain_radar", "")
            vc_names: Set[str] = set()
            for vc in (g.get("value_chains") or []):
                if isinstance(vc, dict):
                    for m in (vc.get("members") or []):
                        if isinstance(m, dict) and m.get("theme"):
                            vc_names.add(str(m["theme"]))
                    if vc.get("group"):
                        vc_names.add(str(vc["group"]))
            if vc_names and not any(n in vcr for n in vc_names):
                res.fail("value_chain_radar.body must cite an industry-chain theme")
                res.digest_usage = "FAIL"
            radar_names: Set[str] = set()
            for bucket in (g.get("stock_radar") or {}).values():
                if isinstance(bucket, list):
                    for it in bucket:
                        if isinstance(it, dict):
                            if it.get("ticker"):
                                radar_names.add(str(it["ticker"]))
                            if it.get("name"):
                                radar_names.add(str(it["name"]))
            if radar_names and not any(n in vcr for n in radar_names):
                res.fail("value_chain_radar.body must cite a stock from the radar")
                res.digest_usage = "FAIL"
            if res.digest_usage == "REQUIRED":
                res.digest_usage = "PASS"

    # --- provenance: tickers/themes must exist in context ---
    ok_t = allowed_tickers(context)
    if ok_t:
        bad = sorted(tick_all - ok_t)
        if bad:
            res.fail("tickers not present in source data: %s" % ", ".join(bad))
    ok_th = allowed_themes(context)
    if ok_th:
        bad = sorted(theme_all - ok_th)
        if bad:
            res.fail("themes not present in source data: %s" % ", ".join(bad))

    # --- provenance: derived fields must not introduce new numbers ---
    base_text = "".join([s.get("body", "") for s in secs if isinstance(s, dict)] +
                        [w for w in (brief.get("watchpoints") or []) if isinstance(w, str)])
    base_nums = number_tokens(base_text)
    base_ticks = mentioned_tickers(base_text, aliases)
    for f in DERIVED_FIELDS:
        v = brief.get(f)
        chunks = v if isinstance(v, list) else [v]
        for idx, chunk in enumerate(chunks):
            if not isinstance(chunk, str):
                continue
            label = f if not isinstance(v, list) else "%s[%d]" % (f, idx)
            new = number_tokens(chunk) - base_nums
            if new:
                res.fail("%s introduces number(s) absent from sections/watchpoints: %s"
                         % (label, ", ".join("%s%s" % (a, b) for a, b in sorted(new))))
            new_t = mentioned_tickers(chunk, aliases) - base_ticks
            if new_t:
                res.fail("%s introduces stock(s) absent from sections/watchpoints: %s"
                         % (label, ", ".join(sorted(new_t))))

    # --- forbidden / internal / metaphor / jargon, per field ---
    ftexts = field_texts(brief)
    for label, txt in ftexts.items():
        hits: List[str] = []
        hits += ["금칙어:%s" % w for w in FORBIDDEN if w in txt]
        hits += ["내부명칭:%s" % w for w in INTERNAL if w in txt]
        if label != "disclaimer":
            hits += ["자금은유:%s" % w for w in MONEY_METAPHOR if w in txt]
            hits += ["금지표현:%s" % w for w in BAD_PHRASE if w in txt]
            hits += ["업계용어:%s" % w for w in JARGON if w in txt]
        if hits:
            res.field_scan[label] = hits
            res.fail("%s violates term policy: %s" % (label, ", ".join(hits)))

    # --- article length by status ---
    art = article_text(brief)
    res.article_chars = len(art)
    res.social_chars = len(brief.get("social_summary") or "")
    res.email_chars = len(brief.get("email_subject") or "") + \
        len(brief.get("email_preview") or "")
    lo, hi = ARTICLE_LEN.get(status, ARTICLE_LEN["ready"])
    if not (lo <= res.article_chars <= hi):
        res.fail("article length %d out of range %d-%d for status '%s'"
                 % (res.article_chars, lo, hi, status))
    return res


def validate_and_store(raw_response: str, context: Mapping[str, Any],
                       comparison_status: str, expected_as_of: str,
                       evidence_dir: str) -> ValidationResult:
    """Parse -> validate -> persist. Canonical raw text is written by the caller."""
    os.makedirs(evidence_dir, exist_ok=True)
    try:
        brief = parse_response(raw_response)
    except Exception as exc:
        res = ValidationResult()
        res.fail("JSON parse failed: %s" % exc.__class__.__name__)
        _write(evidence_dir, "validation.json", res.to_dict())
        return res
    res = validate_brief(brief, context, comparison_status, expected_as_of)
    if res.ok:
        _write(evidence_dir, "response.json", brief)
    _write(evidence_dir, "validation.json", res.to_dict())
    return res


def _write(d: str, name: str, obj: Any) -> str:
    path = os.path.join(d, name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path
