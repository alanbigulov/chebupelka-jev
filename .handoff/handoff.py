from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn
from urllib.parse import unquote

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = SCRIPT_DIR / "TEMPLATE.md"
RUNTIME_CONFIG_DIR = SCRIPT_DIR.parent / "runtime-config"

STATE_DIR_NAME = ".handoff"
SESSION_NAME = "SESSION.md"
PREPARED_NAME = "SESSION.next.md"
ARCHIVE_NAME = "archive"

SCHEMA_FIELD = "Схема"
TIME_FIELD = "Время снимка UTC"
RUNTIME_FIELD = "Рантайм"
SENDER_FIELD_PREFIX = "Отправитель"
UNKNOWN_RUNTIME = "unknown"
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
ARCHIVE_STAMP_FORMAT = "%Y%m%dT%H%M%S%fZ"

USAGE = """\
использование: python3 .handoff/handoff.py <команда>

  start [--runtime ID]  брифинг в начале сессии: рантайм, состояние, снимок, архив
  check [ПУТЬ]          проверить снимок по TEMPLATE.md; без пути берётся SESSION.next.md
  save                  проверить SESSION.next.md, убрать прежний SESSION.md в архив и заменить его
"""


class HandoffError(Exception):
    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Runtime:
    id: str
    name: str
    aliases: tuple[str, ...]
    entry_files: tuple[str, ...]
    detect_env: tuple[str, ...]
    start_command: str
    unconfirmed: tuple[str, ...]

    @property
    def config_path(self) -> str:
        return f"{RUNTIME_CONFIG_DIR.name}/runtimes/{self.id}.json"


@dataclass(frozen=True)
class Registry:
    runtimes: tuple[Runtime, ...]
    resume_prompt: str

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(runtime.id for runtime in self.runtimes)

    def find(self, name: str) -> Runtime | None:
        wanted = name.lower()
        for runtime in self.runtimes:
            if wanted in (label.lower() for label in (runtime.id, *runtime.aliases)):
                return runtime
        return None

    def detect(self, environ: Mapping[str, str]) -> list[tuple[Runtime, str]]:
        matches = []
        for runtime in self.runtimes:
            marker = next((name for name in runtime.detect_env if environ.get(name)), None)
            if marker:
                matches.append((runtime, marker))
        return matches

    def id_of_sender(self, sender: str) -> str:
        text = sender.lower()
        for runtime in self.runtimes:
            if any(label.lower() in text for label in (runtime.id, runtime.name, *runtime.aliases)):
                return runtime.id
        return UNKNOWN_RUNTIME


@contextmanager
def reading_config(path: Path) -> Iterator[None]:
    try:
        yield
    except (OSError, ValueError, KeyError) as error:
        raise HandoffError(f"не удалось прочитать {path}: {type(error).__name__}: {error}") from error


def load_runtime(path: Path, runtime_id: str) -> Runtime:
    with reading_config(path):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["id"] != runtime_id:
            raise ValueError(f"поле id равно «{data['id']}», а manifest.json называет «{runtime_id}»")
        return Runtime(
            id=data["id"],
            name=data["name"],
            aliases=tuple(data["aliases"]),
            entry_files=tuple(data["entry_files"]),
            detect_env=tuple(data["detect_env"]),
            start_command=data["commands"]["start"],
            unconfirmed=tuple(data["checked"]["unconfirmed"]),
        )


def load_registry(directory: Path) -> Registry:
    manifest_path = directory / "manifest.json"
    with reading_config(manifest_path):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        runtime_ids, resume_prompt = manifest["runtimes"], manifest["resume_prompt"]
    runtimes = tuple(
        load_runtime(directory / "runtimes" / f"{runtime_id}.json", runtime_id) for runtime_id in runtime_ids
    )
    return Registry(runtimes, resume_prompt)


@dataclass(frozen=True)
class MetaRow:
    value: str
    line: int


FENCES = ("```", "~~~")
CELL_SEPARATOR = re.compile(r"(?<!\\)\|")
TABLE_RULE = re.compile(r":?-+:?")


def outside_fences(lines: Sequence[str]) -> Iterator[tuple[int, str]]:
    fence = None
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        marker = stripped[:3]
        # A line such as ```git status``` is inline code. An opening fence has no fence character after its run.
        if fence is None and marker in FENCES and marker[0] not in stripped.lstrip(marker[0]):
            fence = marker
        elif marker == fence:
            fence = None
        elif fence is None:
            yield number, line


def metadata_table(prose: Sequence[tuple[int, str]], after: int) -> dict[str, MetaRow]:
    table: list[tuple[int, str]] = []
    for number, line in prose:
        if number <= after:
            continue
        if line.lstrip().startswith("|"):
            table.append((number, line.strip()))
        elif table:
            break
    rows: dict[str, MetaRow] = {}
    for number, line in table[1:]:
        cells = CELL_SEPARATOR.split(line.strip("|"), maxsplit=1)
        field = cells[0].strip()
        if not TABLE_RULE.fullmatch(field):
            rows.setdefault(field, MetaRow(cells[1].strip() if len(cells) > 1 else "", number))
    return rows


def unquoted(value: str) -> str:
    return value.replace("`", "").strip()


@dataclass(frozen=True)
class Snapshot:
    lines: tuple[str, ...]
    prose: tuple[tuple[int, str], ...]
    headings: tuple[tuple[int, str], ...]
    metadata: dict[str, MetaRow]

    @classmethod
    def parse(cls, text: str) -> Snapshot:
        lines = tuple(text.splitlines())
        prose = tuple(outside_fences(lines))
        headings = tuple((number, line[3:].strip()) for number, line in prose if line.startswith("## "))
        metadata = metadata_table(prose, headings[0][0]) if headings else {}
        return cls(lines, prose, headings, metadata)

    def value(self, field: str) -> str:
        row = self.metadata.get(field)
        return unquoted(row.value) if row else ""

    @property
    def schema(self) -> int | None:
        match = re.match(r"\d+", self.value(SCHEMA_FIELD))
        return int(match.group()) if match else None

    @property
    def time(self) -> datetime | None:
        try:
            return datetime.strptime(self.value(TIME_FIELD), TIME_FORMAT)
        except ValueError:
            return None

    @property
    def declared_runtime(self) -> str | None:
        if RUNTIME_FIELD not in self.metadata:
            return None
        return self.value(RUNTIME_FIELD).split(";")[0].strip()

    def runtime_id(self, registry: Registry) -> str:
        declared = self.declared_runtime
        if declared is not None:
            return declared or UNKNOWN_RUNTIME
        senders = (row.value for field, row in self.metadata.items() if field.startswith(SENDER_FIELD_PREFIX))
        return registry.id_of_sender(next(senders, ""))


def read_snapshot(path: Path) -> Snapshot:
    if not path.is_file():
        raise HandoffError(f"файл не найден: {path}")
    return Snapshot.parse(path.read_bytes().decode("utf-8", errors="replace"))


GIT_LOCATION_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE")


def git(directory: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    # Git hooks and aliases export these. With GIT_DIR set, Git takes the -C directory for the work tree root.
    env = {name: value for name, value in os.environ.items() if name not in GIT_LOCATION_VARS}
    try:
        return subprocess.run(["git", "-C", str(directory), *args], capture_output=True, env=env)
    except FileNotFoundError as error:
        raise HandoffError("команда git не найдена в PATH") from error


def git_path(directory: Path, *args: str) -> Path:
    result = git(directory, *args)
    if result.returncode != 0:
        raise HandoffError(
            f"git {' '.join(args)} в {directory} завершился с кодом {result.returncode}; нужен Git-репозиторий"
        )
    return directory / os.fsdecode(result.stdout).strip()


@dataclass(frozen=True)
class Layout:
    checkout_root: Path
    main_root: Path

    @property
    def state_dir(self) -> Path:
        return self.main_root / STATE_DIR_NAME

    @property
    def session(self) -> Path:
        return self.state_dir / SESSION_NAME

    @property
    def prepared(self) -> Path:
        # An agent isolated in a linked worktree may be unable to write into the main checkout.
        return self.checkout_root / STATE_DIR_NAME / PREPARED_NAME

    @property
    def archive_dir(self) -> Path:
        return self.state_dir / ARCHIVE_NAME

    @property
    def link_bases(self) -> tuple[Path, ...]:
        return tuple(dict.fromkeys(root / STATE_DIR_NAME for root in (self.main_root, self.checkout_root)))

    @property
    def working_copy(self) -> str:
        if self.checkout_root == self.main_root:
            return "основной клон"
        return f"worktree {os.path.relpath(self.checkout_root, self.main_root)}"

    def archived(self) -> list[Path]:
        return sorted(self.archive_dir.glob("*.md"))


def discover_layout() -> Layout:
    checkout_root = git_path(SCRIPT_DIR, "rev-parse", "--show-toplevel").resolve()
    common_dir = git_path(checkout_root, "rev-parse", "--git-common-dir").resolve()
    main_root = common_dir.parent if common_dir.name == ".git" else checkout_root
    return Layout(checkout_root, main_root)


@dataclass(frozen=True)
class Problem:
    message: str
    line: int | None = None

    def __str__(self) -> str:
        where = f"строка {self.line}: " if self.line else ""
        return f"ошибка: {where}{self.message}"


@dataclass(frozen=True)
class CheckContext:
    snapshot: Snapshot
    template: Snapshot
    registry: Registry
    link_bases: tuple[Path, ...]
    home: str


def check_sections(ctx: CheckContext) -> list[Problem]:
    expected = [title for _, title in ctx.template.headings]
    found = [title for _, title in ctx.snapshot.headings]
    problems = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, expected, found, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        problems += [Problem(f"нет раздела «{title}»") for title in expected[i1:i2] if title not in found]
        for line, title in ctx.snapshot.headings[j1:j2]:
            kind = "раздел стоит не на своём месте или повторяется" if title in expected else "лишний раздел"
            problems.append(Problem(f"{kind}: «{title}»", line))
    return problems


def check_metadata(ctx: CheckContext) -> list[Problem]:
    problems = []
    for field in ctx.template.metadata:
        row = ctx.snapshot.metadata.get(field)
        if row is None:
            problems.append(Problem(f"в таблице метаданных нет поля «{field}»"))
        elif not unquoted(row.value):
            problems.append(Problem(f"поле метаданных «{field}» пустое", row.line))
    return problems


def check_schema(ctx: CheckContext) -> list[Problem]:
    found = ctx.snapshot.schema
    if not ctx.snapshot.value(SCHEMA_FIELD) or found == ctx.template.schema:
        return []
    shown = "не распознана" if found is None else found
    line = ctx.snapshot.metadata[SCHEMA_FIELD].line
    return [Problem(f"схема снимка {shown}, а шаблон задаёт {ctx.template.schema}", line)]


PLACEHOLDER = re.compile(r"<[^<>\n]+>")


def check_placeholders(ctx: CheckContext) -> list[Problem]:
    placeholders = dict.fromkeys(found for line in ctx.template.lines for found in PLACEHOLDER.findall(line))
    return [
        Problem(f"не заполнен placeholder шаблона: {placeholder}", number)
        for number, line in enumerate(ctx.snapshot.lines, start=1)
        for placeholder in placeholders
        if placeholder in line
    ]


def check_runtime(ctx: CheckContext) -> list[Problem]:
    declared = ctx.snapshot.declared_runtime
    if not ctx.snapshot.value(RUNTIME_FIELD) or declared in (*ctx.registry.ids, UNKNOWN_RUNTIME):
        return []
    known = ", ".join((*ctx.registry.ids, UNKNOWN_RUNTIME))
    line = ctx.snapshot.metadata[RUNTIME_FIELD].line
    return [Problem(f"рантайм «{declared}» не входит в реестр; допустимые id: {known}", line)]


def check_time(ctx: CheckContext) -> list[Problem]:
    value = ctx.snapshot.value(TIME_FIELD)
    if not value or ctx.snapshot.time:
        return []
    line = ctx.snapshot.metadata[TIME_FIELD].line
    return [Problem(f"время снимка «{value}» не в формате YYYY-MM-DDTHH:MM:SSZ", line)]


PRIVACY_KINDS = {
    "secret": "секрет",
    "home": "абсолютный домашний путь",
    "email": "адрес электронной почты",
}
SECRET_PATTERNS = (
    r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{20,}",
    r"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{20,}",
    r"(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{20,}",
    r"(?<![A-Za-z0-9])xox[abprs]-[A-Za-z0-9-]{10,}",
    r"(?<![A-Z0-9])AKIA[A-Z0-9]{16}(?![A-Z0-9])",
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----",
    r"[A-Za-z][A-Za-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@",
)
# The lookbehind keeps URL paths such as example.com/home/page/ and relative paths out.
HOME_PATTERNS = (
    r"(?<![\w.~-])/(?:Users|home)/[^/\s]+/",
    r"[A-Za-z]:\\Users\\",
)
EMAIL_PATTERNS = (r"(?<![A-Za-z0-9._%+-])(?!(?i:git|noreply)@)[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}",)


def privacy_scanner(home: str) -> re.Pattern[str]:
    home_patterns = HOME_PATTERNS
    # With a home of "/" (some containers) the pattern would match almost every slash in the snapshot.
    if os.path.isabs(home) and os.path.dirname(home) != home:
        home_patterns += (re.escape(home) + r"(?![\w.-])",)
    groups = {"secret": SECRET_PATTERNS, "home": home_patterns, "email": EMAIL_PATTERNS}
    # One alternation reports each match once, so user:password@host is a secret and not also an email.
    return re.compile("|".join(f"(?P<{kind}>{'|'.join(patterns)})" for kind, patterns in groups.items()))


def masked(value: str) -> str:
    return f"{value[:4]}… (всего символов: {len(value)})"


def check_privacy(ctx: CheckContext) -> list[Problem]:
    scanner = privacy_scanner(ctx.home)
    return [
        Problem(f"{PRIVACY_KINDS[match.lastgroup]}: {masked(match.group())}", number)
        for number, line in enumerate(ctx.snapshot.lines, start=1)
        for match in scanner.finditer(line)
    ]


LINK = re.compile(r"\[[^\]\n]*\]\(\s*<?([^)\s>]+)>?[^)\n]*\)")
INLINE_CODE = re.compile(r"`[^`\n]*`")
URL_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")


def check_links(ctx: CheckContext) -> list[Problem]:
    problems = []
    for number, line in ctx.snapshot.prose:
        for target in LINK.findall(INLINE_CODE.sub("", line)):
            path = unquote(target.split("#", 1)[0])
            if not path or URL_SCHEME.match(target):
                continue
            if not any((base / path).exists() for base in ctx.link_bases):
                problems.append(Problem(f"ссылка ведёт на несуществующий файл: {target}", number))
    return problems


RULES: tuple[Callable[[CheckContext], list[Problem]], ...] = (
    check_sections,
    check_metadata,
    check_schema,
    check_placeholders,
    check_runtime,
    check_time,
    check_privacy,
    check_links,
)


def examine(path: Path, layout: Layout, registry: Registry) -> tuple[Snapshot, list[Problem]]:
    snapshot = read_snapshot(path)
    context = CheckContext(snapshot, read_snapshot(TEMPLATE_PATH), registry, layout.link_bases, os.path.expanduser("~"))
    problems = [problem for rule in RULES for problem in rule(context)]
    return snapshot, sorted(problems, key=lambda problem: problem.line or 0)


def report(problems: Sequence[Problem]) -> None:
    for problem in problems:
        print(problem, file=sys.stderr)


START_WITH_RUNTIME = "python3 .handoff/handoff.py start --runtime <id>"


def resolve_runtime(registry: Registry, requested: str | None, environ: Mapping[str, str]) -> tuple[Runtime, str]:
    known = f"Известные id: {', '.join(registry.ids)}; для рантайма вне реестра: {UNKNOWN_RUNTIME}."
    if requested is not None:
        runtime = registry.find(requested)
        if runtime is None:
            raise HandoffError(f"рантайм «{requested}» не найден в реестре.\n{known}", code=2)
        return runtime, "указан явно"
    matches = registry.detect(environ)
    if len(matches) == 1:
        runtime, marker = matches[0]
        return runtime, f"распознан по переменной {marker}"
    if matches:
        seen = ", ".join(f"{runtime.id} ({marker})" for runtime, marker in matches)
        found = f"подошло несколько рантаймов: {seen}"
    else:
        found = "ни одна переменная окружения из реестра не задана"
    raise HandoffError(f"рантайм не распознан, {found}.\n{known}\nЗапусти ещё раз: {START_WITH_RUNTIME}", code=2)


def runtime_briefing(registry: Registry, requested: str | None, environ: Mapping[str, str]) -> list[str]:
    if requested is not None and requested.lower() == UNKNOWN_RUNTIME:
        return [f"Рантайм: неизвестен ({UNKNOWN_RUNTIME})"]
    runtime, how = resolve_runtime(registry, requested, environ)
    correction = [f"Если это не твой рантайм, повтори: {START_WITH_RUNTIME}"] if requested is None else []
    return [
        f"Рантайм: {runtime.name} ({runtime.id}), {how}",
        *correction,
        f"Конфигурация: {runtime.config_path}",
        f"Входные файлы: {', '.join(runtime.entry_files)}",
        *(f"Не подтверждено: {note}" for note in runtime.unconfirmed),
    ]


def plural(count: int, one: str, few: str, many: str) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return one
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return few
    return many


def state_briefing(layout: Layout, registry: Registry) -> list[str]:
    archived = [path.name for path in layout.archived()]
    if layout.session.is_file():
        snapshot = read_snapshot(layout.session)
        schema = "схема не распознана" if snapshot.schema is None else f"схема {snapshot.schema}"
        taken = f"снят {snapshot.value(TIME_FIELD)}" if snapshot.time else "время не распознано"
        lines = [f"Снимок: {SESSION_NAME}, {schema}, {taken}, рантайм {snapshot.runtime_id(registry)}"]
        reading = "«Возобновление сессии», затем снимок"
    elif archived:
        lines = [f"Снимок: {SESSION_NAME} нет. Последний снимок лежит в архиве."]
        reading = f"«Возобновление сессии», затем {ARCHIVE_NAME}/{archived[-1]}"
    else:
        lines = ["Снимок: нет. Это первая сессия в этом клоне."]
        reading = "«Первая сессия»"
    if layout.prepared.is_file():
        lines.append(
            f"Внимание: в {STATE_DIR_NAME}/ этой рабочей копии лежит {PREPARED_NAME}. Прошлая сессия подготовила снимок "
            "и не сохранила его; прочитай его до начала работы."
        )
    if archived:
        count = f"{len(archived)} {plural(len(archived), 'снимок', 'снимка', 'снимков')}"
        lines.append(f"Архив: {count}, последний {archived[-1]}")
    else:
        lines.append("Архив: пусто")
    lines.append(f"Дальше: прочитай .handoff/README.md, раздел {reading}.")
    return lines


def cmd_start(args: argparse.Namespace) -> int:
    registry = load_registry(RUNTIME_CONFIG_DIR)
    lines = runtime_briefing(registry, args.runtime, os.environ)
    layout = discover_layout()
    lines += [f"Состояние: {layout.state_dir}", f"Рабочая копия: {layout.working_copy}"]
    lines += state_briefing(layout, registry)
    print("\n".join(lines))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    layout = discover_layout()
    path = args.path or layout.prepared
    snapshot, problems = examine(path, layout, load_registry(RUNTIME_CONFIG_DIR))
    if problems:
        report(problems)
        return 1
    print(
        f"Снимок {path.name} прошёл проверку: "
        f"разделов {len(snapshot.headings)}, полей метаданных {len(snapshot.metadata)}."
    )
    return 0


def archive_slug(runtime_id: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", runtime_id.lower()).strip("-") or UNKNOWN_RUNTIME


def archive_previous(layout: Layout, content: bytes, runtime_id: str) -> str:
    archived = layout.archived()
    if archived and archived[-1].read_bytes() == content:
        return f"Прежний снимок уже лежит в архиве, копия не создавалась: {ARCHIVE_NAME}/{archived[-1].name}"
    layout.archive_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime(ARCHIVE_STAMP_FORMAT)
    target = layout.archive_dir / f"{stamp}-{archive_slug(runtime_id)}.md"
    try:
        with target.open("xb") as saved:
            saved.write(content)
    except FileExistsError as error:
        raise HandoffError(f"архив {target.name} уже существует; повтори save, ничего не заменено") from error
    return f"Прежний снимок убран в архив: {ARCHIVE_NAME}/{target.name}"


def install(prepared: Path, session: Path) -> None:
    if prepared.parent == session.parent:
        os.replace(prepared, session)
        return
    # A linked worktree can sit on another filesystem, where os.replace cannot move a file.
    # Staging the copy next to SESSION.md keeps the swap atomic.
    session.parent.mkdir(exist_ok=True)
    staged = session.with_name(f"{SESSION_NAME}.{os.getpid()}.tmp")
    shutil.copyfile(prepared, staged)
    os.replace(staged, session)
    prepared.unlink()


def cmd_save(args: argparse.Namespace) -> int:
    layout = discover_layout()
    registry = load_registry(RUNTIME_CONFIG_DIR)
    if not layout.prepared.is_file():
        raise HandoffError(
            f"нет подготовленного снимка {layout.prepared}. Заполни его по {TEMPLATE_PATH.name} и повтори save."
        )
    prepared, problems = examine(layout.prepared, layout, registry)
    if problems:
        report(problems)
        raise HandoffError(f"снимок не сохранён: {PREPARED_NAME} не прошёл проверку.")
    session_path = f"{STATE_DIR_NAME}/{SESSION_NAME}"
    if git(layout.main_root, "check-ignore", "-q", session_path).returncode != 0:
        raise HandoffError(
            f"снимок не сохранён: Git не игнорирует {session_path}, состояние сессии могло бы попасть в репозиторий. "
            f"Верни правило /{STATE_DIR_NAME}/* в .gitignore и повтори save."
        )
    archive_note = "Прежнего снимка не было."
    if layout.session.is_file():
        content = layout.session.read_bytes()
        previous = Snapshot.parse(content.decode("utf-8", errors="replace"))
        if content == layout.prepared.read_bytes():
            archive_note = "Этот снимок уже сохранён, архив не менялся."
        elif previous.time and prepared.time and prepared.time < previous.time:
            raise HandoffError(
                f"снимок не сохранён: в {SESSION_NAME} уже лежит более новый снимок "
                f"({previous.value(TIME_FIELD)} против {prepared.value(TIME_FIELD)}). "
                f"Сначала прочитай его, перенеси нужное в {PREPARED_NAME}, обнови время снимка и повтори save."
            )
        else:
            archive_note = archive_previous(layout, content, previous.runtime_id(registry))
    install(layout.prepared, layout.session)
    print(f"Снимок сохранён: {layout.session}")
    print(archive_note)
    print("Продолжить в любом рантайме из корня основного клона:")
    for runtime in registry.runtimes:
        print("  " + runtime.start_command.replace("{prompt}", registry.resume_prompt))
    return 0


class RussianUsageParser(argparse.ArgumentParser):
    def format_help(self) -> str:
        return USAGE

    format_usage = format_help

    def error(self, message: str) -> NoReturn:
        self.exit(2, f"ошибка: неверные аргументы.\n\n{USAGE}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = RussianUsageParser()
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start")
    start.add_argument("--runtime")
    start.set_defaults(run=cmd_start)
    check = commands.add_parser("check")
    check.add_argument("path", nargs="?", type=Path)
    check.set_defaults(run=cmd_check)
    commands.add_parser("save").set_defaults(run=cmd_save)
    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except HandoffError as error:
        print(f"ошибка: {error}", file=sys.stderr)
        return error.code


if __name__ == "__main__":
    # Agents read this output through pipes, where the locale encoding is not always UTF-8.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
