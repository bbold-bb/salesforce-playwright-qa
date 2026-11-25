#!/usr/bin/env python3
"""Prints the copy of a round's run summary that goes to the shared QA Evidence folder.

The local run summary keeps the whole history. The shared copy keeps the result of each step and what was seen, and
leaves out the attempts, what changed between them and the test tooling: a reader of the shared folder needs to know
what was tested and what it showed, not how many tries the script took. publish.sh writes it in place of the local
copy; the local run summary and results.json stay on this machine.

The sections it drops are the run summary's "## Attempts" and "## What changed before A<n>", the Attempts column of
the Results table, and any header bullet that starts with "- **Run with:**" (a spec can put how it was run there).

  python3 shared_summary.py "evidence/<epic>/<QA sub-task>/<round>/run-summary.md" > <shared copy>
"""
import re
import sys

DROP_SECTIONS = ("## Attempts", "## What changed")
DROP_BULLETS = ("- **Run with:**",)


def without_column(table_lines, name):
    """Drops one column from a markdown table, by its header."""
    header = [c.strip() for c in table_lines[0].strip().strip("|").split("|")]
    if name not in header:
        return table_lines
    i = header.index(name)
    out = []
    for line in table_lines:
        cells = line.strip().strip("|").split("|")
        del cells[i]
        out.append("|" + "|".join(cells) + "|")
    return out


def shared_copy(text):
    sections = re.split(r"(?m)^(?=## )", text)
    kept = []
    for section in sections:
        if section.startswith(DROP_SECTIONS):
            continue
        lines = [l for l in section.split("\n") if not l.startswith(DROP_BULLETS)]
        # The shared copy leaves the attempts out, so it doesn't point at their notes.
        lines = [l.replace("; each attempt's time is in its note", "") for l in lines]
        if section.startswith("## Results"):
            table = [i for i, l in enumerate(lines) if l.startswith("|")]
            lines[table[0]:table[-1] + 1] = without_column(lines[table[0]:table[-1] + 1], "Attempts")
        kept.append("\n".join(lines))
    return "".join(kept)


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as f:
        sys.stdout.write(shared_copy(f.read()))
