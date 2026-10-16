from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
PROJECT = SKILL.parent
SOURCE = SKILL / "source" / "SKILL.md"
SKILL_JSON = SKILL / "skill.json"
CONTRACT = SKILL / "chebu-tutor-docs" / "contract.md"
TEMPLATE = PROJECT / ".handoff" / "TEMPLATE.md"
DELIMITER = "CHEBU_TUTOR_ARGS"
PLACEHOLDER = "$ARGUMENTS"


def template_modes() -> list[str]:
    row = re.search(r"^\| Режим тьютора \| `<([a-z / ]+)>` \|$", TEMPLATE.read_text(encoding="utf-8"), re.MULTILINE)
    assert row, f"no mode row in {TEMPLATE}"
    return row.group(1).split(" / ")


def contract_usage() -> str:
    lines = [line for line in CONTRACT.read_text(encoding="utf-8").splitlines() if line.startswith("использование:")]
    assert len(lines) == 1, f"expected one usage line in {CONTRACT}, found {lines}"
    return lines[0]


def check_command(body: str) -> str:
    blocks = re.findall(r"^```bash\n(.*?)^```$", body, flags=re.MULTILINE | re.DOTALL)
    found = [block for block in blocks if "--mode <<" in block]
    assert len(found) == 1, f"expected one bash block with the --mode heredoc, found {len(found)}"
    return found[0]


class SourceTest(unittest.TestCase):
    def setUp(self) -> None:
        text = SOURCE.read_text(encoding="utf-8")
        header = re.match(r"---\n(.*?)\n---\n", text, flags=re.DOTALL)
        self.assertIsNotNone(header, "no frontmatter")
        self.header = header.group(1).splitlines()
        self.body = text[header.end() :]

    def test_header_names_the_skill_and_takes_facts_from_skill_json(self) -> None:
        skill = json.loads(SKILL_JSON.read_text(encoding="utf-8"))
        self.assertIn(f"name: {skill['name']}", self.header)
        self.assertIn('description: "{{description}}"', self.header)
        metadata = self.header.index("metadata:")
        self.assertEqual(self.header[metadata + 1], '  version: "{{version}}"')

    def test_header_leaves_the_call_to_the_student(self) -> None:
        self.assertIn("disable-model-invocation: true", self.header)
        triggers = self.header.index("triggers:")
        self.assertEqual(self.header[triggers + 1 : triggers + 2], ["  - user"])
        self.assertNotIn("  - model", self.header)
        self.assertFalse([line for line in self.header if line.startswith("user-invocable")])

    def test_body_points_to_project_rules(self) -> None:
        for reference in ("AGENTS.md", "tutor-modes.md", ".handoff/handoff.py start"):
            self.assertIn(reference, self.body, reference)

    def test_arguments_placeholder_is_the_only_line_inside_the_heredoc(self) -> None:
        self.assertEqual(self.body.count(PLACEHOLDER), 1, PLACEHOLDER)
        self.assertNotRegex(self.body, r"\$\d|\$\{", "positional or braced substitution")
        lines = check_command(self.body).splitlines()
        self.assertEqual(lines[1:], [PLACEHOLDER, DELIMITER])

    def test_usage_line_matches_contract_and_check_code(self) -> None:
        usage = contract_usage()
        printed = subprocess.run(
            [sys.executable, str(PROJECT / ".handoff" / "handoff.py"), "start", "--runtime", "unknown", "--mode"],
            cwd=PROJECT,
            input="",
            capture_output=True,
            encoding="utf-8",
        )
        self.assertEqual(printed.returncode, 0, printed.stderr)
        self.assertEqual(printed.stdout.splitlines()[0], usage)
        self.assertIn(usage, self.body.splitlines())

    def test_names_every_flag_of_the_template_enumeration(self) -> None:
        for mode in template_modes():
            self.assertIn(f"`--{mode}`", self.body, mode)

    def test_check_command_keeps_student_text_away_from_the_shell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "executed"
            text = f"--guide don't \"EDU-02\" $HOME `touch {marker}` $(touch {marker})"
            command = (
                check_command(self.body)
                .replace("python3", shlex.quote(sys.executable), 1)
                .replace("<id>", "unknown")
                .replace(PLACEHOLDER, text)
            )

            result = subprocess.run(["sh", "-c", command], cwd=PROJECT, capture_output=True, encoding="utf-8")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(marker.exists(), "the shell ran the student text")
            modes = [line for line in result.stdout.splitlines() if line.startswith("Режим тьютора:")]
            self.assertEqual(len(modes), 1, result.stdout)
            self.assertRegex(modes[0], r"^Режим тьютора: guide[ ,]")


if __name__ == "__main__":
    unittest.main()
