#!/usr/bin/env python3
# F29 DELIVERY v7.1 CONTRACT PATCH (2026-07-20)
# Target : /root/moneyflow/us_macro_delivery.py
# Base   : server measured SHA b6a3f13edcad5b43ebe9d2b4bd62cb596e4e8bc6068da8b87c90286bf08db267
#          (10,819 B / 250 lines)
# Effect : strict parse -> JSON Schema -> contract -> validation.json
#          PASS  -> brief.json (disk-verified SHA), status=brief_saved, publishable/eligible = true
#          FAIL  -> no brief.json, status=contract_failed, exit 3
# v6 fallback preserved: the contract runs ONLY when PROMPT_FILE points at a v7 prompt.
# Literal anchors, count gate, backup, py_compile, atomic write. Pure ASCII.

import os, sys, shutil, subprocess, datetime, hashlib

TARGET = "/root/moneyflow/us_macro_delivery.py"
BASE_SHA = "b6a3f13edcad5b43ebe9d2b4bd62cb596e4e8bc6068da8b87c90286bf08db267"
MARKER = "F29-V71-CONTRACT v1"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def fail(msg):
    print("HARD_FAIL: " + msg)
    sys.exit(1)


src = open(TARGET, "r", encoding="utf-8").read()
pre = sha256(TARGET)
if MARKER in src:
    fail("marker already present - patch already applied")
if pre != BASE_SHA:
    print("WARNING: base SHA mismatch")
    print("  expected: " + BASE_SHA)
    print("  actual  : " + pre)
    fail("refusing to patch a file that is not the measured base")
print("base SHA gate: PASS (%s)" % pre[:16])

# ---------------- anchors ----------------
A_IMPORT = (
    'import json, os, re, sys, time, uuid, hashlib, subprocess, urllib.request, urllib.error\n'
    'from datetime import datetime, timezone\n'
)
A_EVID = (
    'json.dump(comparison, open(os.path.join(outdir, "comparison.json"), "w", encoding="utf-8"),\n'
    '          ensure_ascii=False, indent=2)\n'
    'evidence = {"run_id": run_id, "model": MODEL,\n'
)
A_TAIL = (
    '    "status": "draft_saved"}\n'
    'json.dump(evidence, open(os.path.join(outdir, "evidence.json"), "w", encoding="utf-8"),\n'
    '          ensure_ascii=False, indent=2)\n'
    'print("evidence dir      :", outdir)\n'
    'print("DELIVERY: DONE")\n'
)
for name, a in (("IMPORT", A_IMPORT), ("EVID", A_EVID), ("TAIL", A_TAIL)):
    n = src.count(a)
    if n != 1:
        fail("anchor %s count=%d (expected 1)" % (name, n))
print("anchor gate: 3/3 count==1")

# ---------------- replacements ----------------
N_IMPORT = (
    A_IMPORT +
    '# ' + MARKER + '\n'
    'sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n'
    'import brief_contract_v1_1 as bcv\n'
)

N_EVID = (
    'json.dump(comparison, open(os.path.join(outdir, "comparison.json"), "w", encoding="utf-8"),\n'
    '          ensure_ascii=False, indent=2)\n'
    '\n'
    '# ---------- 8-1. ' + MARKER + ' (v7 output contract) ----------\n'
    '# The contract applies only to v7 structured-JSON prompts. A v6 prose run\n'
    '# keeps the previous behaviour so that fallback stays available.\n'
    '_v7_mode = "macro_prompt_v7" in PROMPT_FILE\n'
    '_val = None\n'
    'if _v7_mode:\n'
    '    _cmp_status = comparison["market_close_comparison"]["status"]\n'
    '    _expect_as_of = (((d.get("market_internals") or {}).get("market_close_snapshot")\n'
    '                      or {}).get("as_of") or d.get("as_of"))\n'
    '    _brief = None\n'
    '    try:\n'
    '        _brief = bcv.parse_response(text)\n'
    '    except Exception as _exc:\n'
    '        _val = bcv.ValidationResult()\n'
    '        _val.fail("response parse failed: %s: %s" % (_exc.__class__.__name__, _exc))\n'
    '    if _brief is not None:\n'
    '        _val = bcv.validate_brief(_brief, d, _cmp_status, _expect_as_of)\n'
    '    _vtmp = os.path.join(outdir, "validation.json.tmp")\n'
    '    json.dump(_val.to_dict(), open(_vtmp, "w", encoding="utf-8"),\n'
    '              ensure_ascii=False, indent=2)\n'
    '    os.replace(_vtmp, os.path.join(outdir, "validation.json"))\n'
    '    _brief_file_sha = None\n'
    '    if _val.ok:\n'
    '        _bpath = os.path.join(outdir, "brief.json")\n'
    '        _btmp = _bpath + ".tmp"\n'
    '        with open(_btmp, "w", encoding="utf-8") as _bf:\n'
    '            json.dump(_brief, _bf, ensure_ascii=False, indent=2)\n'
    '            _bf.flush()\n'
    '            os.fsync(_bf.fileno())\n'
    '        os.replace(_btmp, _bpath)\n'
    '        with open(_bpath, "rb") as _bf:\n'
    '            _brief_file_sha = hashlib.sha256(_bf.read()).hexdigest()\n'
    '        print("brief.json        :", _brief_file_sha[:16], "(disk bytes)")\n'
    '    print("contract          :", "PASS" if _val.ok else "FAIL",\n'
    '          "| schema", _val.schema_validation, "| digest", _val.digest_usage,\n'
    '          "| article", _val.article_chars)\n'
    '\n'
    'evidence = {"run_id": run_id, "model": MODEL,\n'
)

N_TAIL = (
    '    "status": ("brief_saved" if (_val is not None and _val.ok)\n'
    '               else ("contract_failed" if _val is not None else "draft_saved")),\n'
    '    "contract_mode": ("v7" if _val is not None else "v6"),\n'
    '    "contract_ok": (bool(_val.ok) if _val is not None else None),\n'
    '    "schema_validation": (_val.schema_validation if _val is not None else None),\n'
    '    "digest_usage": (_val.digest_usage if _val is not None else None),\n'
    '    "brief_sha256": (_brief_file_sha if _val is not None else None),\n'
    '    "brief_canonical_sha256": (_val.brief_sha256 if _val is not None else None),\n'
    '    "article_chars": (_val.article_chars if _val is not None else None),\n'
    '    "section_ids": (_val.section_ids if _val is not None else None),\n'
    '    "violations": (_val.violations if _val is not None else None),\n'
    '    "publishable": (bool(_val.ok) if _val is not None else False),\n'
    '    "eligible_for_latest": (bool(_val.ok) if _val is not None else False)}\n'
    'json.dump(evidence, open(os.path.join(outdir, "evidence.json"), "w", encoding="utf-8"),\n'
    '          ensure_ascii=False, indent=2)\n'
    'print("evidence dir      :", outdir)\n'
    'if _val is not None and not _val.ok:\n'
    '    print("CONTRACT: FAIL (%d violation(s))" % len(_val.violations))\n'
    '    for _v in _val.violations[:12]:\n'
    '        print("  -", _v)\n'
    '    if len(_val.violations) > 12:\n'
    '        print("  ... %d more" % (len(_val.violations) - 12))\n'
    '    print("DELIVERY: CONTRACT_FAILED (brief.json not written)")\n'
    '    sys.exit(3)\n'
    'if _val is not None:\n'
    '    print("CONTRACT: PASS | %d chars | sections %s | digest %s | brief_sha256 %s"\n'
    '          % (_val.article_chars, ",".join(_val.section_ids), _val.digest_usage,\n'
    '             _val.brief_sha256[:16]))\n'
    'print("DELIVERY: DONE")\n'
)

out = src.replace(A_IMPORT, N_IMPORT, 1)
out = out.replace(A_EVID, N_EVID, 1)
out = out.replace(A_TAIL, N_TAIL, 1)
if out == src:
    fail("no change produced")
if out.count(MARKER) != 2:
    fail("marker count %d != 2" % out.count(MARKER))

ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
bdir = "/root/f29-backups/delivery-v71-" + ts
os.makedirs(bdir, exist_ok=False)
shutil.copy2(TARGET, os.path.join(bdir, "us_macro_delivery.py"))
print("backup: " + bdir + "/us_macro_delivery.py")
print("pre_sha256: " + pre)

tmp = TARGET + ".v71.tmp.py"
with open(tmp, "w", encoding="utf-8") as f:
    f.write(out)
r = subprocess.run([sys.executable, "-m", "py_compile", tmp],
                   capture_output=True, text=True)
if r.returncode != 0:
    os.remove(tmp)
    fail("py_compile failed:\n" + r.stderr)
print("py_compile: PASS")
os.replace(tmp, TARGET)
print("applied. post_sha256: " + sha256(TARGET))
print("post size: %d bytes" % os.path.getsize(TARGET))
print("ROLLBACK: cp %s/us_macro_delivery.py %s" % (bdir, TARGET))
print("NOTE: contract runs only when PROMPT_FILE points at macro_prompt_v7*.")
print("      Requires brief_contract_v1_1.py + us_macro_brief_v1_1.schema.json")
print("      in /root/moneyflow/ and the jsonschema package.")
