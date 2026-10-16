from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
RUNTIME_CONFIG = PROJECT / "runtime-config"
REAL_TEMPLATE = (HERE / "TEMPLATE.md").read_text(encoding="utf-8")
MANIFEST = json.loads((RUNTIME_CONFIG / "manifest.json").read_text(encoding="utf-8"))
RUNTIMES = {
    path.stem: json.loads(path.read_text(encoding="utf-8"))
    for path in sorted((RUNTIME_CONFIG / "runtimes").glob("*.json"))
}
MARKERS = {name for runtime in RUNTIMES.values() for name in runtime["detect_env"]}

PLACEHOLDER = re.compile(r"<[^<>\n]+>")
ENUMERATION = re.compile(r"<([a-z][a-z0-9_-]*(?: / [a-z][a-z0-9_-]*)+)>")
LINK_TARGET = re.compile(r"\]\(([^)#\s:]+)\)")
RESUME_HEADER = "Продолжить в любом рантайме из корня основного клона:"

# Assembled at run time so that no token-shaped literal sits in the repository.
SECRETS = (
    "sk-" + "a1B2c3D4" * 4,
    "ghp_" + "a1B2c3D4" * 5,
    "github_pat_" + "a1B2c3D4" * 5,
    "xoxb-" + "1234567890-" * 2 + "a1B2c3D4",
    "AKIA" + "ABCDEFGH12345678",
    "-----BEGIN OPENSSH " + "PRIVATE KEY-----",
    "https://deploy:" + "hunter2" + "@example.com/repo.git",
)


def set_field(text: str, field: str, value: str) -> str:
    row = re.compile(rf"^\| {re.escape(field)} \|.*$", flags=re.MULTILINE)
    assert row.search(text), f"no metadata row {field!r} in the template"
    return row.sub(lambda _: f"| {field} | {value} |", text)


def drop_field(text: str, field: str) -> str:
    row = re.compile(rf"^\| {re.escape(field)} \|.*\n", flags=re.MULTILINE)
    assert row.search(text), f"no metadata row {field!r} in the template"
    return row.sub("", text)


def add_field(text: str, field: str, value: str) -> str:
    rule = re.compile(r"^\|---\|---\|\n", flags=re.MULTILINE)
    assert rule.search(text), "no metadata table in the template"
    return rule.sub(lambda found: f"{found.group()}| {field} | {value} |\n", text, count=1)


def metadata_rows(template: str) -> dict[str, str]:
    rows = re.findall(r"^\| ([^|\n]+) \| (.*) \|$", template.split("\n## ")[1], flags=re.MULTILINE)
    return dict(rows[1:])


def enumerated_fields(template: str) -> dict[str, list[str]]:
    found = {field: ENUMERATION.fullmatch(value.replace("`", "")) for field, value in metadata_rows(template).items()}
    return {field: choices.group(1).split(" / ") for field, choices in found.items() if choices}


ENUM_FIELD = "Проверочный список"
ENUM_CHOICES = ("alpha", "beta-2", "gamma_3")
ENUM_PLACEHOLDER = f"<{' / '.join(ENUM_CHOICES)}>"
# The synthetic row gives every test an enumerated field, whether or not the real template defines one.
TEMPLATE = add_field(REAL_TEMPLATE, ENUM_FIELD, f"`{ENUM_PLACEHOLDER}`")
HEADINGS = re.findall(r"^## (.+)$", TEMPLATE, flags=re.MULTILINE)
METADATA_FIELDS = list(metadata_rows(TEMPLATE))
SCHEMA = re.search(r"^\| Схема \| (\d+)", TEMPLATE, flags=re.MULTILINE).group(1)


def filler(placeholder: str) -> str:
    choices = ENUMERATION.fullmatch(placeholder)
    return choices.group(1).split(" / ")[0] if choices else "заполнено"


def filled_snapshot(
    *,
    time: str = "2026-10-13T09:00:00Z",
    runtime: str = "claude",
    schema: int | None = None,
    unfilled: str | None = None,
    without_section: str | None = None,
    body: str = "",
) -> str:
    text = PLACEHOLDER.sub(
        lambda found: found.group() if found.group() == unfilled else filler(found.group()), TEMPLATE
    )
    text = set_field(text, "Время снимка UTC", f"`{time}`")
    text = set_field(text, "Рантайм", f"`{runtime}`; `1.0.0`")
    if schema is not None:
        text = set_field(text, "Схема", f"{schema}; [протокол](README.md)")
    if without_section is not None:
        section = rf"^## {re.escape(without_section)}\n.*?(?=^## |\Z)"
        text = re.sub(section, "", text, flags=re.MULTILINE | re.DOTALL)
    return f"{text}\n{body}\n" if body else text


def schema1_snapshot(sender: str, time: str) -> str:
    return (
        "# Передача сессии chebu\n\n## 1. Метаданные\n\n| Поле | Значение |\n|---|---|\n"
        "| Схема | 1; [протокол](README.md) |\n"
        f"| Время снимка UTC | {time} |\n"
        f"| Отправитель: приложение/агент | {sender} |\n\n## 2. Фактически сделано\n\nНичего.\n"
    )


def line_of(text: str, needle: str) -> int:
    return next(number for number, line in enumerate(text.splitlines(), start=1) if needle in line)


def output(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


def problems(result: subprocess.CompletedProcess[str]) -> list[str]:
    return [line for line in output(result).splitlines() if line.startswith("ошибка:")]


class HandoffCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.home = self.root / "userdir"
        self.home.mkdir()
        self.repo = self.root / "repo"
        self.state = self.repo / ".handoff"
        self.session = self.state / "SESSION.md"
        self.prepared = self.state / "SESSION.next.md"
        self.archive = self.state / "archive"
        self.template = self.state / "TEMPLATE.md"

        self.state.mkdir(parents=True)
        shutil.copy(HERE / "handoff.py", self.state / "handoff.py")
        self.template.write_text(TEMPLATE, encoding="utf-8")
        shutil.copytree(RUNTIME_CONFIG, self.repo / "runtime-config")
        shutil.copy(PROJECT / ".gitignore", self.repo / ".gitignore")
        for target in set(LINK_TARGET.findall(TEMPLATE)):
            stub = (self.state / target).resolve()
            stub.parent.mkdir(parents=True, exist_ok=True)
            stub.write_text("stub\n", encoding="utf-8")
        self.git("-c", "init.defaultBranch=main", "init", "-q")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

    def env(self, **extra: str) -> dict[str, str]:
        # HOME is replaced so that neither the owner's Git config nor the real home path reaches the script.
        env = {name: value for name, value in os.environ.items() if name not in MARKERS and not name.startswith("GIT_")}
        env.update(HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"), **extra)
        return env

    def git(self, *args: str) -> None:
        identity = ["-c", "user.name=test", "-c", "user.email=test@example.invalid"]
        subprocess.run(["git", *identity, *args], cwd=self.repo, env=self.env(), check=True, capture_output=True)

    def run_script(
        self,
        *args: str,
        checkout: Path | None = None,
        cwd: Path | None = None,
        stdin: str | None = None,
        **env: str,
    ) -> subprocess.CompletedProcess[str]:
        script = (checkout or self.repo) / ".handoff" / "handoff.py"
        return subprocess.run(
            [sys.executable, str(script), *args],
            cwd=cwd or self.repo,
            env=self.env(**env),
            input=stdin,
            capture_output=True,
            encoding="utf-8",
        )

    def check(self, text: str) -> subprocess.CompletedProcess[str]:
        self.prepared.write_text(text, encoding="utf-8")
        return self.run_script("check")

    def state_files(self) -> dict[str, bytes]:
        return {
            str(path.relative_to(self.state)): path.read_bytes()
            for path in sorted(self.state.rglob("*"))
            if path.is_file()
        }

    def assert_single_problem(self, result: subprocess.CompletedProcess[str], *needles: str) -> None:
        self.assertEqual(result.returncode, 1, output(result))
        found = problems(result)
        self.assertEqual(len(found), 1, found)
        for needle in needles:
            self.assertIn(needle, found[0])

    def assert_clean(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual((result.returncode, problems(result)), (0, []), output(result))


class CheckTest(HandoffCase):
    def test_accepts_filled_snapshot(self) -> None:
        result = self.check(filled_snapshot())
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(len(result.stdout.splitlines()), 1)

    def test_accepts_explicit_path(self) -> None:
        elsewhere = self.root / "elsewhere.md"
        elsewhere.write_text(filled_snapshot(), encoding="utf-8")
        self.assert_clean(self.run_script("check", str(elsewhere)))

    def test_reports_missing_file(self) -> None:
        self.assert_single_problem(self.run_script("check"), "SESSION.next.md")

    def test_reports_missing_section(self) -> None:
        missing = HEADINGS[3]
        self.assert_single_problem(self.check(filled_snapshot(without_section=missing)), f"нет раздела «{missing}»")

    def test_reports_extra_section(self) -> None:
        extra = "Раздел сверх шаблона"
        text = filled_snapshot(body=f"## {extra}")
        self.assert_single_problem(
            self.check(text), f"лишний раздел: «{extra}»", f"строка {line_of(text, f'## {extra}')}:"
        )

    def test_reports_misplaced_section(self) -> None:
        moved = HEADINGS[3]
        text = filled_snapshot(without_section=moved, body=f"## {moved}")
        self.assert_single_problem(self.check(text), moved, f"строка {line_of(text, f'## {moved}')}:")

    def test_ignores_heading_inside_code_fence(self) -> None:
        self.assert_clean(self.check(filled_snapshot(body="```text\n## main...origin/main\n```")))

    def test_reports_missing_metadata_field(self) -> None:
        field = METADATA_FIELDS[-1]
        self.assert_single_problem(self.check(drop_field(filled_snapshot(), field)), f"нет поля «{field}»")

    def test_reports_empty_metadata_field(self) -> None:
        field = METADATA_FIELDS[-1]
        text = set_field(filled_snapshot(), field, "")
        self.assert_single_problem(
            self.check(text), f"поле метаданных «{field}» пустое", f"строка {line_of(text, f'| {field} |')}:"
        )

    def test_reports_schema_mismatch(self) -> None:
        text = filled_snapshot(schema=99)
        self.assert_single_problem(self.check(text), "99", f"строка {line_of(text, '| Схема |')}:")

    def test_reports_leftover_placeholder(self) -> None:
        leftover = PLACEHOLDER.findall(TEMPLATE)[-1]
        text = filled_snapshot(unfilled=leftover)
        self.assert_single_problem(self.check(text), leftover, f"строка {line_of(text, leftover)}:")

    def test_reports_unknown_runtime(self) -> None:
        text = filled_snapshot(runtime="hal9000")
        self.assert_single_problem(self.check(text), "hal9000", f"строка {line_of(text, '| Рантайм |')}:")

    def test_accepts_runtime_outside_registry_declared_as_unknown(self) -> None:
        self.assert_clean(self.check(filled_snapshot(runtime="unknown")))

    def test_reports_malformed_time(self) -> None:
        text = filled_snapshot(time="2026-10-13 09:00")
        self.assert_single_problem(
            self.check(text), "2026-10-13 09:00", f"строка {line_of(text, '| Время снимка UTC |')}:"
        )

    def test_accepts_every_choice_of_enumerated_field(self) -> None:
        for choice in ENUM_CHOICES:
            with self.subTest(choice=choice):
                self.assert_clean(self.check(set_field(filled_snapshot(), ENUM_FIELD, f"`{choice}`")))

    def test_reports_value_outside_enumerated_field(self) -> None:
        text = set_field(filled_snapshot(), ENUM_FIELD, "`delta`")
        self.assert_single_problem(
            self.check(text),
            f"строка {line_of(text, f'| {ENUM_FIELD} |')}: поле «{ENUM_FIELD}»: значение «delta» не входит в список: "
            + ", ".join(ENUM_CHOICES),
        )

    def test_reports_missing_enumerated_field_once(self) -> None:
        self.assert_single_problem(self.check(drop_field(filled_snapshot(), ENUM_FIELD)), f"нет поля «{ENUM_FIELD}»")

    def test_reports_unfilled_enumerated_field_once(self) -> None:
        text = filled_snapshot(unfilled=ENUM_PLACEHOLDER)
        self.assert_single_problem(self.check(text), f"не заполнен placeholder шаблона: {ENUM_PLACEHOLDER}")

    def test_placeholder_with_prose_alternatives_is_not_an_enumeration(self) -> None:
        field = "Проверочная подсказка"
        self.template.write_text(add_field(TEMPLATE, field, "`<нет / конкретный остаток>`"), encoding="utf-8")
        self.assert_clean(self.check(add_field(filled_snapshot(), field, "заполнено")))

    def test_reports_home_paths(self) -> None:
        paths = (
            "/Users/somebody/notes.md",
            "/home/somebody/notes.md",
            "C:\\Users\\somebody\\notes.md",
            f"{self.home}/notes.md",
        )
        text = filled_snapshot(body="\n".join(paths))
        result = self.check(text)
        self.assertEqual(result.returncode, 1)
        found = problems(result)
        self.assertEqual(len(found), len(paths), found)
        for path, problem in zip(paths, found):
            self.assertIn(f"строка {line_of(text, path)}: абсолютный домашний путь", problem)
        self.assertNotIn("somebody", output(result))
        self.assertNotIn(str(self.home), output(result))

    def test_reports_secrets_without_printing_them(self) -> None:
        text = filled_snapshot(body="\n".join(SECRETS))
        result = self.check(text)
        self.assertEqual(result.returncode, 1)
        found = problems(result)
        self.assertEqual(len(found), len(SECRETS), found)
        for secret, problem in zip(SECRETS, found):
            self.assertIn(f"строка {line_of(text, secret)}: секрет", problem)
            self.assertNotIn(secret[len(secret) // 2 :], output(result))

    def test_reports_email_address(self) -> None:
        email = "somebody" + "@example.com"
        text = filled_snapshot(body=f"Написать на {email} после выпуска.")
        result = self.check(text)
        self.assert_single_problem(result, f"строка {line_of(text, email)}: адрес электронной почты")
        self.assertNotIn(email, output(result))

    def test_accepts_public_references_that_resemble_private_data(self) -> None:
        body = "\n".join(
            (
                "git@github.com:owner/repo.git",
                "Co-Authored-By: Agent <noreply@example.com>",
                "https://github.com/users/owner/projects/4",
                "https://example.com/home/page/index.html",
                "task-tracking-and-project-status-board",
                "actions/checkout@v4.1.0",
            )
        )
        self.assert_clean(self.check(filled_snapshot(body=body)))

    def test_reports_broken_relative_link(self) -> None:
        text = filled_snapshot(body="[план](../docs/missing-plan.md)")
        self.assert_single_problem(
            self.check(text), "../docs/missing-plan.md", f"строка {line_of(text, 'missing-plan')}:"
        )

    def test_accepts_link_to_existing_file_resolved_from_handoff_dir(self) -> None:
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "plan.md").write_text("план\n", encoding="utf-8")
        self.assert_clean(self.check(filled_snapshot(body="[план](../docs/plan.md#этап-1)")))

    def test_accepts_urls_and_anchors_as_link_targets(self) -> None:
        body = "[сайт](https://example.com/absent) [почта](mailto:git@example.com) [вверх](#1-метаданные)"
        self.assert_clean(self.check(filled_snapshot(body=body)))

    def test_ignores_link_inside_code_fence(self) -> None:
        self.assert_clean(self.check(filled_snapshot(body="```text\n[план](../docs/missing-plan.md)\n```")))

    def test_inline_triple_backticks_do_not_open_code_fence(self) -> None:
        text = filled_snapshot(body="```git status``` показывает чистое дерево\n[план](../docs/missing-plan.md)")
        self.assert_single_problem(self.check(text), "../docs/missing-plan.md")

    def test_accepts_link_to_file_that_exists_only_in_linked_worktree(self) -> None:
        linked = self.root / "linked"
        self.git("worktree", "add", "-q", "-b", "linked", str(linked))
        (linked / "draft.md").write_text("черновик\n", encoding="utf-8")
        text = filled_snapshot(body="[черновик](../draft.md)")
        self.prepared.write_text(text, encoding="utf-8")
        (linked / ".handoff" / "SESSION.next.md").write_text(text, encoding="utf-8")

        self.assert_single_problem(self.run_script("check"), "../draft.md")
        self.assert_clean(self.run_script("check", checkout=linked))


class SaveTest(HandoffCase):
    def test_archives_previous_snapshot_and_replaces_session(self) -> None:
        previous = schema1_snapshot("Codex", "2026-10-12T18:00:00Z").encode("utf-8") + b"tail\r\n\xff"
        prepared = filled_snapshot()
        self.session.write_bytes(previous)
        self.prepared.write_text(prepared, encoding="utf-8")

        result = self.run_script("save")

        self.assertEqual(result.returncode, 0, output(result))
        [archived] = self.archive.iterdir()
        self.assertRegex(archived.name, r"^\d{8}T\d{12}Z-codex\.md$")
        self.assertEqual(archived.read_bytes(), previous)
        self.assertEqual(self.session.read_text(encoding="utf-8"), prepared)
        self.assertFalse(self.prepared.exists())

    def test_first_save_creates_session_without_archive(self) -> None:
        prepared = filled_snapshot()
        self.prepared.write_text(prepared, encoding="utf-8")

        result = self.run_script("save")

        self.assertEqual(result.returncode, 0, output(result))
        self.assertEqual(self.state_files().get("SESSION.md"), prepared.encode("utf-8"))
        self.assertFalse(self.archive.exists())

    def test_rerun_after_interrupted_save_does_not_duplicate_archive(self) -> None:
        previous = schema1_snapshot("Codex", "2026-10-12T18:00:00Z").encode("utf-8")
        self.session.write_bytes(previous)
        self.archive.mkdir()
        (self.archive / "20261012T180500000000Z-codex.md").write_bytes(previous)
        self.prepared.write_text(filled_snapshot(), encoding="utf-8")

        result = self.run_script("save")

        self.assertEqual(result.returncode, 0, output(result))
        self.assertEqual([path.name for path in self.archive.iterdir()], ["20261012T180500000000Z-codex.md"])
        self.assertFalse(self.prepared.exists())

    def test_writes_nothing_when_check_fails(self) -> None:
        self.session.write_text(schema1_snapshot("Codex", "2026-10-12T18:00:00Z"), encoding="utf-8")
        self.prepared.write_text(filled_snapshot(runtime="hal9000"), encoding="utf-8")
        before = self.state_files()

        result = self.run_script("save")

        self.assertEqual(result.returncode, 1)
        self.assertIn("hal9000", output(result))
        self.assertEqual(self.state_files(), before)

    def test_refuses_without_prepared_snapshot(self) -> None:
        self.session.write_text(filled_snapshot(), encoding="utf-8")
        before = self.state_files()

        result = self.run_script("save")

        self.assert_single_problem(result, "SESSION.next.md")
        self.assertEqual(self.state_files(), before)

    def test_refuses_when_session_is_not_ignored_by_git(self) -> None:
        (self.repo / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        self.session.write_text(schema1_snapshot("Codex", "2026-10-12T18:00:00Z"), encoding="utf-8")
        self.prepared.write_text(filled_snapshot(), encoding="utf-8")
        before = self.state_files()

        result = self.run_script("save")

        self.assert_single_problem(result, ".handoff/SESSION.md", ".gitignore")
        self.assertEqual(self.state_files(), before)

    def test_refuses_to_replace_newer_snapshot(self) -> None:
        self.session.write_text(filled_snapshot(time="2026-10-13T12:00:00Z"), encoding="utf-8")
        self.prepared.write_text(filled_snapshot(time="2026-10-13T11:59:59Z"), encoding="utf-8")
        before = self.state_files()

        refused = self.run_script("save")

        self.assert_single_problem(refused, "SESSION.md", "2026-10-13T12:00:00Z")
        self.assertEqual(self.state_files(), before)

        self.prepared.write_text(filled_snapshot(time="2026-10-13T12:00:00Z"), encoding="utf-8")
        self.assertEqual(self.run_script("save").returncode, 0, "a snapshot of the same age must be accepted")

    def test_from_linked_worktree_writes_into_main_checkout(self) -> None:
        linked = self.root / "linked"
        self.git("worktree", "add", "-q", "-b", "linked", str(linked))
        tracked = sorted(path.name for path in (linked / ".handoff").iterdir())
        before = set(self.state_files())
        prepared = filled_snapshot()
        (linked / ".handoff" / "SESSION.next.md").write_text(prepared, encoding="utf-8")

        result = self.run_script("save", checkout=linked, cwd=linked)

        self.assertEqual(result.returncode, 0, output(result))
        self.assertEqual(self.session.read_text(encoding="utf-8"), prepared)
        self.assertEqual(set(self.state_files()) - before, {"SESSION.md"})
        self.assertEqual(sorted(path.name for path in (linked / ".handoff").iterdir()), tracked)

    def test_from_linked_worktree_keeps_prepared_snapshot_of_main_checkout(self) -> None:
        linked = self.root / "linked"
        self.git("worktree", "add", "-q", "-b", "linked", str(linked))
        other_agent_draft = filled_snapshot(body="черновик другого агента")
        self.prepared.write_text(other_agent_draft, encoding="utf-8")
        (linked / ".handoff" / "SESSION.next.md").write_text(filled_snapshot(), encoding="utf-8")

        result = self.run_script("save", checkout=linked, cwd=linked)

        self.assertEqual(result.returncode, 0, output(result))
        self.assertEqual(self.prepared.read_text(encoding="utf-8"), other_agent_draft)

    def test_saving_snapshot_that_is_already_saved_adds_no_archive(self) -> None:
        saved = filled_snapshot()
        self.session.write_text(saved, encoding="utf-8")
        self.prepared.write_text(saved, encoding="utf-8")

        result = self.run_script("save")

        self.assertEqual(result.returncode, 0, output(result))
        self.assertEqual(self.state_files().get("SESSION.md"), saved.encode("utf-8"))
        self.assertFalse(self.archive.exists())
        self.assertFalse(self.prepared.exists())

    def test_prints_start_command_for_every_registry_runtime(self) -> None:
        self.prepared.write_text(filled_snapshot(), encoding="utf-8")

        result = self.run_script("save")

        lines = result.stdout.splitlines()
        self.assertIn(RESUME_HEADER, lines, output(result))
        expected = [
            "  " + RUNTIMES[runtime_id]["commands"]["start"].replace("{prompt}", MANIFEST["resume_prompt"])
            for runtime_id in MANIFEST["runtimes"]
        ]
        self.assertEqual(lines[lines.index(RESUME_HEADER) + 1 :], expected)
        self.assertNotIn("{prompt}", result.stdout)


class StartTest(HandoffCase):
    def test_detects_runtime_from_env_marker(self) -> None:
        runtime = next(runtime for runtime in RUNTIMES.values() if runtime["detect_env"])
        marker = runtime["detect_env"][0]

        result = self.run_script("start", **{marker: "1"})

        self.assertEqual(result.returncode, 0, output(result))
        self.assertEqual(
            result.stdout.splitlines()[:2],
            [
                f"Рантайм: {runtime['name']} ({runtime['id']}), распознан по переменной {marker}",
                "Если это не твой рантайм, повтори: python3 .handoff/handoff.py start --runtime <id>",
            ],
        )

    def test_accepts_explicit_runtime_given_as_alias_in_any_case(self) -> None:
        runtime = next(runtime for runtime in RUNTIMES.values() if runtime["aliases"])

        result = self.run_script("start", "--runtime", runtime["aliases"][0].upper())

        self.assertEqual(result.returncode, 0, output(result))
        self.assertEqual(result.stdout.splitlines()[0], f"Рантайм: {runtime['name']} ({runtime['id']}), указан явно")

    def test_explicit_runtime_wins_over_env_marker(self) -> None:
        marked, chosen = [runtime for runtime in RUNTIMES.values() if runtime["detect_env"]][:2]

        result = self.run_script("start", "--runtime", chosen["id"], **{marked["detect_env"][0]: "1"})

        self.assertEqual(
            result.stdout.splitlines()[:2],
            [
                f"Рантайм: {chosen['name']} ({chosen['id']}), указан явно",
                f"Конфигурация: runtime-config/runtimes/{chosen['id']}.json",
            ],
        )

    def test_exits_2_with_id_list_when_no_marker_is_set(self) -> None:
        result = self.run_script("start")

        self.assertEqual((result.returncode, result.stdout), (2, ""))
        for runtime_id in MANIFEST["runtimes"]:
            self.assertIn(runtime_id, result.stderr)
        self.assertIn("--runtime <id>", result.stderr)

    def test_treats_empty_marker_as_unset(self) -> None:
        marker = sorted(MARKERS)[0]

        self.assertEqual(self.run_script("start", **{marker: ""}).returncode, 2)

    def test_exits_2_naming_both_runtimes_when_two_markers_are_set(self) -> None:
        first, second = [runtime for runtime in RUNTIMES.values() if runtime["detect_env"]][:2]
        markers = {first["detect_env"][0]: "1", second["detect_env"][0]: "1"}

        result = self.run_script("start", **markers)

        self.assertEqual((result.returncode, result.stdout), (2, ""))
        for marker in markers:
            self.assertIn(marker, result.stderr)
        for runtime_id in MANIFEST["runtimes"]:
            self.assertIn(runtime_id, result.stderr)
        self.assertIn("--runtime <id>", result.stderr)

    def test_exits_2_with_id_list_for_unregistered_runtime(self) -> None:
        result = self.run_script("start", "--runtime", "hal9000")

        self.assertEqual((result.returncode, result.stdout), (2, ""))
        for runtime_id in MANIFEST["runtimes"]:
            self.assertIn(runtime_id, result.stderr)

    def test_accepts_unknown_runtime_without_config_lines(self) -> None:
        result = self.run_script("start", "--runtime", "unknown")

        self.assertEqual(result.returncode, 0, output(result))
        lines = result.stdout.splitlines()
        self.assertEqual(lines[0], "Рантайм: неизвестен (unknown)")
        self.assertEqual(lines[1], f"Состояние: {self.state}")

    def test_briefs_resumed_session_in_fixed_order(self) -> None:
        runtime = next(runtime for runtime in RUNTIMES.values() if runtime["checked"]["unconfirmed"])
        chosen = {field: choices[-1] for field, choices in enumerated_fields(TEMPLATE).items()}
        snapshot = filled_snapshot(time="2026-10-13T09:00:00Z", runtime="grok")
        for field, choice in chosen.items():
            snapshot = set_field(snapshot, field, f"`{choice}`")
        self.session.write_text(snapshot, encoding="utf-8")
        self.archive.mkdir()
        for name in ("20261012T180500000000Z-codex.md", "20261013T080000000000Z-claude.md"):
            (self.archive / name).write_text("старый снимок\n", encoding="utf-8")

        result = self.run_script("start", "--runtime", runtime["id"])

        self.assertEqual(result.returncode, 0, output(result))
        self.assertEqual(
            result.stdout.splitlines(),
            [
                f"Рантайм: {runtime['name']} ({runtime['id']}), указан явно",
                f"Конфигурация: runtime-config/runtimes/{runtime['id']}.json",
                f"Входные файлы: {', '.join(runtime['entry_files'])}",
                *(f"Не подтверждено: {note}" for note in runtime["checked"]["unconfirmed"]),
                f"Состояние: {self.state}",
                "Рабочая копия: основной клон",
                f"Снимок: SESSION.md, схема {SCHEMA}, снят 2026-10-13T09:00:00Z, рантайм grok",
                *(f"{field}: {choice}" for field, choice in chosen.items()),
                "Архив: 2 снимка, последний 20261013T080000000000Z-claude.md",
                "Дальше: прочитай .handoff/README.md, раздел «Возобновление сессии», затем снимок.",
            ],
        )

    def test_reports_enumerated_field_absent_from_older_snapshot(self) -> None:
        self.session.write_text(drop_field(filled_snapshot(), ENUM_FIELD), encoding="utf-8")

        result = self.run_script("start", "--runtime", "unknown")

        self.assertIn(f"{ENUM_FIELD}: в снимке не указан", result.stdout.splitlines())

    def test_prints_one_line_per_enumerated_field_of_real_template(self) -> None:
        self.template.write_text(REAL_TEMPLATE, encoding="utf-8")
        self.session.write_text(filled_snapshot(), encoding="utf-8")

        result = self.run_script("start", "--runtime", "unknown")

        self.assertEqual(result.returncode, 0, output(result))
        self.assertEqual(
            result.stdout.splitlines()[3:],
            [
                f"Снимок: SESSION.md, схема {SCHEMA}, снят 2026-10-13T09:00:00Z, рантайм claude",
                *(f"{field}: {choices[0]}" for field, choices in enumerated_fields(REAL_TEMPLATE).items()),
                "Архив: пусто",
                "Дальше: прочитай .handoff/README.md, раздел «Возобновление сессии», затем снимок.",
            ],
        )

    def test_summarises_schema_1_snapshot_by_its_sender(self) -> None:
        self.session.write_text(schema1_snapshot("Claude Code", "2026-10-12T18:51:09Z"), encoding="utf-8")

        result = self.run_script("start", "--runtime", "unknown")

        self.assertIn(
            "Снимок: SESSION.md, схема 1, снят 2026-10-12T18:51:09Z, рантайм claude", result.stdout.splitlines()
        )

    def test_reports_first_session_when_there_is_no_snapshot(self) -> None:
        result = self.run_script("start", "--runtime", "unknown")

        self.assertEqual(result.returncode, 0, output(result))
        self.assertEqual(
            result.stdout.splitlines()[-3:],
            [
                "Снимок: нет. Это первая сессия в этом клоне.",
                "Архив: пусто",
                "Дальше: прочитай .handoff/README.md, раздел «Первая сессия».",
            ],
        )

    def test_points_to_newest_archived_snapshot_when_session_is_missing(self) -> None:
        newest = "20261013T080000000000Z-claude.md"
        self.archive.mkdir()
        for name in ("20261012T180500000000Z-codex.md", newest):
            (self.archive / name).write_text("старый снимок\n", encoding="utf-8")

        result = self.run_script("start", "--runtime", "unknown")

        self.assertEqual(result.returncode, 0, output(result))
        self.assertEqual(
            result.stdout.splitlines()[-3:],
            [
                "Снимок: SESSION.md нет. Последний снимок лежит в архиве.",
                f"Архив: 2 снимка, последний {newest}",
                f"Дальше: прочитай .handoff/README.md, раздел «Возобновление сессии», затем archive/{newest}.",
            ],
        )

    def test_warns_about_prepared_snapshot_that_was_never_saved(self) -> None:
        self.prepared.write_text(filled_snapshot(), encoding="utf-8")

        result = self.run_script("start", "--runtime", "unknown")

        self.assertEqual(len([line for line in result.stdout.splitlines() if "SESSION.next.md" in line]), 1)

    def test_from_linked_worktree_reports_main_checkout_state(self) -> None:
        linked = self.root / "linked"
        self.git("worktree", "add", "-q", "-b", "linked", str(linked))

        result = self.run_script("start", "--runtime", "unknown", checkout=linked, cwd=linked)

        self.assertEqual(
            result.stdout.splitlines()[1:3], [f"Состояние: {self.state}", "Рабочая копия: worktree ../linked"]
        )

    def test_ignores_process_cwd(self) -> None:
        result = self.run_script("start", "--runtime", "unknown", cwd=self.root)

        self.assertEqual(result.stdout.splitlines()[1:2], [f"Состояние: {self.state}"])

    def test_ignores_git_dir_inherited_from_hook_or_alias(self) -> None:
        result = self.run_script("start", "--runtime", "unknown", GIT_DIR=str(self.repo / ".git"))

        self.assertEqual(result.stdout.splitlines()[1:3], [f"Состояние: {self.state}", "Рабочая копия: основной клон"])


MODE_FIELD = "Режим тьютора"
SKILL_USAGE = (
    "использование: chebu-tutor --execute|--guide|--walkthrough|--sandbox|--quiz [цель, тикет, ограничения]"
)


class ModeTest(HandoffCase):
    def start_with_words(self, words: str) -> subprocess.CompletedProcess[str]:
        return self.run_script("start", "--runtime", "unknown", "--mode", stdin=words)

    def plain_start(self) -> list[str]:
        result = self.run_script("start", "--runtime", "unknown")
        self.assertEqual(result.returncode, 0, output(result))
        return result.stdout.splitlines()

    def assert_refused(self, result: subprocess.CompletedProcess[str], reason: str, usage: str = SKILL_USAGE) -> None:
        self.assertEqual((result.returncode, result.stdout), (2, ""), output(result))
        lines = result.stderr.splitlines()
        self.assertTrue(lines[0].startswith("ошибка:"), result.stderr)
        self.assertIn(reason, lines[0])
        self.assertEqual(lines[-1], usage)

    def test_one_flag_with_student_text_replaces_only_the_mode_line(self) -> None:
        self.session.write_text(filled_snapshot(), encoding="utf-8")
        recorded = f"{MODE_FIELD}: execute"
        plain = self.plain_start()
        self.assertIn(recorded, plain)

        result = self.start_with_words("--guide тикет EDU-02, код пишу сам. DeepSeek не запускать.")

        self.assertEqual((result.returncode, result.stderr), (0, ""), output(result))
        changed = f"{MODE_FIELD}: guide по флагу, в снимке был execute"
        self.assertEqual(result.stdout.splitlines(), [changed if line == recorded else line for line in plain])

    def test_flag_equal_to_snapshot_mode_is_confirmed(self) -> None:
        self.session.write_text(filled_snapshot(), encoding="utf-8")

        result = self.start_with_words("--execute")

        self.assertEqual(result.returncode, 0, output(result))
        self.assertIn(f"{MODE_FIELD}: execute, из снимка и флага", result.stdout.splitlines())

    def test_flag_names_absent_snapshot_mode(self) -> None:
        line = f"{MODE_FIELD}: quiz по флагу, в снимке режима нет"
        with self.subTest("older snapshot without the field"):
            self.session.write_text(drop_field(filled_snapshot(), MODE_FIELD), encoding="utf-8")
            plain = self.plain_start()

            result = self.start_with_words("--quiz")

            absent = f"{MODE_FIELD}: в снимке не указан"
            self.assertEqual(result.stdout.splitlines(), [line if entry == absent else entry for entry in plain])
        with self.subTest("first session"):
            self.session.unlink()
            plain = self.plain_start()

            result = self.start_with_words("--quiz")

            after = plain.index("Снимок: нет. Это первая сессия в этом клоне.") + 1
            self.assertEqual(result.stdout.splitlines(), [*plain[:after], line, *plain[after:]])

    def test_flag_compares_with_newest_archived_snapshot_when_session_is_missing(self) -> None:
        self.archive.mkdir()
        older = set_field(filled_snapshot(), MODE_FIELD, "`guide`")
        (self.archive / "20261012T180500000000Z-codex.md").write_text(older, encoding="utf-8")
        (self.archive / "20261013T080000000000Z-claude.md").write_text(filled_snapshot(), encoding="utf-8")
        plain = self.plain_start()

        result = self.start_with_words("--quiz")

        after = plain.index("Снимок: SESSION.md нет. Последний снимок лежит в архиве.") + 1
        line = f"{MODE_FIELD}: quiz по флагу, в снимке был execute"
        self.assertEqual(result.stdout.splitlines(), [*plain[:after], line, *plain[after:]])

    def test_no_flag_prints_usage_then_unchanged_briefing(self) -> None:
        self.session.write_text(filled_snapshot(), encoding="utf-8")
        plain = self.plain_start()
        for words in ("тикет EDU-02, код пишу сам", ""):
            with self.subTest(words=words):
                result = self.start_with_words(words)

                self.assertEqual((result.returncode, result.stderr), (0, ""), output(result))
                self.assertEqual(result.stdout.splitlines(), [SKILL_USAGE, *plain])

    def test_two_flags_are_refused_before_briefing(self) -> None:
        self.session.write_text(filled_snapshot(), encoding="utf-8")
        for words, count in (("--guide --quiz", 2), ("--guide тикет EDU-02 --guide", 2), ("--guide --quiz --sandbox", 3)):
            with self.subTest(words=words):
                self.assert_refused(self.start_with_words(words), f"получено {count}")

    def test_unsubstituted_placeholder_is_refused(self) -> None:
        self.session.write_text(filled_snapshot(), encoding="utf-8")
        for words in ("$ARGUMENTS", "--quiz $ARGUMENTS"):
            with self.subTest(words=words):
                self.assert_refused(self.start_with_words(words), "осталось $ARGUMENTS")

    def test_flag_outside_the_list_is_refused(self) -> None:
        for flag in ("--exec", "--help", "--Guide", "--"):
            with self.subTest(flag=flag):
                self.assert_refused(self.start_with_words(f"{flag} тикет EDU-02"), f"флаг {flag} не входит")

    def test_quotes_dollars_and_newlines_do_not_change_the_parse(self) -> None:
        words = "тикет \"EDU-02\" don't $HOME `id` $(id)\n--walkthrough\nразберём agent_loop()"

        result = self.start_with_words(words)

        self.assertEqual(result.returncode, 0, output(result))
        self.assertIn(f"{MODE_FIELD}: walkthrough по флагу, в снимке режима нет", result.stdout.splitlines())

    def test_flags_follow_the_mode_enumeration_of_the_template(self) -> None:
        modes = "execute / guide / walkthrough / sandbox / quiz / pair"
        self.template.write_text(set_field(TEMPLATE, MODE_FIELD, f"`<{modes}>`"), encoding="utf-8")
        usage = SKILL_USAGE.replace("--quiz", "--quiz|--pair")

        accepted = self.start_with_words("--pair")

        self.assertEqual(accepted.returncode, 0, output(accepted))
        self.assertIn(f"{MODE_FIELD}: pair по флагу, в снимке режима нет", accepted.stdout.splitlines())
        self.assert_refused(self.start_with_words("--exec"), "флаг --exec не входит", usage)

    def test_without_mode_key_stdin_is_ignored(self) -> None:
        plain = self.plain_start()

        result = self.run_script("start", "--runtime", "unknown", stdin="--exec --guide")

        self.assertEqual((result.returncode, result.stdout.splitlines()), (0, plain), output(result))


class CommandLineTest(HandoffCase):
    def test_rejects_unknown_command_with_russian_usage(self) -> None:
        result = self.run_script("resume")

        self.assertEqual((result.returncode, result.stdout), (2, ""))
        self.assertTrue(result.stderr.startswith("ошибка:"), result.stderr)
        self.assertIn("использование:", result.stderr)
        self.assertNotIn("usage:", result.stderr)


class RegistryTest(unittest.TestCase):
    def test_resume_prompt_survives_double_quotes_of_start_commands(self) -> None:
        self.assertFalse(set('"$`\\') & set(MANIFEST["resume_prompt"]), "the printed start commands would break")

    def test_manifest_lists_exactly_the_runtime_files(self) -> None:
        self.assertEqual(sorted(MANIFEST["runtimes"]), sorted(RUNTIMES))
        for stem, runtime in RUNTIMES.items():
            self.assertEqual(runtime["id"], stem)

    def test_names_and_markers_identify_one_runtime(self) -> None:
        names = [name.lower() for runtime in RUNTIMES.values() for name in (runtime["id"], *runtime["aliases"])]
        markers = [marker for runtime in RUNTIMES.values() for marker in runtime["detect_env"]]
        self.assertEqual(len(names), len(set(names)), "an id or alias is claimed by two runtimes")
        self.assertEqual(len(markers), len(set(markers)), "an environment marker is claimed by two runtimes")
        self.assertNotIn("unknown", names)

    def test_agents_md_names_every_runtime_id(self) -> None:
        agents = (PROJECT / "AGENTS.md").read_text(encoding="utf-8")
        for runtime_id in (*MANIFEST["runtimes"], "unknown"):
            self.assertIn(f"`{runtime_id}`", agents)


if __name__ == "__main__":
    unittest.main()
