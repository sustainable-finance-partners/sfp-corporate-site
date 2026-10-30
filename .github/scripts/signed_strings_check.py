"""Signed legal strings render verbatim on this site.

Reads .github/signed_strings.json. Each entry is a counsel-approved or signed string,
extracted from one line of its source document. For every entry this check asserts:

1. the fixture is self-consistent: the recorded transforms applied to the extracted
   text give the string, and the string's sha256 is the recorded one;
2. the string renders verbatim, the recorded number of times, on each target surface:
   - ``html_text``: the page's text content (tags removed, entities decoded, script
     and style content excluded, runs of whitespace read as one space);
   - ``meta_description``: the ``content`` of ``<meta name="description">``;
   - ``jsonld_organization_description``: ``description`` of the Organization JSON-LD;
   - ``txt_comment_text``: the text of a ``.txt`` file's ``#`` comment lines;
3. with ``--source-root DIR`` (the desk, where the source documents live): the source
   line's sha256 matches, and extracting from it again gives the same text.

The ``checks`` block adds plain-text absences (replaced wording must be gone),
presences (facts and lines that must stay) and absent patterns.

``--self-test`` proves the matcher can fail: every string with one character changed
must be reported missing. A check that cannot fail is not a check.

Exit code 0 only when every assertion holds. Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / ".github" / "signed_strings.json"


class _Page(HTMLParser):
    """Collects text content, the meta description and the JSON-LD blocks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.meta_description: list[str] = []
        self.jsonld: list[str] = []
        self._skip_depth = 0
        self._in_jsonld = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k: (v or "") for k, v in attrs}
        if tag == "meta" and attr.get("name") == "description":
            self.meta_description.append(attr.get("content", ""))
        if tag in ("script", "style"):
            self._skip_depth += 1
            self._in_jsonld = tag == "script" and attr.get("type") == "application/ld+json"
            if self._in_jsonld:
                self.jsonld.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip_depth:
            self._skip_depth -= 1
            self._in_jsonld = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            if self._in_jsonld:
                self.jsonld[-1] += data
            return
        self.text_parts.append(data)


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def surface_text(path: Path, surface: str) -> list[str]:
    """The text(s) of one surface of one file; a string is searched in each."""
    raw = path.read_text(encoding="utf-8")
    if surface == "txt_comment_text":
        lines = [ln.rstrip("\r") for ln in raw.split("\n")]
        return ["\n".join(ln[1:].lstrip(" ") for ln in lines if ln.startswith("#"))]
    page = _Page()
    page.feed(raw)
    page.close()
    if surface == "html_text":
        return [_collapse("".join(page.text_parts))]
    if surface == "meta_description":
        return page.meta_description
    if surface == "jsonld_organization_description":
        out: list[str] = []
        for block in page.jsonld:
            data: Any = json.loads(block)
            if isinstance(data, dict) and data.get("@type") == "Organization":
                out.append(str(data.get("description", "")))
        return out
    raise ValueError(f"unknown surface {surface!r}")


def apply_extract(line: str, extract: dict[str, Any]) -> str:
    kind = extract["kind"]
    if kind == "after_prefix":
        prefix = str(extract["prefix"])
        if not line.startswith(prefix):
            raise ValueError(f"source line does not start with {prefix!r}")
        return line[len(prefix) :]
    if kind == "regex":
        matches = re.findall(str(extract["pattern"]), line)
        if len(matches) != 1:
            raise ValueError(f"pattern matched {len(matches)} times, expected 1")
        return str(matches[0])
    raise ValueError(f"unknown extract kind {kind!r}")


def apply_transforms(text: str, transforms: list[dict[str, Any]]) -> str:
    for step in transforms:
        kind = step["kind"]
        if kind == "replace":
            old, new = str(step["old"]), str(step["new"])
            if text.count(old) != 1:
                raise ValueError(f"transform anchor {old!r} occurs {text.count(old)} times")
            text = text.replace(old, new)
        elif kind == "drop_markdown":
            text = text.replace("**", "").replace("`", "")
        else:
            raise ValueError(f"unknown transform kind {kind!r}")
    return text


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check(fixture: dict[str, Any], source_root: Path | None) -> tuple[list[str], int]:
    """Return (failures, assertions made)."""
    failures: list[str] = []
    made = 0
    cache: dict[tuple[str, str], list[str]] = {}

    def texts(rel: str, surface: str) -> list[str]:
        key = (rel, surface)
        if key not in cache:
            cache[key] = surface_text(REPO_ROOT / rel, surface)
        return cache[key]

    for entry in fixture["entries"]:
        eid = str(entry["id"])
        string = str(entry["string"])
        made += 1
        try:
            rebuilt = apply_transforms(str(entry["extracted"]), list(entry["transforms"]))
        except ValueError as exc:
            failures.append(f"FIXTURE[{eid}]: {exc}")
            rebuilt = None
        if rebuilt is not None and rebuilt != string:
            failures.append(f"FIXTURE[{eid}]: transforms of the extracted text do not give the string")
        made += 1
        if _sha(string) != entry["string_sha256"]:
            failures.append(f"FIXTURE[{eid}]: string sha256 differs from the recorded one")
        if source_root is not None:
            made += 1
            src = source_root / str(entry["source_path"])
            if not src.is_file():
                failures.append(f"SOURCE[{eid}]: {entry['source_path']} not found under {source_root}")
            else:
                lines = src.read_bytes().decode("utf-8").split("\n")
                no = int(entry["source_line"])
                line = lines[no - 1].rstrip("\r") if 0 < no <= len(lines) else ""
                if _sha(line) != entry["source_line_sha256"]:
                    failures.append(f"SOURCE[{eid}]: line {no} sha256 differs (the source moved or changed)")
                else:
                    try:
                        if apply_extract(line, dict(entry["extract"])) != entry["extracted"]:
                            failures.append(f"SOURCE[{eid}]: extraction from line {no} differs")
                    except ValueError as exc:
                        failures.append(f"SOURCE[{eid}]: {exc}")
        for target in entry["targets"]:
            made += 1
            rel, surface, want = str(target["file"]), str(target["surface"]), int(target["count"])
            found = sum(t.count(string) for t in texts(rel, surface))
            if found != want:
                failures.append(f"RENDER[{eid}] {rel} {surface}: found {found}, expected {want}")

    checks = fixture.get("checks", {})
    for item in checks.get("absent", []):
        made += 1
        body = (REPO_ROOT / str(item["file"])).read_text(encoding="utf-8").replace("\r\n", "\n")
        if str(item["text"]) in body:
            failures.append(f"ABSENT {item['file']}: still contains {item['text']!r}")
    for item in checks.get("present", []):
        made += 1
        body = (REPO_ROOT / str(item["file"])).read_text(encoding="utf-8").replace("\r\n", "\n")
        if str(item["text"]) not in body:
            failures.append(f"PRESENT {item['file']}: missing {str(item['text'])[:80]!r}")
    for item in checks.get("absent_regex", []):
        made += 1
        body = (REPO_ROOT / str(item["file"])).read_text(encoding="utf-8")
        hit = re.search(str(item["pattern"]), body)
        if hit:
            failures.append(f"ABSENT-RE {item['file']}: {hit.group(0)!r} ({item.get('why', '')})")
    return failures, made


def self_test(fixture: dict[str, Any]) -> list[str]:
    """Every string, with one character changed, must be reported missing."""
    problems: list[str] = []
    for entry in fixture["entries"]:
        string = str(entry["string"])
        mid = len(string) // 2
        mutated = string[:mid] + ("X" if string[mid] != "X" else "Y") + string[mid + 1 :]
        probe = dict(entry)
        probe["string"] = mutated
        probe["string_sha256"] = _sha(mutated)
        probe["extracted"] = mutated
        probe["transforms"] = []
        failures, _ = check({"entries": [probe], "checks": {}}, None)
        if not any(f.startswith(f"RENDER[{entry['id']}]") for f in failures):
            problems.append(f"SELF-TEST[{entry['id']}]: a changed string was not reported missing")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, help="directory holding the source documents")
    parser.add_argument("--self-test", action="store_true", help="prove the matcher can fail")
    args = parser.parse_args(argv)
    fixture: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if args.self_test:
        problems = self_test(fixture)
        for line in problems:
            print(f"  {line}")
        print(f"SIGNED STRINGS SELF-TEST: {'FAIL' if problems else 'OK'} ({len(fixture['entries'])} mutations)")
        return 1 if problems else 0
    failures, made = check(fixture, args.source_root)
    mode = "with source lines" if args.source_root else "fixture + render"
    for line in failures:
        print(f"  {line}")
    verdict = "FAIL" if failures else "OK"
    print(
        f"SIGNED STRINGS: {verdict} ({len(fixture['entries'])} strings, {made} assertions, "
        f"{len(failures)} failed; {mode})"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
