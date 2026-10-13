from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import issues_sync

REPO_URL = "https://github.com/alanbigulov/chebupelka-jev"
SCOPE = issues_sync.SHARED_SECTIONS["Границы работы"]
COMPLETION = issues_sync.SHARED_SECTIONS["Запись завершения"]

ISSUE_1_BODY = """## Контекст и учебная тема

Правильная история нескольких инструментов; протокол сообщений. Исходная база: v0.1.1. Место изменения: `agent_loop()`.

## Критерии готовности

- [ ] Одно assistant-сообщение со всеми вызовами, отдельный результат каждого.
- [ ] запрос с двумя вызовами корректно продолжается.
- [ ] Необходимые локальные проверки результата проходят без реального API.
- [ ] Ссылки на изменения и результаты проверки записаны в issue.
- [ ] Учебное объяснение связано с будущим учебным пакетом целевой версии v0.1.4.

## Границы работы

Сначала воспроизвести нынешнее поведение и согласовать минимальный план с владельцем. Не реализовывать остальные задачи автоматически. Целевая версия предварительная, срок не назначен. Частичное выполнение не означает завершение всей задачи.

## Источники

- [Код исходной базы](https://github.com/alanbigulov/chebupelka-jev/blob/v0.1.1/agent/chebupelkajev.py).
- [Существующие локальные проверки](https://github.com/alanbigulov/chebupelka-jev/blob/v0.1.1/agent/tests/test_agent.py).
- [Учебный roadmap](https://github.com/alanbigulov/chebupelka-jev/blob/main/coding-agent-developement/development-roadmap.md).
- [Паспорта уроков](https://github.com/alanbigulov/chebupelka-jev/blob/main/coding-agent-developement/README.md).

## Запись завершения

Указать коммит или PR, выполненные команды и результаты, непроверенные сценарии и ссылку на урок. После проверки закрыть issue и синхронизировать Status проекта с Готово.


## Решение о составе v0.1.2

По согласованному решению владельца v0.1.2 фиксирует текущий трекер и урок о его создании. Эта задача кода остаётся открытой и переносится в предварительную v0.1.3.

## Решение о составе v0.1.3

По согласованному решению владельца v0.1.3 содержит только переименование проекта. Исходник в main теперь называется `agent/chebu.py`.
"""

EDU_01 = """# EDU-01. Правильная история нескольких инструментов

| Поле | Значение |
|---|---|
| ID | EDU-01 |
| Учебная тема | Протокол сообщений |
| Область и тип | area:agent, type:bug |
| Место изменения | `agent_loop()` |
| Исходная база | v0.1.1 |
| Целевая версия в трекере владельца | v0.1.4 |
| Issue в трекере владельца | [#1](https://github.com/alanbigulov/chebupelka-jev/issues/1) |

## Критерии готовности

- [ ] Одно assistant-сообщение со всеми вызовами, отдельный результат каждого.
- [ ] Запрос с двумя вызовами корректно продолжается.
- [ ] Необходимые локальные проверки результата проходят без реального API.
- [ ] Ссылки на изменения и результаты проверки записаны в трекере: в issue или в снимке `.handoff/`.
- [ ] Учебное объяснение изменения записано и связано с версией, в которую изменение входит.

## Источники

- [Код исходной базы](https://github.com/alanbigulov/chebupelka-jev/blob/v0.1.1/agent/chebupelkajev.py).
- [Существующие локальные проверки](https://github.com/alanbigulov/chebupelka-jev/blob/v0.1.1/agent/tests/test_agent.py).
- [Учебный roadmap](../development-roadmap.md).
- [Паспорта уроков](../README.md).
"""


def make_issue(
    number=7,
    title="[EDU-07] Параметры URL, модели и лимита; конфигурация",
    labels=("area:agent", "type:feature"),
    milestone="v0.2.0",
    baseline="v0.1.1",
    place="Константы и CLI",
    context=None,
    criteria=("- [ ] Настройки задаются без редактирования исходников.",),
    sources=(f"- [Код исходной базы]({REPO_URL}/blob/v0.1.1/agent/chebupelkajev.py).",),
    scope=SCOPE,
    completion=COMPLETION,
    tail="",
):
    if context is None:
        summary = title.split("] ", 1)[1]
        context = f"{summary}. Исходная база: {baseline}. Место изменения: {place}."
    body = "\n\n".join(
        [
            f"## Контекст и учебная тема\n\n{context}",
            "## Критерии готовности\n\n" + "\n".join(criteria),
            f"## Границы работы\n\n{scope}",
            "## Источники\n\n" + "\n".join(sources),
            f"## Запись завершения\n\n{completion}",
        ]
    )
    return {
        "number": number,
        "title": title,
        "labels": [{"name": name} for name in labels],
        "milestone": {"title": milestone} if milestone else None,
        "body": body + tail,
        "url": f"{REPO_URL}/issues/{number}",
    }


def section(text, heading):
    lines = text.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0].splitlines()
    return [line for line in lines if line]


class RenderTests(unittest.TestCase):
    def assert_row(self, text, name, value):
        self.assertIn(f"| {name} | {value} |", text.splitlines())

    def test_issue_1_becomes_the_agreed_file(self):
        issue = make_issue(
            number=1,
            title="[EDU-01] Правильная история нескольких инструментов; протокол сообщений",
            labels=("area:agent", "type:bug"),
            milestone="v0.1.4",
        )
        issue["body"] = ISSUE_1_BODY
        self.assertEqual(issues_sync.render(issue), EDU_01)

    def test_title_gives_id_task_and_theme(self):
        text = issues_sync.render(
            make_issue(title="[EDU-08] Работа с режимом рассуждений DeepSeek; полный ответ API")
        )
        self.assertEqual(text.splitlines()[0], "# EDU-08. Работа с режимом рассуждений DeepSeek")
        self.assert_row(text, "ID", "EDU-08")
        self.assert_row(text, "Учебная тема", "Полный ответ API")

    def test_context_gives_baseline_and_place(self):
        places = ("`run_bash()`", "Константы и CLI", "`json.loads()` и `call_tool()`")
        for place in places:
            with self.subTest(place=place):
                text = issues_sync.render(make_issue(baseline="v0.1.3", place=place))
                self.assert_row(text, "Исходная база", "v0.1.3")
                self.assert_row(text, "Место изменения", place)

    def test_context_that_adds_to_the_title_is_rejected(self):
        issue = make_issue(
            number=4,
            context="Другая задача; другая тема. Исходная база: v0.1.1. Место изменения: `run_bash()`.",
        )
        with self.assertRaises(issues_sync.TicketError) as raised:
            issues_sync.render(issue)
        self.assertIn("issue #4", str(raised.exception))
        self.assertIn("Контекст и учебная тема", str(raised.exception))

    def test_only_area_and_type_labels_are_listed_area_first(self):
        text = issues_sync.render(
            make_issue(labels=("status:partial", "type:testing", "area:agent"))
        )
        self.assert_row(text, "Область и тип", "area:agent, type:testing")

    def test_label_order_from_gh_does_not_change_the_file(self):
        labels = ("area:docs", "type:bug", "area:agent")
        self.assertEqual(
            issues_sync.render(make_issue(labels=labels)),
            issues_sync.render(make_issue(labels=labels[::-1])),
        )

    def test_milestone_title_or_placeholder(self):
        row = "Целевая версия в трекере владельца"
        self.assert_row(issues_sync.render(make_issue(milestone="v0.3.0")), row, "v0.3.0")
        self.assert_row(issues_sync.render(make_issue(milestone=None)), row, "не назначена")

    def test_issue_row_links_to_the_issue(self):
        text = issues_sync.render(make_issue(number=12))
        self.assert_row(text, "Issue в трекере владельца", f"[#12]({REPO_URL}/issues/12)")

    def test_criteria_keep_order_and_state_and_start_with_a_capital(self):
        text = issues_sync.render(
            make_issue(
                criteria=(
                    "- [x] один pwd передаёт результат и ID во второй запрос.",
                    "- [ ] `reasoning_content` сохраняется согласно протоколу.",
                    "- [x] Добавить проверку предела ходов.",
                    "- [ ] ключ не печатается.",
                )
            )
        )
        self.assertEqual(
            section(text, "Критерии готовности"),
            [
                "- [x] Один pwd передаёт результат и ID во второй запрос.",
                "- [ ] `reasoning_content` сохраняется согласно протоколу.",
                "- [x] Добавить проверку предела ходов.",
                "- [ ] Ключ не печатается.",
            ],
        )

    def test_tracker_criteria_are_reworded_for_a_student(self):
        text = issues_sync.render(
            make_issue(
                criteria=(
                    "- [ ] Ссылки на изменения и результаты проверки записаны в issue.",
                    "- [ ] Учебное объяснение связано с будущим учебным пакетом целевой версии v0.1.4.",
                    "- [x] Учебное объяснение связано с соответствующей версией и задачей LEARN-v0.1.2, если изменение входит в этот выпуск.",
                )
            )
        )
        explanation = (
            "Учебное объяснение изменения записано и связано с версией, в которую изменение входит."
        )
        self.assertEqual(
            section(text, "Критерии готовности"),
            [
                "- [ ] Ссылки на изменения и результаты проверки записаны в трекере: в issue или в снимке `.handoff/`.",
                f"- [ ] {explanation}",
                f"- [x] {explanation}",
            ],
        )

    def test_trailing_spaces_do_not_hide_a_tracker_criterion(self):
        criterion = "- [ ] Ссылки на изменения и результаты проверки записаны в issue.  "
        text = issues_sync.render(make_issue(criteria=(criterion,)))
        self.assertEqual(
            section(text, "Критерии готовности"),
            [
                "- [ ] Ссылки на изменения и результаты проверки записаны в трекере: в issue или в снимке `.handoff/`."
            ],
        )

    def test_criterion_that_only_resembles_the_tracker_one_is_kept(self):
        criterion = "- [ ] Ссылки на изменения и результаты проверки записаны в issue и в PR."
        text = issues_sync.render(make_issue(criteria=(criterion,)))
        self.assertEqual(section(text, "Критерии готовности"), [criterion])

    def test_line_that_is_not_a_criterion_is_rejected(self):
        issue = make_issue(number=9, criteria=("- [ ] Первый.", "Примечание владельца."))
        with self.assertRaises(issues_sync.TicketError) as raised:
            issues_sync.render(issue)
        self.assertIn("issue #9", str(raised.exception))
        self.assertIn("Примечание владельца.", str(raised.exception))

    def test_links_to_main_become_relative_and_tag_links_stay(self):
        text = issues_sync.render(
            make_issue(
                sources=(
                    f"- [Код исходной базы]({REPO_URL}/blob/v0.1.1/agent/chebupelkajev.py).",
                    f"- [Учебный roadmap]({REPO_URL}/blob/main/coding-agent-developement/development-roadmap.md).",
                    f"- [Правила версий]({REPO_URL}/blob/main/VERSIONING.md).",
                    f"- [Урок]({REPO_URL}/blob/main/coding-agent-developement/lessons-v0.1.1/version.md).",
                    "- [Чужой проект](https://github.com/someone/else/blob/main/README.md).",
                )
            )
        )
        self.assertEqual(
            section(text, "Источники"),
            [
                f"- [Код исходной базы]({REPO_URL}/blob/v0.1.1/agent/chebupelkajev.py).",
                "- [Учебный roadmap](../development-roadmap.md).",
                "- [Правила версий](../../VERSIONING.md).",
                "- [Урок](../lessons-v0.1.1/version.md).",
                "- [Чужой проект](https://github.com/someone/else/blob/main/README.md).",
            ],
        )

    def test_shared_sections_are_dropped(self):
        text = issues_sync.render(make_issue())
        for heading, shared in issues_sync.SHARED_SECTIONS.items():
            self.assertNotIn(heading, text)
            self.assertNotIn(shared, text)

    def test_shared_section_matches_after_reflow(self):
        reflowed = SCOPE.replace(". ", ".\n", 1).replace(", ", ",  ", 1)
        self.assertNotEqual(reflowed, SCOPE)
        self.assertEqual(
            issues_sync.render(make_issue(scope=reflowed)), issues_sync.render(make_issue())
        )

    def test_shared_section_with_its_own_text_is_rejected(self):
        own_text = {
            "Границы работы": make_issue(number=5, scope=SCOPE + " Сеть не трогать."),
            "Запись завершения": make_issue(number=5, completion="Указать только PR."),
        }
        for heading, issue in own_text.items():
            with self.subTest(heading=heading):
                with self.assertRaises(issues_sync.TicketError) as raised:
                    issues_sync.render(issue)
                self.assertIn("issue #5", str(raised.exception))
                self.assertIn(f"«{heading}»", str(raised.exception))

    def test_unknown_heading_is_rejected(self):
        issue = make_issue(number=11, tail="\n\n## Заметки владельца\n\nПроверить позже.")
        with self.assertRaises(issues_sync.TicketError) as raised:
            issues_sync.render(issue)
        self.assertIn("issue #11", str(raised.exception))
        self.assertIn("«Заметки владельца»", str(raised.exception))

    def test_text_above_the_first_heading_is_rejected(self):
        issue = make_issue(number=10)
        issue["body"] = "Срочно: согласовать с владельцем.\n\n" + issue["body"]
        with self.assertRaises(issues_sync.TicketError) as raised:
            issues_sync.render(issue)
        self.assertIn("issue #10", str(raised.exception))
        self.assertIn("Срочно: согласовать с владельцем.", str(raised.exception))

    def test_repeated_heading_keeps_the_lines_of_both_sections(self):
        text = issues_sync.render(
            make_issue(
                sources=("- [Первый](https://example.org/1).",),
                tail="\n\n## Источники\n\n- [Второй](https://example.org/2).",
            )
        )
        self.assertEqual(
            section(text, "Источники"),
            ["- [Первый](https://example.org/1).", "- [Второй](https://example.org/2)."],
        )

    def test_missing_section_is_rejected(self):
        issue = make_issue(number=3)
        body = issue["body"]
        issue["body"] = body[: body.index("## Источники")] + body[body.index("## Запись") :]
        with self.assertRaises(issues_sync.TicketError) as raised:
            issues_sync.render(issue)
        self.assertIn("issue #3", str(raised.exception))
        self.assertIn("«Источники»", str(raised.exception))

    def test_title_of_another_shape_is_rejected(self):
        issue = make_issue(number=15, title="Приёмка выпуска v0.1.3", context="x")
        with self.assertRaises(issues_sync.TicketError) as raised:
            issues_sync.render(issue)
        self.assertIn("issue #15", str(raised.exception))
        self.assertIn("Приёмка выпуска v0.1.3", str(raised.exception))

    def test_release_decision_sections_are_dropped(self):
        decisions = (
            "\n\n\n## Решение о составе v0.1.2\n\nЗадача переносится в v0.1.3."
            "\n\n## Решение о составе v0.1.3\n\nЗадача переносится в v0.1.4.\n"
        )
        self.assertEqual(
            issues_sync.render(make_issue(tail=decisions)), issues_sync.render(make_issue())
        )

    def test_file_ends_with_one_newline(self):
        for tail in ("", "\n", "\n\n\n"):
            with self.subTest(tail=tail):
                text = issues_sync.render(make_issue(tail=tail))
                self.assertEqual(text, text.rstrip("\n") + "\n")

    def test_body_saved_by_the_browser_renders_the_same(self):
        browser = make_issue()
        browser["body"] = browser["body"].replace("\n", "\r\n")
        self.assertEqual(issues_sync.render(browser), issues_sync.render(make_issue()))


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.issues = {
            1: make_issue(number=1, title="[EDU-01] История инструментов; протокол сообщений"),
            2: make_issue(number=2, title="[EDU-02] HTTP-таймаут; граница сети"),
        }
        self.commands = []

    def gh(self, command, **options):
        self.commands.append(command)
        issue = self.issues[int(command[3])]
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(issue), stderr="")

    def run_cli(self, *arguments, gh=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(issues_sync, "TICKETS_DIR", self.folder):
            with patch.object(issues_sync.subprocess, "run", side_effect=gh or self.gh):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = issues_sync.main(["--numbers", "1", "2", *arguments])
        return code, stdout.getvalue(), stderr.getvalue()

    def files(self):
        return sorted(path.name for path in self.folder.iterdir())

    def test_written_files_match_on_the_next_check(self):
        code, _, _ = self.run_cli("--write")
        self.assertEqual(code, 0)
        self.assertEqual(self.files(), ["EDU-01.md", "EDU-02.md"])
        self.assertEqual(
            (self.folder / "EDU-02.md").read_bytes(),
            issues_sync.render(self.issues[2]).encode("utf-8"),
        )

        code, stdout, _ = self.run_cli()
        self.assertEqual(code, 0)
        self.assertEqual(stdout.splitlines(), ["EDU-01.md: совпадает", "EDU-02.md: совпадает"])

    def test_edited_file_is_reported_with_a_diff_towards_the_issue(self):
        self.run_cli("--write")
        path = self.folder / "EDU-02.md"
        fresh = "- [ ] Настройки задаются без редактирования исходников."
        edited = "- [x] Настройки задаются без редактирования исходников."
        path.write_text(path.read_text(encoding="utf-8").replace(fresh, edited), encoding="utf-8")

        code, stdout, _ = self.run_cli()
        lines = stdout.splitlines()
        self.assertEqual(code, 1)
        self.assertIn("EDU-01.md: совпадает", lines)
        self.assertIn("EDU-02.md: расходится", lines)
        self.assertIn(f"-{edited}", lines)
        self.assertIn(f"+{fresh}", lines)

    def test_file_without_final_newline_is_reported(self):
        self.run_cli("--write")
        path = self.folder / "EDU-01.md"
        path.write_bytes(path.read_bytes().rstrip(b"\n"))

        code, stdout, _ = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("EDU-01.md: расходится", stdout.splitlines())
        self.assertIn("\\ В конце файла нет новой строки", stdout.splitlines())

    def test_missing_file_is_reported_and_not_created(self):
        code, stdout, _ = self.run_cli()
        self.assertEqual(code, 1)
        self.assertEqual(stdout.splitlines(), ["EDU-01.md: нет файла", "EDU-02.md: нет файла"])
        self.assertEqual(self.files(), [])

    def test_gh_reads_the_named_repository(self):
        self.run_cli("--repo", "student/fork")
        self.assertEqual(
            [command[:4] for command in self.commands],
            [["gh", "issue", "view", "1"], ["gh", "issue", "view", "2"]],
        )
        for command in self.commands:
            self.assertEqual(command[command.index("-R") + 1], "student/fork")

    def test_missing_gh_stops_with_code_2(self):
        def no_gh(command, **options):
            raise FileNotFoundError(2, "No such file or directory", "gh")

        code, stdout, stderr = self.run_cli(gh=no_gh)
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("Не найдена команда gh", stderr)

    def test_failed_gh_call_stops_with_code_2(self):
        def failing_gh(command, **options):
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="HTTP 401\n")

        code, stdout, stderr = self.run_cli("--write", gh=failing_gh)
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("issue #1", stderr)
        self.assertIn("HTTP 401", stderr)
        self.assertEqual(self.files(), [])

    def test_issue_of_another_shape_stops_the_write_of_every_file(self):
        self.issues[1] = make_issue(number=1, completion="Указать только PR.")
        self.issues[2] = make_issue(number=2, tail="\n\n## Заметки владельца\n\nПозже.")

        code, stdout, stderr = self.run_cli("--write")
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("issue #1: раздел «Запись завершения»", stderr)
        self.assertIn("issue #2: неизвестный раздел «Заметки владельца»", stderr)
        self.assertEqual(self.files(), [])


if __name__ == "__main__":
    unittest.main()
