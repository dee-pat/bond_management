"""Check relative Markdown links, their anchors, and skills named in Read by task.

Usage: python3 scripts/test_doc_links.py [-v]

Paths are relative to the app root, so it runs from any directory.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = [
    ROOT / "AGENTS.md",
    ROOT / "e2e/AGENTS.md",
    ROOT / "frontend/AGENTS.md",
    *sorted(ROOT.glob("docs/*.md")),
]
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
FENCE = re.compile(r"^\s*(```|~~~)")


def prose_lines(path):
    """Yield (number, line) outside fenced code blocks."""
    in_fence = False
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            yield number, line


def slug(heading):
    """GitHub's heading anchor: lowercase, punctuation dropped, spaces to hyphens."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading).strip().lower()
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def anchors(path):
    seen = {}
    for _, line in prose_lines(path):
        if match := re.match(r"#{1,6}\s+(.+?)\s*#*$", line):
            base = slug(match.group(1))
            count = seen.get(base, 0)
            seen[base] = count + 1
            yield base if count == 0 else f"{base}-{count}"


class DocLinkTests(unittest.TestCase):
    def test_relative_links_and_anchors_resolve(self):
        broken = []
        for doc in DOCS:
            for number, line in prose_lines(doc):
                for target in LINK.findall(line):
                    if re.match(r"[a-z]+:", target):
                        continue
                    file_part, _, anchor = target.partition("#")
                    path = (doc.parent / file_part).resolve() if file_part else doc
                    where = f"{doc.relative_to(ROOT)}:{number}: {target}"
                    if not path.exists():
                        broken.append(f"{where} (missing file)")
                    elif anchor and path.suffix == ".md" and anchor not in set(anchors(path)):
                        broken.append(f"{where} (missing anchor)")
        self.assertEqual(broken, [])

    def test_read_by_task_skills_exist(self):
        section = (ROOT / "AGENTS.md").read_text().split("## Read by task", 1)[1].split("\n## ", 1)[0]
        rows = [line for line in section.splitlines() if line.startswith("|")]
        skills = {name for row in rows for name in re.findall(r"`([a-z0-9]+(?:-[a-z0-9]+)+)`", row)}
        self.assertTrue(skills, "no skills found in the Read by task table")
        missing = sorted(
            name for name in skills if not (ROOT / ".agents/skills" / name / "SKILL.md").is_file()
        )
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
