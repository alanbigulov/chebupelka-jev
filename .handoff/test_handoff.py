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
TEMPLATE = (HERE / "TEMPLATE.md").read_text(encoding="utf-8")
MANIFEST = json.loads((RUNTIME_CONFIG / "manifest.json").read_text(encoding="utf-8"))
RUNTIMES = {
    path.stem: json.loads(path.read_text(encoding="utf-8"))
    for path in sorted((RUNTIME_CONFIG / "runtimes").glob("*.json"))
}
MARKERS = {name for runtime in RUNTIMES.values() for name in runtime["detect_env"]}

PLACEHOLDER = re.compile(r"<[^<>\n]+>")
HEADINGS = re.findall(r"^## (.+)$", TEMPLATE, flags=re.MULTILINE)
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


def filled_snapshot(
    *,
    time: str = "2026-10-13T09:00:00Z",
    runtime: str = "claude",
    schema: int | None = None,
    unfilled: str | None = None,
    without_section: str | None = None,
    body: str = "",
) -> str:
    text = PLACEHOLDER.sub(lambda found: found.group() if found.group() == unfilled else "заполнено", TEMPLATE)
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

        self.state.mkdir(parents=True)
        for name in ("handoff.py", "TEMPLATE.md"):
            shutil.copy(HERE / name, self.state / name)
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
        self, *args: str, checkout: Path | None = None, cwd: Path | None = None, **env: str
    ) -> subprocess.CompletedProcess[str]:
        script = (checkout or self.repo) / ".handoff" / "handoff.py"
        return subprocess.run(
            [sys.executable, str(script), *args],
            cwd=cwd or self.repo,
            env=self.env(**env),
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
        text = filled_snapshot(body="## 11. Сверх шаблона")
        self.assert_single_problem(self.check(text), "11. Сверх шаблона", f"строка {line_of(text, '## 11.')}:")

    def test_reports_misplaced_section(self) -> None:
        moved = HEADINGS[3]
        text = filled_snapshot(without_section=moved, body=f"## {moved}")
        self.assert_single_problem(self.check(text), moved, f"строка {line_of(text, f'## {moved}')}:")

    def test_ignores_heading_inside_code_fence(self) -> None:
        self.assert_clean(self.check(filled_snapshot(body="```text\n## main...origin/main\n```")))

    def test_reports_missing_metadata_field(self) -> None:
        self.assert_single_problem(self.check(drop_field(filled_snapshot(), "Выпуск")), "Выпуск")

    def test_reports_empty_metadata_field(self) -> None:
        text = set_field(filled_snapshot(), "Выпуск", "")
        self.assert_single_problem(self.check(text), "Выпуск", f"строка {line_of(text, '| Выпуск |')}:")

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
        self.prepared.write_text(filled_snapshot(body="[черновик](../draft.md)"), encoding="utf-8")

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
        prepared = filled_snapshot()
        self.prepared.write_text(prepared, encoding="utf-8")

        result = self.run_script("save", checkout=linked, cwd=linked)

        self.assertEqual(result.returncode, 0, output(result))
        self.assertEqual(self.session.read_text(encoding="utf-8"), prepared)
        self.assertFalse(self.prepared.exists())
        self.assertEqual(
            sorted(path.name for path in (linked / ".handoff").iterdir()),
            ["README.md", "TEMPLATE.md", "handoff.py"],
        )

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
            result.stdout.splitlines()[0],
            f"Рантайм: {runtime['name']} ({runtime['id']}), распознан по переменной {marker}",
        )

    def test_accepts_explicit_runtime_given_as_alias_in_any_case(self) -> None:
        runtime = next(runtime for runtime in RUNTIMES.values() if runtime["aliases"])

        result = self.run_script("start", "--runtime", runtime["aliases"][0].upper())

        self.assertEqual(result.returncode, 0, output(result))
        self.assertEqual(result.stdout.splitlines()[0], f"Рантайм: {runtime['name']} ({runtime['id']}), указан явно")

    def test_explicit_runtime_wins_over_env_marker(self) -> None:
        marked, chosen = [runtime for runtime in RUNTIMES.values() if runtime["detect_env"]][:2]

        result = self.run_script("start", "--runtime", chosen["id"], **{marked["detect_env"][0]: "1"})

        self.assertEqual(result.stdout.splitlines()[:1], [f"Рантайм: {chosen['name']} ({chosen['id']}), указан явно"])

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
        self.session.write_text(filled_snapshot(time="2026-10-13T09:00:00Z", runtime="grok"), encoding="utf-8")
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
                "Снимок: SESSION.md, схема 2, снят 2026-10-13T09:00:00Z, рантайм grok",
                "Архив: 2 снимка, последний 20261013T080000000000Z-claude.md",
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

    def test_names_newest_archive_as_fallback_when_session_is_missing(self) -> None:
        self.archive.mkdir()
        for name in ("20261012T180500000000Z-codex.md", "20261013T080000000000Z-claude.md"):
            (self.archive / name).write_text("старый снимок\n", encoding="utf-8")

        result = self.run_script("start", "--runtime", "unknown")

        [archive_line] = [line for line in result.stdout.splitlines() if line.startswith("Архив:")]
        self.assertIn("20261013T080000000000Z-claude.md", archive_line)
        self.assertNotIn("20261012T180500000000Z-codex.md", archive_line)
        self.assertIn("прочитай", archive_line)

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


if __name__ == "__main__":
    unittest.main()
