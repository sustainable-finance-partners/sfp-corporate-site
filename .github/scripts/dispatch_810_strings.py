"""The 810 section 4 signed strings, extracted from a byte copy of the dispatch.

COO dispatch 810 v2 section 4 (2026-11-06, "Corporate #24", line 26) signs two strings for
this site, and both render byte for byte:

* the Privacy Policy header, "Last updated 2026-11-06 · v1.3";
* the AP2 mandate wording PCP R-06's claim-state governs: an AP2 mandate is "recorded as
  unverified context where presented; mandate verification is planned".

This script is the only author of the 810 rows of .github/signed_strings.json. It works
as dispatch_809_strings.py does:
1. It reads the byte copy at .github/fixtures/dispatch_810/.
2. It checks the copy's size, SHA-256 and house pin (sha256 after CRLF to LF, first 16 hex).
3. It extracts each string from its line with one regex that must match exactly once.
4. It writes the rows. No string is typed here: each row names a line and a pattern.

.github/scripts/signed_strings_check.py then proves that each string renders at its
targets, and with --source-root it re-extracts each string from the original.

The checks block gains 810's absences: the wording that is gone. That is 810's rule for any
sentence saying AP2 is integrated, supported, enforced or verified: it takes the
substitution, and a sentence the substitution cannot make true is removed. The checks block
also gains one presence, the header's date in the page's metadata block. Each carries
"source": "810 section 4", so a rewrite replaces exactly these.

Usage:
  python3 .github/scripts/dispatch_810_strings.py --write
  python3 .github/scripts/dispatch_810_strings.py --check
  python3 .github/scripts/dispatch_810_strings.py --self-test

--check (CI) passes when the copy hashes to its recorded digest, and the 810 rows and
checks in the fixture equal a fresh extraction from the copy, in order and byte for byte.

--self-test plants three failures, and each must be reported:
* a copy with one byte changed;
* a row whose string has one character changed;
* a line on which a pattern matches twice.

Exit 0 only when all holds. Standard library only.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import signed_strings_check as ssc  # noqa: E402  (the checker's own extract and transforms)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / ".github" / "signed_strings.json"
COPY_REL = ".github/fixtures/dispatch_810/dispatch_810_20261106.md"
COPY_SHA256 = "6812b2b25843eef76f5388a67ed21a71ba51c418b3f5ad386a19dbe3a8794361"
COPY_BYTES = 9288
HOUSE_PIN = "6812b2b25843eef7"
#: The original, under the Business Apparatus root (signed_strings_check --source-root).
SOURCE_PATH = (
    "00_Operating_Model/CCO_DISPATCH_810_809_HANDBACK_3_RULED_Q_DEPLOY_B_BY_FACT_FIVE_PRS_"
    "CLEARED_31_PRE_ENGINE_SENTINEL_CLASSED_THREE_WITHDRAWN_RPS_NOTE_SIGNED_AUDIT_KINDS_"
    "PERMANENT_MIGRATION_RUN_BURN_RULE_20261106.md"
)
TAG = "810 section 4"
ID_PREFIX = "810-"
#: The line of the copy that carries both strings ("Corporate #24 (after #23)").
LINE = 26

#: A signed string in 810 is set as *"..."*; its text holds no ASCII double quote.
QUOTED = r'\*"([^"]+)"\*'

#: One row per signed string: the 810 line, the pattern (group 1 is the string), targets.
ROWS: tuple[dict[str, Any], ...] = (
    {
        "id": "810-privacy-updated",
        "label": "810 section 4: privacy-policy.html header, its last-updated date and version",
        "line": LINE,
        "pattern": r"the Privacy Policy header " + QUOTED,
        "targets": [("site/privacy-policy.html", "html_text", 1)],
    },
    {
        "id": "810-ap2",
        "label": "810 section 4: spec.html, the AP2 mandate claim-state (was :7, :55, :71)",
        "line": LINE,
        "pattern": r"an AP2 mandate is " + QUOTED,
        "targets": [
            ("site/spec.html", "html_text", 2),
            ("site/spec.html", "meta_description", 1),
        ],
    },
)

#: The checks this PR adds: the AP2 wording that is gone, and the header's date.
CHECKS: dict[str, list[dict[str, str]]] = {
    "absent": [
        {"file": "site/spec.html", "text": "AP2 mandate compatible"},
        {"file": "site/spec.html", "text": "recorded as evidence of delegated authority"},
        {"file": "site/spec.html", "text": "AP2 mandate signature verification failed"},
        {"file": "site/spec.html", "text": "MANDATE_INVALID_SIGNATURE"},
        {"file": "site/privacy-policy.html", "text": "last updated 2026-10-31"},
        {"file": "site/privacy-policy.html", "text": "<strong>Last Updated</strong>2026-10-31"},
    ],
    "present": [
        {
            "file": "site/privacy-policy.html",
            "text": "<div><strong>Last Updated</strong>2026-11-06</div>",
            "why": "810 section 4: the header's date, in the page's metadata block too",
        },
        {
            "file": "site/privacy-policy.html",
            "text": "<div><strong>Version</strong>v1.3</div>",
            "why": "810 section 4: the version stays v1.3",
        },
    ],
}


class Refused(Exception):
    """The copy, a line or a pattern is not as expected."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_copy(raw: bytes) -> list[str]:
    """Failures of the byte copy against its recorded size, digest and house pin."""
    lf = raw.replace(b"\r\n", b"\n")
    problems: list[str] = []
    if len(lf) != COPY_BYTES:
        problems.append(f"COPY: {len(lf)} bytes after CRLF to LF, expected {COPY_BYTES}")
    if _sha(lf) != COPY_SHA256:
        problems.append("COPY: sha256 after CRLF to LF differs from the recorded one")
    if _sha(lf)[:16] != HOUSE_PIN:
        problems.append(f"COPY: house pin {_sha(lf)[:16]}, expected {HOUSE_PIN}")
    return problems


def build(raw: bytes) -> list[dict[str, Any]]:
    """The 810 rows extracted from the copy."""
    lines = raw.decode("utf-8").split("\n")
    rows: list[dict[str, Any]] = []
    for spec in ROWS:
        no = int(spec["line"])
        line = lines[no - 1].rstrip("\r") if 0 < no <= len(lines) else ""
        extract = {"kind": "regex", "pattern": spec["pattern"], "group": 1}
        try:
            extracted = ssc.apply_extract(line, extract)
        except ValueError as exc:
            raise Refused(f"{spec['id']}: line {no}: {exc}") from None
        transforms: list[dict[str, str]] = []
        try:
            string = ssc.apply_transforms(extracted, transforms)
        except ValueError as exc:
            raise Refused(f"{spec['id']}: {exc}") from None
        rows.append(
            {
                "id": spec["id"],
                "label": spec["label"],
                "source_path": SOURCE_PATH,
                "source_copy": COPY_REL,
                "source_line": no,
                "source_line_sha256": _sha(line.encode("utf-8")),
                "extract": extract,
                "extracted": extracted,
                "transforms": transforms,
                "string": string,
                "string_sha256": _sha(string.encode("utf-8")),
                "targets": [
                    {"file": f, "surface": s, "count": c} for f, s, c in spec["targets"]
                ],
            }
        )
    return rows


def tagged_checks() -> dict[str, list[dict[str, str]]]:
    return {
        kind: [{**item, "source": TAG} for item in items] for kind, items in CHECKS.items()
    }


def merge(fixture: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The fixture with its 810 rows and 810 checks replaced by ``rows`` and CHECKS."""
    out = copy.deepcopy(fixture)
    out["entries"] = [
        e for e in out["entries"] if not str(e["id"]).startswith(ID_PREFIX)
    ] + rows
    checks = out.setdefault("checks", {})
    for kind, items in tagged_checks().items():
        kept = [i for i in checks.get(kind, []) if i.get("source") != TAG]
        checks[kind] = kept + items
    return out


def compare(fixture: dict[str, Any], raw: bytes) -> list[str]:
    """Failures of the fixture's 810 rows and checks against a fresh extraction."""
    problems = verify_copy(raw)
    current = [e for e in fixture["entries"] if str(e["id"]).startswith(ID_PREFIX)]
    try:
        expected = build(raw)
    except Refused as exc:
        return problems + [f"EXTRACT: {exc}"]
    want_ids = [r["id"] for r in expected]
    have_ids = [e["id"] for e in current]
    if have_ids != want_ids:
        problems.append(f"ROWS: fixture has {have_ids}, extraction gives {want_ids}")
    for want, have in zip(expected, current):
        if want != have:
            keys = sorted(k for k in set(want) | set(have) if want.get(k) != have.get(k))
            problems.append(f"ROW[{want['id']}]: differs from a fresh extraction in {keys}")
    checks = fixture.get("checks", {})
    for kind, items in tagged_checks().items():
        have_items = [i for i in checks.get(kind, []) if i.get("source") == TAG]
        if have_items != items:
            problems.append(f"CHECKS[{kind}]: the 810 items differ from this script's")
    return problems


def self_test(fixture: dict[str, Any], raw: bytes) -> list[str]:
    """Each planted failure must be reported; returns the ones that were not."""
    missed: list[str] = []
    line = raw.split(b"\n")[LINE - 1]
    at = raw.index(line) + line.index(b"unverified context")
    flipped = raw[:at] + (b"U" if raw[at : at + 1] != b"U" else b"V") + raw[at + 1 :]
    if not any(p.startswith("COPY:") for p in compare(fixture, flipped)):
        missed.append("a copy with one byte changed was not reported")
    mutated = copy.deepcopy(fixture)
    row = next(e for e in mutated["entries"] if e["id"] == "810-ap2")
    mid = len(row["string"]) // 2
    row["string"] = row["string"][:mid] + "X" + row["string"][mid + 1 :]
    if not any(p.startswith("ROW[810-ap2]") for p in compare(mutated, raw)):
        missed.append("a row whose string has one character changed was not reported")
    seg = re.search(ROWS[1]["pattern"].encode("utf-8"), line)
    doubled = raw.replace(line, line + b" " + (seg.group(0) if seg else b""), 1)
    if not any("matched 2 times" in p for p in compare(fixture, doubled)):
        missed.append("a pattern matching twice on its line was not reported")
    return missed


def _dump(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="rewrite the 810 rows")
    mode.add_argument("--check", action="store_true", help="rows equal a fresh extraction")
    mode.add_argument("--self-test", action="store_true", help="prove --check can fail")
    args = parser.parse_args(argv)
    raw = (REPO_ROOT / COPY_REL).read_bytes()
    fixture: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if args.write:
        problems = verify_copy(raw)
        if problems:
            for p in problems:
                print(f"  {p}")
            print("810 STRINGS: REFUSED (the copy is not the dispatch of record)")
            return 1
        try:
            rows = build(raw)
        except Refused as exc:
            print(f"810 STRINGS: REFUSED ({exc})")
            return 1
        FIXTURE.write_bytes(_dump(merge(fixture, rows)).encode("utf-8"))
        for r in rows:
            print(f"  {r['id']}: {r['string']}")
        print(f"810 STRINGS: WRITTEN ({len(rows)} rows)")
        return 0
    if args.self_test:
        missed = self_test(fixture, raw)
        for m in missed:
            print(f"  {m}")
        print(
            f"810 STRINGS SELF-TEST: {'FAIL' if missed else 'OK'} (3 planted failures, "
            f"{len(missed)} not reported)"
        )
        return 1 if missed else 0
    problems = compare(fixture, raw)
    for p in problems:
        print(f"  {p}")
    n_rows = sum(1 for e in fixture["entries"] if str(e["id"]).startswith(ID_PREFIX))
    print(
        f"810 STRINGS: {'FAIL' if problems else 'OK'} ({n_rows} rows and the 810 checks "
        f"equal a fresh extraction from {COPY_REL}; {len(problems)} failed)"
    )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
