from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_REPO = "alanbigulov/chebupelka-jev"
DEFAULT_NUMBERS = tuple(range(1, 13))
ISSUE_FIELDS = "number,title,labels,milestone,body,url"
TICKETS_DIR = Path(__file__).resolve().parent

TITLE = re.compile(r"\[(?P<id>[A-Z]+-\d+)\] (?P<task>.+?); (?P<theme>.+)")
CONTEXT = re.compile(
    r"(?P<summary>.+)\. Исходная база: (?P<baseline>\S+)\. Место изменения: (?P<place>.+)\."
)
CRITERION = re.compile(r"- \[(?P<state>[ x])\] (?P<text>.+)")

CONTEXT_HEADING = "Контекст и учебная тема"
CRITERIA_HEADING = "Критерии готовности"
SOURCES_HEADING = "Источники"
KEPT_HEADINGS = (CONTEXT_HEADING, CRITERIA_HEADING, SOURCES_HEADING)

# Every issue repeats these texts, so the tickets drop them and the folder's README states the rules once.
SHARED_SECTIONS = {
    "Границы работы": (
        "Сначала воспроизвести нынешнее поведение и согласовать минимальный план с владельцем. "
        "Не реализовывать остальные задачи автоматически. "
        "Целевая версия предварительная, срок не назначен. "
        "Частичное выполнение не означает завершение всей задачи."
    ),
    "Запись завершения": (
        "Указать коммит или PR, выполненные команды и результаты, непроверенные сценарии "
        "и ссылку на урок. "
        "После проверки закрыть issue и синхронизировать Status проекта с Готово."
    ),
}
# Release history of the owner's tracker, not part of the task.
DROPPED_HEADING_PREFIXES = ("Решение о составе",)

LABEL_PREFIXES = ("area:", "type:")
NO_MILESTONE = "не назначена"

# Criteria tied to the owner's tracker or release plan are reworded so that a student can meet them.
CRITERION_REWORDINGS = (
    (
        re.compile(r"Ссылки на изменения и результаты проверки записаны в issue\."),
        "Ссылки на изменения и результаты проверки записаны в трекере: "
        "в issue или в снимке `.handoff/`.",
    ),
    (
        re.compile(r"Учебное объяснение связано с.*"),
        "Учебное объяснение изменения записано и связано с версией, в которую изменение входит.",
    ),
)

# Path under the repository URL -> the same place relative to this folder. The first match wins.
# Links pinned to a tag match neither row and stay absolute.
MAIN_BRANCH_LINKS = (
    ("blob/main/coding-agent-developement/", "../"),
    ("blob/main/", "../../"),
)


class TicketError(Exception):
    pass


class GhError(Exception):
    pass


def _problem(issue: dict, text: str) -> TicketError:
    return TicketError(f"issue #{issue['number']}: {text}")


def _capitalise(text: str) -> str:
    return text[:1].upper() + text[1:]


def parse_title(issue: dict) -> dict[str, str]:
    title = TITLE.fullmatch(issue["title"])
    if not title:
        raise _problem(
            issue, f"заголовок «{issue['title']}» не имеет вида «[ID] задача; учебная тема»"
        )
    return title.groupdict()


def _kept_sections(issue: dict) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    heading = None
    for line in issue["body"].splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
            sections.setdefault(heading, [])
        elif line.strip():
            if heading is None:
                raise _problem(issue, f"текст до первого раздела: {line.strip()}")
            sections[heading].append(line.rstrip())

    for heading, lines in sections.items():
        if heading in SHARED_SECTIONS:
            text = " ".join(" ".join(lines).split())
            if text != SHARED_SECTIONS[heading]:
                raise _problem(
                    issue,
                    f"раздел «{heading}» отличается от общего текста.\n"
                    f"  В issue: {text}\n"
                    f"  Общий текст: {SHARED_SECTIONS[heading]}",
                )
        elif heading not in KEPT_HEADINGS and not heading.startswith(DROPPED_HEADING_PREFIXES):
            raise _problem(issue, f"неизвестный раздел «{heading}»")

    for heading in KEPT_HEADINGS:
        if heading not in sections:
            raise _problem(issue, f"нет раздела «{heading}»")
    return {heading: sections[heading] for heading in KEPT_HEADINGS}


def _criterion(issue: dict, line: str) -> str:
    criterion = CRITERION.fullmatch(line)
    if not criterion:
        raise _problem(
            issue, f"строка раздела «{CRITERIA_HEADING}» не имеет вида «- [ ] текст»: {line}"
        )
    text = _capitalise(criterion["text"])
    for pattern, replacement in CRITERION_REWORDINGS:
        if pattern.fullmatch(text):
            text = replacement
    return f"- [{criterion['state']}] {text}"


def _relative_links(line: str, repo_url: str) -> str:
    for path, relative in MAIN_BRANCH_LINKS:
        line = line.replace(f"]({repo_url}/{path}", f"]({relative}")
    return line


def render(issue: dict) -> str:
    """Return the ticket file text for one issue as `gh issue view --json` prints it."""
    title = parse_title(issue)
    sections = _kept_sections(issue)

    context = CONTEXT.fullmatch(" ".join(sections[CONTEXT_HEADING]))
    summary = f"{title['task']}; {title['theme']}"
    # The ticket drops the summary, so it must add nothing to the title.
    if not context or context["summary"] != summary:
        raise _problem(
            issue,
            f"раздел «{CONTEXT_HEADING}» не имеет вида "
            f"«{summary}. Исходная база: версия. Место изменения: место.»",
        )

    names = sorted(label["name"] for label in issue["labels"])
    labels = [name for prefix in LABEL_PREFIXES for name in names if name.startswith(prefix)]
    fields = (
        ("ID", title["id"]),
        ("Учебная тема", _capitalise(title["theme"])),
        ("Область и тип", ", ".join(labels)),
        ("Место изменения", context["place"]),
        ("Исходная база", context["baseline"]),
        (
            "Целевая версия в трекере владельца",
            issue["milestone"]["title"] if issue["milestone"] else NO_MILESTONE,
        ),
        ("Issue в трекере владельца", f"[#{issue['number']}]({issue['url']})"),
    )
    repo_url = issue["url"].rsplit("/issues/", 1)[0]
    lines = [
        f"# {title['id']}. {title['task']}",
        "",
        "| Поле | Значение |",
        "|---|---|",
        *(f"| {name} | {value} |" for name, value in fields),
        "",
        f"## {CRITERIA_HEADING}",
        "",
        *(_criterion(issue, line) for line in sections[CRITERIA_HEADING]),
        "",
        f"## {SOURCES_HEADING}",
        "",
        *(_relative_links(line, repo_url) for line in sections[SOURCES_HEADING]),
    ]
    return "\n".join(lines) + "\n"


def fetch_issue(number: int, repo: str) -> dict:
    command = ["gh", "issue", "view", str(number), "-R", repo, "--json", ISSUE_FIELDS]
    try:
        result = subprocess.run(command, capture_output=True, encoding="utf-8")
    except FileNotFoundError:
        raise GhError(
            "Не найдена команда gh. Для чтения issues нужен GitHub CLI: https://cli.github.com"
        ) from None
    if result.returncode != 0:
        raise GhError(f"gh не прочитал issue #{number} из {repo}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def _diff(name: str, current: str, fresh: str) -> str:
    lines = difflib.unified_diff(
        current.splitlines(keepends=True),
        fresh.splitlines(keepends=True),
        fromfile=f"{name}, файл",
        tofile=f"{name}, issue",
    )
    return "".join(
        line if line.endswith("\n") else f"{line}\n\\ В конце файла нет новой строки\n"
        for line in lines
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Сверяет файлы тикетов EDU-NN.md с issues владельца или записывает их заново."
    )
    parser.add_argument("--write", action="store_true", help="записать файлы вместо сверки")
    parser.add_argument(
        "--repo", default=DEFAULT_REPO, help="репозиторий с issues (по умолчанию %(default)s)"
    )
    parser.add_argument(
        "--numbers",
        type=int,
        nargs="+",
        default=DEFAULT_NUMBERS,
        metavar="N",
        help="номера issues через пробел (по умолчанию с 1 по 12)",
    )
    args = parser.parse_args(argv)

    try:
        issues = [fetch_issue(number, args.repo) for number in args.numbers]
    except GhError as error:
        print(error, file=sys.stderr)
        return 2

    tickets: dict[str, str] = {}
    problems = []
    for issue in issues:
        try:
            tickets[f"{parse_title(issue)['id']}.md"] = render(issue)
        except TicketError as error:
            problems.append(str(error))
    if problems:
        print(*problems, sep="\n", file=sys.stderr)
        return 2

    if args.write:
        for name, text in tickets.items():
            with (TICKETS_DIR / name).open("w", encoding="utf-8", newline="\n") as ticket:
                ticket.write(text)
            print(f"{name}: записан")
        return 0

    drift = False
    for name, text in tickets.items():
        path = TICKETS_DIR / name
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == text:
            print(f"{name}: совпадает")
        elif current is None:
            drift = True
            print(f"{name}: нет файла")
        else:
            drift = True
            print(f"{name}: расходится")
            sys.stdout.write(_diff(name, current, text))
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
