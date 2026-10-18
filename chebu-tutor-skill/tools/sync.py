from __future__ import annotations

import json
import os
import posixpath
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
SKILL_JSON = ROOT / "chebu-tutor-skill" / "skill.json"
SOURCE_DIR = ROOT / "chebu-tutor-skill" / "source"
SKILL_FILE = "SKILL.md"

# The generator writes only inside skill block paths, so importing handoff.py must not leave .handoff/__pycache__.
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / ".handoff"))
import handoff  # noqa: E402

USAGE = """\
использование: python3 chebu-tutor-skill/tools/sync.py [--check]

  без ключа  записать адаптеры навыка по блокам skill из runtime-config/runtimes/
  --check    сравнить адаптеры с источниками, ничего не записывая; код 1 при расхождении
"""

NOTICE = (
    "Сгенерировано chebu-tutor-skill/tools/sync.py из {source}. "
    "Не правь вручную: измени источник и выполни python3 chebu-tutor-skill/tools/sync.py."
)
COMMENT = {".md": "<!-- {} -->", ".yaml": "# {}"}
BLOCK_KEYS = frozenset({"dir", "link_to"})
PLACEHOLDER = re.compile(r'"\{\{([a-z_]+)\}\}"')
FRONTMATTER = re.compile(r"---\n(.*?\n)---\n", re.DOTALL)
VERSION_LABEL = '  version: "{{version}}"'
CHECK_HINT = "Адаптеры расходятся с источниками. Запиши их: python3 chebu-tutor-skill/tools/sync.py"
BLOCKED_HINT = "Генератор не удаляет папки и файлы и не пишет через ссылки. Убери эти пути вручную и запусти sync.py снова."


class SyncError(Exception):
    pass


@dataclass(frozen=True)
class File:
    text: str


@dataclass(frozen=True)
class Link:
    # The symlink text is relative to the link's own directory (D-12), so a clone at another path still works.
    target: str


@dataclass(frozen=True)
class Folder:
    # The relative paths the generator writes in an adapter folder; any other file there is drift it will not delete.
    files: frozenset[str]


Entry = File | Link | Folder


@dataclass(frozen=True)
class Drift:
    # A blocked path needs a person: the generator never removes a file or a folder and never writes through a link.
    path: str
    reason: str
    blocked: bool = False

    def __str__(self) -> str:
        return f"{self.path}: {self.reason}"


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args not in ([], ["--check"]):
        print(f"ошибка: неверные аргументы.\n\n{USAGE}", file=sys.stderr, end="")
        return 2
    try:
        plan = desired()
    except (SyncError, handoff.HandoffError) as error:
        print(f"ошибка: {error}", file=sys.stderr)
        return 1
    found = drift(plan)
    if not found:
        print(summary(plan))
        return 0
    if args:
        for item in found:
            print(f"ошибка: {item}", file=sys.stderr)
        print(CHECK_HINT, file=sys.stderr)
        return 1
    if blocked := [item for item in found if item.blocked]:
        for item in blocked:
            print(f"ошибка: {item}", file=sys.stderr)
        print(BLOCKED_HINT, file=sys.stderr)
        return 1
    for item in found:
        try:
            place(item.path, plan[item.path])
        except OSError as error:
            print(f"ошибка: {item.path}: {error}", file=sys.stderr)
            return 1
        print(f"записано: {item.path}, было: {item.reason}")
    return 0


def desired() -> dict[str, Entry]:
    skill = read_json(SKILL_JSON)
    name = skill.get("name")
    if not isinstance(name, str):
        raise SyncError(f"{shown(SKILL_JSON)}: нет строкового поля name")
    folder = render_folder(skill)
    plan: dict[str, Entry] = {}
    for directory, target in skill_dirs(name).items():
        if target is None:
            plan[directory] = Folder(frozenset(folder))
            plan |= {f"{directory}/{rel}": File(text) for rel, text in folder.items()}
        else:
            plan[directory] = Link(posixpath.relpath(target, posixpath.dirname(directory)))
    return dict(sorted(plan.items()))


def skill_dirs(name: str) -> dict[str, str | None]:
    # Each distinct adapter directory maps to the folder it links to, or to None when the generator writes it.
    dirs: dict[str, str | None] = {}
    owner: dict[str, str] = {}
    for runtime_id in handoff.load_registry(handoff.RUNTIME_CONFIG_DIR).ids:
        path = handoff.RUNTIME_CONFIG_DIR / "runtimes" / f"{runtime_id}.json"
        block = read_json(path).get("skill")
        if not isinstance(block, dict):
            raise SyncError(f"{shown(path)}: нет блока skill, а manifest.json называет рантайм {runtime_id}")
        if unknown := sorted(set(block) - BLOCK_KEYS):
            raise SyncError(
                f"{shown(path)}: в блоке skill неизвестные поля {', '.join(unknown)}; допустимы dir и link_to"
            )
        directory = repo_path(block.get("dir"), path, "dir")
        target = repo_path(block["link_to"], path, "link_to") if "link_to" in block else None
        if PurePosixPath(directory).name != name:
            raise SyncError(
                f"{shown(path)}: папка skill.dir «{directory}» должна называться {name}, "
                f"как навык в chebu-tutor-skill/skill.json"
            )
        if directory in dirs and dirs[directory] != target:
            raise SyncError(
                f"рантаймы {owner[directory]} и {runtime_id} по-разному описывают {directory} в блоках skill: "
                f"один пишет папку, другой ставит ссылку или ссылается в другое место"
            )
        dirs[directory] = target
        owner.setdefault(directory, runtime_id)
    for directory, target in dirs.items():
        if target is not None and (target not in dirs or dirs[target] is not None):
            config = handoff.RUNTIME_CONFIG_DIR / "runtimes" / f"{owner[directory]}.json"
            raise SyncError(
                f"{shown(config)}: skill.link_to «{target}» не называет папку, "
                f"которую генератор пишет по блоку skill без link_to"
            )
    return dirs


def repo_path(value: object, config: Path, key: str) -> str:
    parts = PurePosixPath(value).parts if isinstance(value, str) else ()
    if not parts or value.startswith("/") or ".." in parts or str(PurePosixPath(value)) != value:
        raise SyncError(
            f"{shown(config)}: skill.{key} «{value}» должен быть путём от корня репозитория без / в начале и без .."
        )
    return value


def render_folder(skill: Mapping[str, object]) -> dict[str, str]:
    sources = sorted(
        path
        for path in SOURCE_DIR.rglob("*")
        if path.is_file() and not any(part.startswith(".") for part in path.relative_to(SOURCE_DIR).parts)
    )
    skill_md = SOURCE_DIR / SKILL_FILE
    if skill_md not in sources:
        raise SyncError(f"нет файла {shown(skill_md)}")
    check_skill(read_text(skill_md), skill)
    return {path.relative_to(SOURCE_DIR).as_posix(): render(path, skill) for path in sources}


def check_skill(text: str, skill: Mapping[str, object]) -> None:
    where = shown(SOURCE_DIR / SKILL_FILE)
    header = FRONTMATTER.match(text)
    if header is None:
        raise SyncError(f"{where}: нет заголовка между строками ---")
    lines = header.group(1).splitlines()
    if f"name: {skill['name']}" not in lines:
        raise SyncError(
            f"{where}: в заголовке нет строки name: {skill['name']}; имя навыка равно имени папки адаптера"
        )
    if VERSION_LABEL not in lines:
        raise SyncError(f'{where}: в заголовке нет метки версии metadata.version "{{{{version}}}}"')
    modes = handoff.read_snapshot(handoff.TEMPLATE_PATH).enumerations.get(handoff.MODE_FIELD)
    if modes is None:
        raise SyncError(f"в {shown(handoff.TEMPLATE_PATH)} нет перечисления «{handoff.MODE_FIELD}»")
    body = text[header.end() :]
    if missing := [f"--{mode}" for mode in modes if f"`--{mode}`" not in body]:
        raise SyncError(
            f"{where} не называет флаги {', '.join(missing)} из перечисления "
            f"«{handoff.MODE_FIELD}» в {shown(handoff.TEMPLATE_PATH)}"
        )
    usage = handoff.skill_usage(modes)
    if usage not in body.splitlines():
        raise SyncError(f"в {where} нет строки использования, которую печатает handoff.py: {usage}")


def render(path: Path, skill: Mapping[str, object]) -> str:
    where = shown(path)

    def value(found: re.Match[str]) -> str:
        field = found.group(1)
        if not isinstance(skill.get(field), str):
            raise SyncError(f'{where}: плейсхолдер "{{{{{field}}}}}" не называет строковое поле chebu-tutor-skill/skill.json')
        # A JSON string is a valid YAML double-quoted scalar, so any description stays valid frontmatter.
        return json.dumps(skill[field], ensure_ascii=False)

    text = PLACEHOLDER.sub(value, read_text(path))
    if "{{" in text:
        raise SyncError(f'{where}: плейсхолдер без кавычек; пиши "{{{{поле}}}}"')
    comment = COMMENT.get(path.suffix)
    if comment is None:
        raise SyncError(
            f"{where}: генератор не знает, как пометить файл {path.suffix or 'без расширения'}; "
            f"в source/ допустимы .md и .yaml"
        )
    notice = comment.format(NOTICE.format(source=where)) + "\n"
    header = FRONTMATTER.match(text) if path.suffix == ".md" else None
    cut = header.end() if header else 0
    return text[:cut] + notice + text[cut:]


def drift(plan: Mapping[str, Entry]) -> list[Drift]:
    return [found for path, entry in plan.items() if (found := compare(path, entry))]


def compare(path: str, entry: Entry) -> Drift | None:
    target = ROOT / path
    if target.parent.resolve() != target.parent:
        return Drift(path, "путь проходит через символическую ссылку", blocked=True)
    match entry:
        case Folder(files):
            return compare_folder(path, target, files)
        case Link(text):
            if target.is_symlink():
                actual = os.readlink(target)
                return None if actual == text else Drift(path, f"ссылка ведёт в {actual}, нужна {text}")
            if target.is_dir():
                return Drift(path, f"обычная папка вместо ссылки на {text}", blocked=True)
            if target.exists():
                return Drift(
                    path,
                    f"файл вместо ссылки на {text}; если Git хранит ссылки как текстовые файлы, включи core.symlinks",
                    blocked=True,
                )
            return Drift(path, f"нет ссылки на {text}")
        case File(text):
            if target.is_symlink():
                return Drift(path, "ссылка вместо файла")
            if target.is_dir():
                return Drift(path, "папка вместо файла", blocked=True)
            if not target.exists():
                return Drift(path, "нет файла")
            return None if target.read_bytes() == text.encode("utf-8") else Drift(path, "файл отличается от источника")


def compare_folder(path: str, target: Path, files: frozenset[str]) -> Drift | None:
    if target.is_symlink():
        return Drift(path, "ссылка вместо папки адаптера", blocked=True)
    if not target.exists():
        return None
    if not target.is_dir():
        return Drift(path, "файл вместо папки адаптера", blocked=True)
    extra = []
    for folder, dirs, names in os.walk(target):
        # render_folder skips dot paths in source/ and macOS drops .DS_Store, so dot paths are not drift.
        dirs[:] = [name for name in dirs if not name.startswith(".")]
        found = [name for name in names if not name.startswith(".")]
        found += [name for name in dirs if (Path(folder) / name).is_symlink()]
        extra += [rel for name in found if (rel := (Path(folder) / name).relative_to(target).as_posix()) not in files]
    if not extra:
        return None
    return Drift(path, f"лишние файлы, которых нет в {shown(SOURCE_DIR)}/: {', '.join(sorted(extra))}", blocked=True)


def place(path: str, entry: Entry) -> None:
    # No temp files: a crash leaves drift that the next run repairs.
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        target.unlink()
    match entry:
        case File(text):
            target.write_bytes(text.encode("utf-8"))
        case Link(text):
            os.symlink(text, target)


def summary(plan: Mapping[str, Entry]) -> str:
    files = sum(isinstance(entry, File) for entry in plan.values())
    links = sum(isinstance(entry, Link) for entry in plan.values())
    return f"Адаптеры совпадают с источниками: файлов {files}, ссылок {links}."


def read_json(path: Path) -> dict[str, object]:
    try:
        data = json.loads(read_text(path))
    except ValueError as error:
        raise SyncError(f"не удалось прочитать {shown(path)}: {type(error).__name__}: {error}") from error
    if not isinstance(data, dict):
        raise SyncError(f"{shown(path)}: ожидался объект JSON")
    return data


def read_text(path: Path) -> str:
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise SyncError(f"не удалось прочитать {shown(path)}: {type(error).__name__}: {error}") from error


def shown(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


if __name__ == "__main__":
    # Agents read this output through pipes, where the locale encoding is not always UTF-8.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
