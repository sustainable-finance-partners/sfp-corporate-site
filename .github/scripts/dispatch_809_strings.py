"""The 809 section 7 signed strings, extracted from a byte copy of the dispatch.

COO dispatch 809 section 7 (2026-11-06) supplies this site's status strings, and every
sentence the COO signed renders byte for byte. This script is the only author of the
809 rows of .github/signed_strings.json. It reads the byte copy at
.github/fixtures/dispatch_809/, checks the copy's SHA-256 and house pin (sha256 after
CRLF to LF, first 16 hex), extracts each string from its line with one regex that must
match exactly once, and writes the rows. No string is typed here: each row names a
line and a pattern. .github/scripts/signed_strings_check.py then proves that each
string renders at its targets, and with --source-root re-extracts it from the original.

The register sentence is the signed template "The register holds {n} records as of
{date}." filled from one read of the live scorecard: aggregate_stats.forecast_count and
the UTC date of metadata.generated_at, the fields the /deploy page renders. The read is
recorded in the row's "derivation", and the two values are the row's transforms.

The checks block also gains the 809 absences (the replaced wording is gone), presences
(the lines this PR composes from 809's rule rather than copies) and absent patterns.
Each carries "source": "809 section 7" so a rewrite replaces exactly these.

Usage:
  python3 .github/scripts/dispatch_809_strings.py --write --scorecard FILE
  python3 .github/scripts/dispatch_809_strings.py --check
  python3 .github/scripts/dispatch_809_strings.py --self-test

--check (CI): the copy hashes to its recorded digest, and the 809 rows and checks in the
fixture equal a fresh extraction from the copy, in order and byte for byte. --self-test:
a copy with one byte changed, a row whose string has one character changed, and a line
on which a pattern matches twice must each be reported. Exit 0 only when all holds.
Standard library only.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
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
COPY_REL = ".github/fixtures/dispatch_809/dispatch_809_20261106.md"
COPY_SHA256 = "c7271feef01379d7cd103a4a56df0ebb4bef4fa50d30af5f098ed1daceed2ae0"
COPY_BYTES = 15277
HOUSE_PIN = "c7271feef01379d7"
#: The original, under the Business Apparatus root (signed_strings_check --source-root).
SOURCE_PATH = (
    "00_Operating_Model/CCO_DISPATCH_809_808_HANDBACK_2_RULED_610_LIVE_NSF_00132689_"
    "SUBMITTED_BLOOMBERGNEF_NOTES_SIGNED_RETENTION_PERMANENT_RECORD_CLASS_VS_ORIGIN_"
    "INTERNAL_NAMES_RULES_SITE_STRINGS_SUPPLIED_DEPLOY_HOOK_Q_20261106.md"
)
TAG = "809 section 7"
SCORECARD_URL = "https://api.phronesisintel.com/.well-known/scorecard.json"
ID_PREFIX = "809-"

#: A signed string in 809 is set as *"..."*; its text holds no ASCII double quote.
QUOTED = r'\*"([^"]+)"\*'

#: One row per signed string: the 809 line, the pattern (group 1 is the string), targets.
ROWS: tuple[dict[str, Any], ...] = (
    {
        "id": "809-p1",
        "label": "809 section 7: index.html P1 status line (was :158)",
        "line": 40,
        "pattern": r':158 "[^"]*" → ' + QUOTED,
        "targets": [("site/index.html", "html_text", 1)],
    },
    {
        "id": "809-p1-clause",
        "label": "809 section 7: the P1 sentence after its name, on the machine-readable "
        "surfaces (agents.txt Path A, agentic-commerce.json path A)",
        "line": 40,
        "pattern": r':158 "[^"]*" → \*"P1 Identity & Mandate — ([^"]+)"\*',
        "targets": [
            ("site/.well-known/agents.txt", "txt_comment_text", 1),
            ("site/.well-known/agentic-commerce.json", "json_strings", 1),
        ],
    },
    {
        "id": "809-p3",
        "label": "809 section 7: index.html P3 status line (was :160)",
        "line": 40,
        "pattern": r':160 "[^"]*" → ' + QUOTED,
        "targets": [("site/index.html", "html_text", 1)],
    },
    {
        "id": "809-verticals",
        "label": "809 section 7: index.html verticals heading (was :166)",
        "line": 40,
        "pattern": r':166 "[^"]*" → ' + QUOTED,
        "targets": [("site/index.html", "html_text", 1)],
    },
    {
        "id": "809-healthcare",
        "label": "809 section 7: index.html V#3 name (was :171)",
        "line": 40,
        "pattern": r':171 "[^"]*" → ' + QUOTED,
        "targets": [("site/index.html", "html_text", 1)],
    },
    {
        "id": "809-register",
        "label": "809 section 7: index.html product-surface card, the register sentence (was :214)",
        "line": 40,
        "pattern": r"the live `/deploy` sentence \(" + QUOTED,
        "targets": [("site/index.html", "html_text", 1)],
        "register": True,
    },
    {
        "id": "809-catalogued",
        "label": "809 section 7: index.html product-surface card, the catalogued sentence (was :214)",
        "line": 40,
        "pattern": r"its as-of date\) \+ " + QUOTED,
        "targets": [("site/index.html", "html_text", 1)],
    },
    {
        "id": "809-privacy-phi",
        "label": "809 section 7: privacy-policy.html PHI item (was :104)",
        "line": 40,
        "pattern": r"\*\*privacy-policy :104\*\* → " + QUOTED,
        "targets": [("site/privacy-policy.html", "html_text", 1)],
    },
    {
        "id": "809-privacy-meta",
        "label": "809 section 7: privacy-policy.html meta description, the PHI sentence",
        "line": 40,
        "pattern": r'"PHI excluded under HIPAA Safe Harbor" → ' + QUOTED,
        "targets": [("site/privacy-policy.html", "meta_description", 1)],
    },
)

#: The checks this PR adds. Presences are the lines composed from 809's rule, not copied.
CHECKS: dict[str, list[dict[str, str]]] = {
    "absent": [
        {"file": "site/index.html", "text": "— LIVE."},
        {"file": "site/index.html", "text": "all LIVE on production"},
        {"file": "site/index.html", "text": "Phronesis is LIVE on production"},
        {"file": "site/index.html", "text": "every mint primary-source-cited"},
        {"file": "site/index.html", "text": "in production since"},
        {"file": "site/index.html", "text": "HIPAA Safe Harbor"},
        {"file": "site/spec.html", "text": "all twelve LIVE on production"},
        {"file": "site/spec.html", "text": "for live status"},
        {"file": "site/privacy-policy.html", "text": "HIPAA Safe Harbor"},
        {"file": "site/privacy-policy.html", "text": "Themis-Healthcare"},
        {"file": "site/privacy-policy.html", "text": "PHI excluded under"},
        {"file": "site/.well-known/agentic-commerce.json", "text": '"verticals_live"'},
        {
            "file": "site/.well-known/agentic-commerce.json",
            "text": "Direct API access via AP2 mandate authorization",
        },
        {
            "file": "site/.well-known/agents.txt",
            "text": "recorded as evidence of delegated authority",
        },
        {"file": "site/.well-known/agents.txt", "text": "Auth-Methods: AP2,"},
    ],
    "present": [
        {
            "file": "site/.well-known/agentic-commerce.json",
            "text": '"layer_1_authorization_availability": "planned"',
            "why": "809 section 7: mandate verification is planned (a stub at bda96164)",
        },
        {
            "file": "site/.well-known/agentic-commerce.json",
            "text": '"ap2_mandate": "planned"',
            "why": "809 section 7: mandate verification is planned",
        },
        {
            "file": "site/.well-known/agents.txt",
            "text": "Auth-Methods: AP2 (planned), Stripe-SPT (in build), Bearer-JWT",
            "why": "809 section 7: mandate verification is planned",
        },
        {
            "file": "site/index.html",
            "text": "<li><strong>P6 Market-State Telemetry</strong> — defined. "
            "The agentic-marketplace microstructure feed.</li>",
            "why": "809 section 7: P6 takes the status word the code supports; no route "
            "serves it at bda96164, so 'defined'",
        },
        {
            "file": "site/index.html",
            "text": "<li><strong>V#3</strong> Healthcare</li>",
            "why": "809 section 7: the V#3 name alone",
        },
        {
            "file": "site/spec.html",
            "text": "<p>Twelve verticals; all twelve catalogued; archetype taxonomy is "
            'per-vertical. See the home page <a href="/#phronesis">vertical lineup</a>; '
            'records by vertical at <a href="https://phronesisintel.com/verticals" '
            'rel="noopener">phronesisintel.com/verticals</a>.</p>',
            "why": "809 section 7: spec:104 under the same rule (catalogued; records by "
            "vertical at phronesisintel.com/verticals)",
        },
    ],
    "absent_regex": [
        {
            "file": "site/.well-known/agentic-commerce.json",
            "pattern": r'"primitives_live":\s*\[[^\]]*"P[126]-',
            "why": "809 section 7: only P3 is live; P1 is partial, P2 in build, P6 defined",
        },
        {
            "file": "site/.well-known/agentic-commerce.json",
            "pattern": r'"supported_methods":\s*\[\s*"ap2_mandate"',
            "why": "809 section 7: mandate verification is planned, not a live method",
        },
        {
            "file": "site/index.html",
            "pattern": r"\bLIVE\b",
            "why": "809 section 7: no primitive or vertical reads LIVE",
        },
        {
            "file": "site/spec.html",
            "pattern": r"\bLIVE\b",
            "why": "809 section 7: no primitive or vertical reads LIVE",
        },
    ],
}


class Refused(Exception):
    """The copy, a line, a pattern or the scorecard read is not as expected."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_copy(raw: bytes) -> list[str]:
    """Failures of the byte copy against its recorded size, digest and house pin."""
    lf = raw.replace(b"\r\n", b"\n")
    problems: list[str] = []
    if len(lf) != COPY_BYTES:
        problems.append(
            f"COPY: {len(lf)} bytes after CRLF to LF, expected {COPY_BYTES}"
        )
    if _sha(lf) != COPY_SHA256:
        problems.append("COPY: sha256 after CRLF to LF differs from the recorded one")
    if _sha(lf)[:16] != HOUSE_PIN:
        problems.append(f"COPY: house pin {_sha(lf)[:16]}, expected {HOUSE_PIN}")
    return problems


def read_scorecard(data: Any, today: dt.date) -> dict[str, Any]:
    """The register count and its UTC date from a scorecard payload, or Refused."""
    if not isinstance(data, dict):
        raise Refused("the scorecard payload is not a JSON object")
    stats = data.get("aggregate_stats")
    if not isinstance(stats, dict) or "forecast_count" not in stats:
        raise Refused("aggregate_stats.forecast_count is absent")
    n = stats["forecast_count"]
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise Refused(
            f"aggregate_stats.forecast_count is not a positive integer: {n!r}"
        )
    meta = data.get("metadata")
    generated = meta.get("generated_at") if isinstance(meta, dict) else None
    if not isinstance(generated, str):
        raise Refused("metadata.generated_at is absent")
    try:
        stamp = dt.datetime.fromisoformat(generated.replace("Z", "+00:00"))
    except ValueError:
        raise Refused(
            f"metadata.generated_at is not a timestamp: {generated!r}"
        ) from None
    if stamp.tzinfo is None:
        raise Refused(f"metadata.generated_at carries no zone: {generated!r}")
    day = stamp.astimezone(dt.timezone.utc).date()
    if day > today:
        raise Refused(f"metadata.generated_at is later than today: {generated!r}")
    return {"n": n, "date": day.isoformat(), "generated_at": generated}


def build(raw: bytes, register: dict[str, Any]) -> list[dict[str, Any]]:
    """The 809 rows extracted from the copy; ``register`` fills the register template."""
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
        row: dict[str, Any] = {
            "id": spec["id"],
            "label": spec["label"],
            "source_path": SOURCE_PATH,
            "source_copy": COPY_REL,
            "source_line": no,
            "source_line_sha256": _sha(line.encode("utf-8")),
            "extract": extract,
            "extracted": extracted,
        }
        if spec.get("register"):
            transforms = [
                {"kind": "replace", "old": "{n}", "new": str(register["n"])},
                {"kind": "replace", "old": "{date}", "new": str(register["date"])},
            ]
            row["derivation"] = {
                "url": SCORECARD_URL,
                "fields": "aggregate_stats.forecast_count; UTC date of metadata.generated_at",
                "n": register["n"],
                "date": register["date"],
                "generated_at": register["generated_at"],
                "body_sha256": register["body_sha256"],
            }
        row["transforms"] = transforms
        try:
            string = ssc.apply_transforms(extracted, transforms)
        except ValueError as exc:
            raise Refused(f"{spec['id']}: {exc}") from None
        row["string"] = string
        row["string_sha256"] = _sha(string.encode("utf-8"))
        row["targets"] = [
            {"file": f, "surface": s, "count": c} for f, s, c in spec["targets"]
        ]
        rows.append(row)
    return rows


def tagged_checks() -> dict[str, list[dict[str, str]]]:
    return {
        kind: [{**item, "source": TAG} for item in items]
        for kind, items in CHECKS.items()
    }


def merge(fixture: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The fixture with its 809 rows and 809 checks replaced by ``rows`` and CHECKS."""
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
    """Failures of the fixture's 809 rows and checks against a fresh extraction."""
    problems = verify_copy(raw)
    current = [e for e in fixture["entries"] if str(e["id"]).startswith(ID_PREFIX)]
    reg = next((e for e in current if e["id"] == "809-register"), None)
    derivation = reg.get("derivation") if isinstance(reg, dict) else None
    if not isinstance(derivation, dict):
        return problems + ["ROW[809-register]: no derivation recorded"]
    try:
        expected = build(raw, derivation)
    except Refused as exc:
        return problems + [f"EXTRACT: {exc}"]
    want_ids = [r["id"] for r in expected]
    have_ids = [e["id"] for e in current]
    if have_ids != want_ids:
        problems.append(f"ROWS: fixture has {have_ids}, extraction gives {want_ids}")
    for want, have in zip(expected, current):
        if want != have:
            keys = sorted(
                k for k in set(want) | set(have) if want.get(k) != have.get(k)
            )
            problems.append(
                f"ROW[{want['id']}]: differs from a fresh extraction in {keys}"
            )
    checks = fixture.get("checks", {})
    for kind, items in tagged_checks().items():
        have_items = [i for i in checks.get(kind, []) if i.get("source") == TAG]
        if have_items != items:
            problems.append(f"CHECKS[{kind}]: the 809 items differ from this script's")
    return problems


def self_test(fixture: dict[str, Any], raw: bytes) -> list[str]:
    """Each planted failure must be reported; returns the ones that were not."""
    missed: list[str] = []
    line40 = raw.split(b"\n")[39]
    at = raw.index(line40) + line40.index(b"identity live")
    flipped = raw[:at] + (b"I" if raw[at : at + 1] != b"I" else b"J") + raw[at + 1 :]
    if not any(p.startswith("COPY:") for p in compare(fixture, flipped)):
        missed.append("a copy with one byte changed was not reported")
    mutated = copy.deepcopy(fixture)
    row = next(e for e in mutated["entries"] if e["id"] == "809-p3")
    mid = len(row["string"]) // 2
    row["string"] = row["string"][:mid] + "X" + row["string"][mid + 1 :]
    if not any(p.startswith("ROW[809-p3]") for p in compare(mutated, raw)):
        missed.append("a row whose string has one character changed was not reported")
    seg = re.search(ROWS[1]["pattern"].encode("utf-8"), line40)
    doubled = raw.replace(line40, line40 + b" " + (seg.group(0) if seg else b""), 1)
    if not any("matched 2 times" in p for p in compare(fixture, doubled)):
        missed.append("a pattern matching twice on its line was not reported")
    return missed


def _dump(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="rewrite the 809 rows")
    mode.add_argument(
        "--check", action="store_true", help="rows equal a fresh extraction"
    )
    mode.add_argument("--self-test", action="store_true", help="prove --check can fail")
    parser.add_argument(
        "--scorecard", type=Path, help="a saved read of the live scorecard"
    )
    args = parser.parse_args(argv)
    raw = (REPO_ROOT / COPY_REL).read_bytes()
    fixture: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if args.write:
        if args.scorecard is None:
            parser.error(
                "--write needs --scorecard FILE (a saved read of the scorecard)"
            )
        problems = verify_copy(raw)
        if problems:
            for p in problems:
                print(f"  {p}")
            print("809 STRINGS: REFUSED (the copy is not the dispatch of record)")
            return 1
        body = args.scorecard.read_bytes()
        try:
            register = read_scorecard(
                json.loads(body), dt.datetime.now(dt.timezone.utc).date()
            )
            register["body_sha256"] = _sha(body)
            rows = build(raw, register)
        except Refused as exc:
            print(f"809 STRINGS: REFUSED ({exc})")
            return 1
        FIXTURE.write_bytes(_dump(merge(fixture, rows)).encode("utf-8"))
        for r in rows:
            print(f"  {r['id']}: {r['string']}")
        print(
            f"809 STRINGS: WRITTEN ({len(rows)} rows; register n={register['n']} "
            f"as of {register['date']})"
        )
        return 0
    if args.self_test:
        missed = self_test(fixture, raw)
        for m in missed:
            print(f"  {m}")
        print(
            f"809 STRINGS SELF-TEST: {'FAIL' if missed else 'OK'} (3 planted failures, "
            f"{len(missed)} not reported)"
        )
        return 1 if missed else 0
    problems = compare(fixture, raw)
    for p in problems:
        print(f"  {p}")
    n_rows = sum(1 for e in fixture["entries"] if str(e["id"]).startswith(ID_PREFIX))
    print(
        f"809 STRINGS: {'FAIL' if problems else 'OK'} ({n_rows} rows and the 809 checks "
        f"equal a fresh extraction from {COPY_REL}; {len(problems)} failed)"
    )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
