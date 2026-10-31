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
   - ``whole_line``: the file's lines; ``count`` is the number of lines that equal
     the string exactly, so nothing else sits on that line;
3. with ``--source-root DIR`` (the desk, where the source documents live): the source
   line's sha256 matches, and extracting from it again gives the same text. A
   ``regex`` extraction must match exactly once; it returns the match's ``group``
   (default 0, the whole match). A group that is not an integer (null, a float, a
   bool, a string), one the pattern does not have, or a negative one, is reported as
   that entry's SOURCE failure, and the run goes on.

The ``checks`` block adds plain-text absences (replaced wording must be gone),
presences (facts and lines that must stay) and absent patterns.

``--self-test`` proves that the branches below can fail. It does not cover every
branch: the last sentence names the ones it leaves out. Every string with one
character changed must be reported missing at each target. For every ``whole_line``
target, a copy of the file whose string line carries a suffix (``string + " x"``),
and one whose line carries a prefix (``"x " + string``), must each be reported at
that target. For every file the ``checks`` block reads, a text known to be in the
file, entered as an absence, must be reported; a text known not to be in it, entered
as a presence, must be reported; and a pattern that matches it, entered as an absent
pattern, must be reported. A planted source line whose extraction names group 9,
group -1, null, 1.5, true or "1" must each be reported as a SOURCE failure. No probe
covers the FIXTURE checks (the recorded transforms, and the string's sha256), the
SOURCE line-sha check, the SOURCE extraction-differs compare and the SOURCE not-found
branch: disabling any one of them leaves ``--self-test`` OK, so for those it proves
nothing.

Exit code 0 only when every assertion holds. Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
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
    if surface == "whole_line":
        return [ln.rstrip("\r") for ln in raw.split("\n")]
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
        matches = list(re.finditer(str(extract["pattern"]), line))
        if len(matches) != 1:
            raise ValueError(f"pattern matched {len(matches)} times, expected 1")
        raw = extract.get("group", 0)
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise ValueError(f"group must be an integer, got {raw!r}")
        group = raw
        if group < 0:
            raise ValueError(f"pattern has no group {group}")
        try:
            value = matches[0].group(group)
        except IndexError:
            raise ValueError(f"pattern has no group {group}") from None
        if value is None:
            raise ValueError(f"group {group} did not take part in the match")
        return str(value)
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


def check(
    fixture: dict[str, Any], source_root: Path | None, root: Path = REPO_ROOT
) -> tuple[list[str], int]:
    """Return (failures, assertions made). Target and checks files are read under ``root``."""
    failures: list[str] = []
    made = 0
    cache: dict[tuple[str, str], list[str]] = {}

    def texts(rel: str, surface: str) -> list[str]:
        key = (rel, surface)
        if key not in cache:
            cache[key] = surface_text(root / rel, surface)
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
            if surface == "whole_line":
                found = sum(1 for t in texts(rel, surface) if t == string)
            else:
                found = sum(t.count(string) for t in texts(rel, surface))
            if found != want:
                failures.append(f"RENDER[{eid}] {rel} {surface}: found {found}, expected {want}")

    checks = fixture.get("checks", {})
    for item in checks.get("absent", []):
        made += 1
        body = (root / str(item["file"])).read_text(encoding="utf-8").replace("\r\n", "\n")
        if str(item["text"]) in body:
            failures.append(f"ABSENT {item['file']}: still contains {item['text']!r}")
    for item in checks.get("present", []):
        made += 1
        body = (root / str(item["file"])).read_text(encoding="utf-8").replace("\r\n", "\n")
        if str(item["text"]) not in body:
            failures.append(f"PRESENT {item['file']}: missing {str(item['text'])[:80]!r}")
    for item in checks.get("absent_regex", []):
        made += 1
        body = (root / str(item["file"])).read_text(encoding="utf-8")
        hit = re.search(str(item["pattern"]), body)
        if hit:
            failures.append(f"ABSENT-RE {item['file']}: {hit.group(0)!r} ({item.get('why', '')})")
    return failures, made


def check_files(fixture: dict[str, Any]) -> list[str]:
    """Every file the ``checks`` block reads, in order of first use."""
    files: list[str] = []
    checks = fixture.get("checks", {})
    for kind in ("absent", "present", "absent_regex"):
        for item in checks.get(kind, []):
            rel = str(item["file"])
            if rel not in files:
                files.append(rel)
    return files


def _plant(root: Path, rel: str, text: str) -> None:
    """Write ``text`` as ``root / rel``: a planted copy the self-test checks instead."""
    dst = root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(text.encode("utf-8"))


def _whole_line_probes(
    fixture: dict[str, Any], tmp: Path, counts: dict[str, int]
) -> list[str]:
    """A suffix or a prefix on a whole_line string's line must be reported at that target."""
    problems: list[str] = []
    for entry in fixture["entries"]:
        eid, string = str(entry["id"]), str(entry["string"])
        for target in entry["targets"]:
            rel = str(target["file"])
            if str(target["surface"]) != "whole_line":
                continue
            lines = (REPO_ROOT / rel).read_bytes().decode("utf-8").split("\n")
            at = next((i for i, ln in enumerate(lines) if ln.rstrip("\r") == string), None)
            for how, planted_line in (("suffix", string + " x"), ("prefix", "x " + string)):
                counts["whole_line"] += 1
                if at is None:
                    problems.append(
                        f"SELF-TEST[{eid}]: no line of {rel} equals the string, "
                        f"so no {how} can be planted"
                    )
                    continue
                copy = list(lines)
                copy[at] = planted_line + ("\r" if lines[at].endswith("\r") else "")
                planted = tmp / f"whole_line_{counts['whole_line']}"
                _plant(planted, rel, "\n".join(copy))
                probe = dict(entry)
                probe["targets"] = [dict(target)]
                failures, _ = check({"entries": [probe], "checks": {}}, None, planted)
                if not any(f.startswith(f"RENDER[{eid}] {rel} whole_line:") for f in failures):
                    problems.append(
                        f"SELF-TEST[{eid}]: a {how} on the string's line was not reported "
                        f"at {rel} whole_line"
                    )
    return problems


def _extract_group_probes(tmp: Path, counts: dict[str, int]) -> list[str]:
    """A bad regex group must be a SOURCE failure, not a crash and not a silent pass.

    The groups are one the pattern does not have, a negative one, and four values that
    are not integers (null, a float, a bool, a string).
    """
    problems: list[str] = []
    line = "self-test (a) line"
    cases: list[tuple[Any, str]] = [
        (9, "pattern has no group 9"),
        (-1, "pattern has no group -1"),
        (None, "group must be an integer, got None"),
        (1.5, "group must be an integer, got 1.5"),
        (True, "group must be an integer, got True"),
        ("1", "group must be an integer, got '1'"),
    ]
    for group, message in cases:
        counts["extract"] += 1
        src = tmp / f"source_{counts['extract']}"
        _plant(src, "source.md", line + "\n")
        entry = {
            "id": "self-test-group",
            "string": "a",
            "string_sha256": _sha("a"),
            "extracted": "a",
            "transforms": [],
            "source_path": "source.md",
            "source_line": 1,
            "source_line_sha256": _sha(line),
            "extract": {"kind": "regex", "pattern": r"\((a)\)", "group": group},
            "targets": [],
        }
        want = f"SOURCE[self-test-group]: {message}"
        try:
            failures, _ = check({"entries": [entry], "checks": {}}, src)
        except Exception as exc:  # the probe reports a crash instead of crashing itself
            problems.append(
                f"SELF-TEST[extract group {group!r}]: check() raised {type(exc).__name__} "
                f"instead of reporting it"
            )
            continue
        if want not in failures:
            problems.append(f"SELF-TEST[extract group {group!r}]: not reported as {want!r}")
    return problems


def self_test(fixture: dict[str, Any]) -> tuple[list[str], dict[str, int]]:
    """Return (problems, probes run by kind). Every probed branch must report a planted failure."""
    problems: list[str] = []
    counts = {"string": 0, "whole_line": 0, "checks": 0, "extract": 0}
    for entry in fixture["entries"]:
        string = str(entry["string"])
        mid = len(string) // 2
        mutated = string[:mid] + ("X" if string[mid] != "X" else "Y") + string[mid + 1 :]
        probe = dict(entry)
        probe["string"] = mutated
        probe["string_sha256"] = _sha(mutated)
        probe["extracted"] = mutated
        probe["transforms"] = []
        counts["string"] += 1
        failures, _ = check({"entries": [probe], "checks": {}}, None)
        for target in entry["targets"]:
            where = f"RENDER[{entry['id']}] {target['file']} {target['surface']}:"
            if not any(f.startswith(where) for f in failures):
                problems.append(
                    f"SELF-TEST[{entry['id']}]: a changed string was not reported missing "
                    f"at {target['file']} {target['surface']}"
                )
    for rel in check_files(fixture):
        body = (REPO_ROOT / rel).read_text(encoding="utf-8").replace("\r\n", "\n")
        known_present = next((ln for ln in body.split("\n") if ln.strip()), "")
        if not known_present:
            problems.append(f"SELF-TEST[checks {rel}]: the file has no non-empty line to plant")
            continue
        # Longer than the file, so it cannot be a substring of it.
        known_absent = body + "\n(self-test: this text is longer than the file)"
        planted = {
            "absent": [{"file": rel, "text": known_present}],
            "present": [{"file": rel, "text": known_absent}],
            "absent_regex": [{"file": rel, "pattern": re.escape(known_present), "why": "self-test"}],
        }
        failures, _ = check({"entries": [], "checks": planted}, None)
        for branch, prefix in (
            ("absent", f"ABSENT {rel}:"),
            ("present", f"PRESENT {rel}:"),
            ("absent_regex", f"ABSENT-RE {rel}:"),
        ):
            counts["checks"] += 1
            if not any(f.startswith(prefix) for f in failures):
                problems.append(f"SELF-TEST[{branch} {rel}]: a planted failure was not reported")
    with tempfile.TemporaryDirectory(prefix="signed-strings-") as tmp:
        problems += _whole_line_probes(fixture, Path(tmp), counts)
        problems += _extract_group_probes(Path(tmp), counts)
    return problems, counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, help="directory holding the source documents")
    parser.add_argument("--self-test", action="store_true", help="prove the matcher can fail")
    args = parser.parse_args(argv)
    fixture: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if args.self_test:
        problems, counts = self_test(fixture)
        for line in problems:
            print(f"  {line}")
        print(
            f"SIGNED STRINGS SELF-TEST: {'FAIL' if problems else 'OK'} "
            f"({counts['string']} string mutations, {counts['whole_line']} whole-line probes, "
            f"{counts['checks']} check-branch probes, {counts['extract']} extract-group probes, "
            f"{len(problems)} not reported)"
        )
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
