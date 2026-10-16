from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
PROJECT = SKILL.parent
SKILL_JSON = SKILL / "skill.json"
TEMPLATE = PROJECT / ".handoff" / "TEMPLATE.md"
VERSION = r"^\d+\.\d+\.\d+$"


def template_schema() -> int:
    text = TEMPLATE.read_text(encoding="utf-8")
    row = re.search(r"^\| Схема \| (\d+)", text, flags=re.MULTILINE)
    assert row, f"no schema row in {TEMPLATE}"
    return int(row.group(1))


class SkillJsonTest(unittest.TestCase):
    def setUp(self) -> None:
        self.skill = json.loads(SKILL_JSON.read_text(encoding="utf-8"))

    def test_name_is_chebu_tutor(self) -> None:
        self.assertEqual(self.skill["name"], "chebu-tutor", "name")

    def test_version_is_semver(self) -> None:
        self.assertRegex(self.skill["version"], VERSION, "version")

    def test_handoff_schema_matches_template(self) -> None:
        self.assertEqual(self.skill["requires"]["handoff_schema"], template_schema(), "requires.handoff_schema")

    def test_chebu_min_version_is_semver(self) -> None:
        self.assertRegex(self.skill["requires"]["chebu_min_version"], VERSION, "requires.chebu_min_version")


if __name__ == "__main__":
    unittest.main()
