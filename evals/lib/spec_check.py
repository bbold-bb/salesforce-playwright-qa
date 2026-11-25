"""Checks a Playwright spec Claude wrote against the approved Test Steps and the kit's spec rules
(templates/qa/playwright/templates/story.spec.ts and the salesforce-playwright-qa skill), and that it compiles and
lists its tests. Nothing here runs against an org.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from evals.lib.score import Finding
from evals.lib.steps_check import Draft

EVALS = Path(__file__).resolve().parent.parent
TAG_TO_EVIDENCE = {"Video": "video", "Screenshot": "screenshot", "Query": "query"}

_BRITTLE = [
    (r"xpath=", "xpath= locator"),
    (r"""locator\(\s*['"`]\s*//""", "XPath locator"),
    (r"\.nth\(", ".nth() position"),
    (r"""locator\(\s*['"`]\s*\.""", "CSS class locator"),
    (r"""locator\(\s*['"`]\s*#""", "CSS id locator"),
]
_SKIP = [r"\btest\.skip\b", r"\btest\.fixme\b", r"\btest\.only\b", r"\bstorageState\b",
         r"\btest\.describe\.(skip|fixme|only)\b"]


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"(?m)^\s*//.*$", "", src)
    return re.sub(r"(?m)\s+//\s.*$", "", src)  # a trailing comment; a // inside a string has no space before


def scenarios(src: str) -> list[dict]:
    """The SCENARIOS entries: id, flow and evidence, read from the array literal."""
    m = re.search(r"SCENARIOS\s*(?::[^=]+)?=\s*\[(.*?)\n\];", src, re.S)
    if not m:
        return []
    out = []
    for chunk in re.split(r"(?=\{\s*id:)", m.group(1)):
        idm = re.search(r"id:\s*['\"`](S\d+)['\"`]", chunk)
        if not idm:
            continue
        fl = re.search(r"flow:\s*['\"`](F\d+)['\"`]", chunk)
        ev = re.search(r"evidence:\s*\[([^\]]*)\]", chunk)
        out.append({"id": idm.group(1), "flow": fl.group(1) if fl else None,
                    "evidence": sorted(re.findall(r"['\"`](\w+)['\"`]", ev.group(1))) if ev else []})
    return out


def _expected(approved: Draft) -> list[dict]:
    return [{"id": f"S{s.number}", "flow": s.flow, "evidence": [TAG_TO_EVIDENCE.get(s.tag, s.tag.lower())]}
            for s in approved.steps if s.number != 1]


def _blocks(src: str) -> dict[str, str]:
    """Each step's code: from its step(r.S<n> or standalone('S<n>') marker to the next marker."""
    marks = [(m.start(), m.group(1) or m.group(2)) for m in
             re.finditer(r"step\(\s*r\.(S\d+)\b|standalone\(\s*['\"`](S\d+)['\"`]", src)]
    blocks: dict[str, str] = {}
    for i, (pos, sid) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(src)
        blocks[sid] = blocks.get(sid, "") + src[pos:end]
    return blocks


def _query_helpers(src: str) -> set[str]:
    """Local functions whose definition calls query(), directly or through another such function, so a step that
    calls them checks by query."""
    bodies: dict[str, str] = {}
    for m in re.finditer(r"(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*(?::[^=]+)?=>|function\s+(\w+)\s*\(",
                         src):
        name = m.group(1) or m.group(2)
        body = src[m.end():m.end() + 600]
        nxt = re.search(r"\n(?:const|let|function|async function|test|\})", body)
        bodies[name] = body[:nxt.start()] if nxt else body
    names = {n for n, b in bodies.items() if "query(" in b}
    grew = True
    while grew:
        more = {n for n, b in bodies.items() if n not in names and any(re.search(rf"\b{h}\(", b) for h in names)}
        names |= more
        grew = bool(more)
    return names


def check_spec(spec_text: str, approved: Draft, ticket: str) -> list[Finding]:
    src = _strip_comments(spec_text)
    out: list[Finding] = []

    def add(rule: str, ok: bool, detail: str = "") -> None:
        out.append(Finding(rule, ok, detail))

    got = sorted(scenarios(src), key=lambda s: s["id"])
    want = sorted(_expected(approved), key=lambda s: s["id"])
    add("scenarios-match", got == want, "" if got == want else f"SCENARIOS {got} != approved {want}")

    flows = sorted({s["flow"] for s in got if s["flow"]})
    cards = len(re.findall(r"\bopeningCard\(\s*\w+\s*,", src))
    add("opening-card-per-flow", cards >= len(flows), f"{cards} opening cards for flows {flows}")

    blocks = _blocks(src)
    video_ids = [s["id"] for s in got if "video" in s["evidence"]]
    no_chapter = [i for i in video_ids if "chapter(" not in blocks.get(i, "")]
    add("chapter-per-video-step", not no_chapter, f"video steps with no chapter card: {no_chapter}" if no_chapter else "")

    brittle = [label for pat, label in _BRITTLE if re.search(pat, src)]
    add("no-brittle-locator", not brittle, ", ".join(brittle))

    skips = [p for p in _SKIP if re.search(p, src)]
    add("no-skip", not skips, ", ".join(skips))

    # Who a spec runs as comes from testUser(), so it runs as any tester's users (README.md, Test users). Checked on the
    # code and its strings alike: a title or card that types a user's name is wrong for every other tester.
    typed = sorted(set(re.findall(r"['\"`]([^'\"`\n]*\bTest User\b[^'\"`\n]*)['\"`]", src)))
    add("no-typed-user", not typed, f"a test user's name typed in the spec: {typed}" if typed else "")
    runs_as_user = any(s.flow for s in approved.steps)
    add("test-user-by-persona", not runs_as_user or bool(re.search(r"\btestUser\(\s*['\"`]\w+['\"`]\s*\)", src)),
        "" if not runs_as_user or "testUser(" in src else "no testUser('<persona>') for a spec that runs as a user")

    # Only a spec with steps run as a user can create records; a query-only spec has nothing to name.
    makes_records = any(s.flow or s.tag in ("Video", "Screenshot") for s in approved.steps)
    naming = re.search(r"(?:QA|\$\{RECORD_PREFIX\})\s+\$\{TICKET\}\s+\$\{ROUND\}", src)
    add("record-naming", bool(naming) or not makes_records,
        "" if naming or not makes_records else "no record prefix of the form QA ${TICKET} ${ROUND}")

    helpers = _query_helpers(src)
    no_query = [i for i in (s["id"] for s in got) if not (
        "query(" in blocks.get(i, "") or any(re.search(rf"\b{h}\(", blocks.get(i, "")) for h in helpers))]
    add("query-per-step", not no_query, f"steps with no query check: {no_query}" if no_query else "")
    return out


def compile_check(harness_dir: Path, ticket: str, approved: Draft) -> list[Finding]:
    """tsc (strict, no emit) over the spec and the harness lib, then playwright test --list for the spec."""
    harness_dir = Path(harness_dir)
    spec = harness_dir / "tests" / f"{ticket}.spec.ts"
    if not spec.is_file():
        return [Finding("tsc", False, f"no tests/{ticket}.spec.ts"), Finding("list", False, "no spec")]
    cfg = harness_dir / "tsconfig.eval.json"
    cfg.write_text(json.dumps({
        "compilerOptions": {"strict": True, "noEmit": True, "target": "ES2022", "module": "commonjs",
                            "moduleResolution": "node", "esModuleInterop": True, "skipLibCheck": True,
                            "types": ["node"], "typeRoots": [str(EVALS / "node_modules" / "@types")]},
        "files": [str(spec)],
    }))
    tsc = subprocess.run([str(EVALS / "node_modules" / ".bin" / "tsc"), "-p", str(cfg)], cwd=harness_dir,
                         capture_output=True, text=True, timeout=300)
    cfg.unlink()
    out = [Finding("tsc", tsc.returncode == 0, (tsc.stdout + tsc.stderr).strip()[-1500:])]
    lst = subprocess.run(["npx", "playwright", "test", "--list", f"tests/{ticket}.spec.ts"], cwd=harness_dir,
                         capture_output=True, text=True, timeout=300)
    titles = re.findall(r"›\s*(\S+)", lst.stdout)
    want = sorted({s.flow for s in approved.steps if s.flow} |
                  {f"S{s.number}" for s in approved.steps if s.number != 1 and not s.flow})
    missing = [w for w in want if w not in titles]
    ok = lst.returncode == 0 and not missing
    out.append(Finding("list", ok, f"missing tests: {missing}" if missing else (lst.stdout + lst.stderr)[-800:] if not ok else ""))
    return out
