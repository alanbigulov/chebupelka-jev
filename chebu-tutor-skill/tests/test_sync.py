from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
PROJECT = SKILL.parent
FOLDER = ".claude/skills/chebu-tutor"
LINK = ".agents/skills/chebu-tutor"
LINK_TEXT = "../../.claude/skills/chebu-tutor"
MODE_ROW = re.compile(r"^(\| Режим тьютора \| `<)([a-z / ]+)(>` \|)$", re.MULTILINE)
COPIED_FILES = (
    ".handoff/handoff.py",
    ".handoff/TEMPLATE.md",
    "chebu-tutor-skill/skill.json",
    "chebu-tutor-skill/tools/sync.py",
)
COPIED_DIRS = ("runtime-config", "chebu-tutor-skill/source")


def problems(result: subprocess.CompletedProcess[str]) -> list[str]:
    return [line for line in result.stderr.splitlines() if line.startswith("ошибка:")]


def header_lines(text: str) -> list[str]:
    return text.split("---\n")[1].splitlines()


def files_under(base: Path) -> list[str]:
    return sorted(path.relative_to(base).as_posix() for path in base.rglob("*") if path.is_file())


def remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        shutil.rmtree(path)


class SyncCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.repo = self.root / "repo"
        for rel in COPIED_FILES:
            (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(PROJECT / rel, self.repo / rel)
        for rel in COPIED_DIRS:
            shutil.copytree(PROJECT / rel, self.repo / rel)

    def run_sync(self, *args: str) -> subprocess.CompletedProcess[str]:
        # cwd sits outside the copy, so a write relative to cwd lands where the tree walk sees it as foreign.
        return subprocess.run(
            [sys.executable, str(self.repo / "chebu-tutor-skill" / "tools" / "sync.py"), *args],
            cwd=self.root,
            capture_output=True,
            encoding="utf-8",
        )

    def generate(self) -> None:
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_in_sync()

    def assert_in_sync(self) -> None:
        result = self.run_sync("--check")
        self.assertEqual((result.returncode, problems(result)), (0, []), result.stderr)

    def assert_check_names(self, path: str) -> list[str]:
        result = self.run_sync("--check")
        self.assertEqual(result.returncode, 1, result.stdout)
        found = problems(result)
        self.assertTrue(any(path in line for line in found), found)
        return found

    def edit_json(self, rel: str, change: Callable[[dict], None]) -> None:
        path = self.repo / rel
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def skill_blocks(self) -> dict[str, dict]:
        config = self.repo / "runtime-config"
        ids = json.loads((config / "manifest.json").read_text(encoding="utf-8"))["runtimes"]
        return {
            rid: json.loads((config / "runtimes" / f"{rid}.json").read_text(encoding="utf-8"))["skill"] for rid in ids
        }

    def entries(self) -> dict[str, tuple[str, bytes | str, int]]:
        found = {}
        for folder, dirs, files in os.walk(self.root):
            for name in dirs + files:
                path = Path(folder) / name
                rel = path.relative_to(self.root).as_posix()
                if path.is_symlink():
                    found[rel] = ("link", os.readlink(path), path.lstat().st_mtime_ns)
                elif path.is_file():
                    found[rel] = ("file", path.read_bytes(), path.lstat().st_mtime_ns)
        return found


class SyncTest(SyncCase):
    def test_writes_one_folder_mirroring_source_and_the_codex_link(self) -> None:
        # Defect: the Codex path is a copy or an absolute link, openai.yaml is missing, the notice is not the first body line, or the body differs from the source beyond the D-17 substitutions.
        self.generate()
        link = self.repo / LINK
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), LINK_TEXT)
        source = SKILL / "source"
        self.assertEqual(files_under(self.repo / FOLDER), files_under(source))
        skill = json.loads((SKILL / "skill.json").read_text(encoding="utf-8"))
        self.assertEqual(self.repo.joinpath(FOLDER).name, skill["name"])
        adapter = (self.repo / FOLDER / "SKILL.md").read_text(encoding="utf-8")
        expected = (
            (source / "SKILL.md")
            .read_text(encoding="utf-8")
            .replace('"{{version}}"', f'"{skill["version"]}"')
            .replace('"{{description}}"', json.dumps(skill["description"], ensure_ascii=False))
        )
        parts = re.match(r"(---\n.*?\n---\n)(.*?\n)(.*)", adapter, re.DOTALL)
        self.assertIsNotNone(parts, adapter)
        head, notice, body = parts.groups()
        self.assertIn(f"name: {skill['name']}", head.splitlines())
        self.assertTrue(notice.startswith("<!-- Сгенерировано"), notice)
        self.assertIn("chebu-tutor-skill/source/SKILL.md", notice)
        self.assertEqual(head + body, expected)
        openai = (self.repo / FOLDER / "agents" / "openai.yaml").read_text(encoding="utf-8").splitlines()
        self.assertTrue(openai[0].startswith("# Сгенерировано"), openai[0])
        self.assertEqual(openai[1:], ["policy:", "  allow_implicit_invocation: false"])
        self.assertEqual((link / "SKILL.md").read_bytes(), (self.repo / FOLDER / "SKILL.md").read_bytes())

    def test_check_names_a_hand_edited_adapter_file(self) -> None:
        # Defect: --check passes after a one-byte hand edit, compares only SKILL.md, or reports drift without naming the file.
        for rel in ("SKILL.md", "agents/openai.yaml"):
            with self.subTest(rel):
                self.generate()
                path = self.repo / FOLDER / rel
                data = bytearray(path.read_bytes())
                data[-1:] = b" "
                path.write_bytes(data)
                found = self.assert_check_names(f"{FOLDER}/{rel}")
                self.assertEqual(len(found), 1, found)

    def test_check_fails_after_a_version_change_without_regeneration(self) -> None:
        # Defect: the generator skips the version label, or --check ignores skill.json and passes after a bump.
        self.generate()
        version = json.loads((self.repo / "chebu-tutor-skill" / "skill.json").read_text(encoding="utf-8"))["version"]
        adapter = self.repo / FOLDER / "SKILL.md"
        self.assertIn(f'  version: "{version}"', header_lines(adapter.read_text(encoding="utf-8")))
        self.edit_json("chebu-tutor-skill/skill.json", lambda skill: skill.update(version="0.2.0"))
        self.assert_check_names(f"{FOLDER}/SKILL.md")
        self.generate()
        self.assertIn('  version: "0.2.0"', header_lines(adapter.read_text(encoding="utf-8")))

    def test_check_fails_for_a_manifest_runtime_without_skill_block(self) -> None:
        # Defect: the generator walks the blocks it finds instead of the manifest ids, so a runtime without an adapter passes --check.
        self.generate()
        runtimes = self.repo / "runtime-config" / "runtimes"
        claude = json.loads((runtimes / "claude.json").read_text(encoding="utf-8"))
        claude["id"] = "newrt"
        del claude["skill"]
        (runtimes / "newrt.json").write_text(json.dumps(claude, ensure_ascii=False), encoding="utf-8")
        self.edit_json("runtime-config/manifest.json", lambda manifest: manifest["runtimes"].append("newrt"))
        result = self.run_sync("--check")
        self.assertEqual(result.returncode, 1, result.stdout)
        found = problems(result)
        self.assertEqual(len(found), 1, found)
        self.assertIn("newrt", found[0])
        self.assertIn("skill", found[0])

    def test_second_run_changes_nothing(self) -> None:
        # Defect: the second run rewrites a file, stacks a second notice, recreates the link, or dies on the existing link.
        self.generate()
        before = self.entries()
        result = self.run_sync()
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual([line for line in result.stdout.splitlines() if line.startswith("записано:")], [])
        self.assertIn("файлов 2, ссылок 1", result.stdout)
        self.assertEqual(self.entries(), before)

    def test_writes_only_inside_skill_block_paths(self) -> None:
        # Defect: the generator writes outside the skill block paths: another runtime directory, .handoff/__pycache__, or a path relative to cwd.
        before = self.entries()
        blocks = self.skill_blocks().values()
        folders = {f"repo/{block['dir']}/" for block in blocks if "link_to" not in block}
        links = {f"repo/{block['dir']}" for block in blocks if "link_to" in block}
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        after = self.entries()
        changed = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
        self.assertTrue(links <= changed)
        foreign = {path for path in changed if path not in links and not any(path.startswith(f) for f in folders)}
        self.assertEqual(foreign, set())

    def test_write_follows_moved_block_paths(self) -> None:
        # Defect: the generator hardcodes an adapter path instead of reading the skill blocks.
        for rid, block in self.skill_blocks().items():
            moved = {"dir": "y/chebu-tutor", "link_to": "x/chebu-tutor"} if "link_to" in block else {"dir": "x/chebu-tutor"}
            self.edit_json(f"runtime-config/runtimes/{rid}.json", lambda runtime: runtime.update(skill=moved))
        before = self.entries()
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        after = self.entries()
        changed = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
        self.assertEqual(
            changed,
            {"repo/x/chebu-tutor/SKILL.md", "repo/x/chebu-tutor/agents/openai.yaml", "repo/y/chebu-tutor"},
        )
        self.assertEqual(after["repo/y/chebu-tutor"][:2], ("link", "../x/chebu-tutor"))

    def test_check_does_not_write(self) -> None:
        # Defect: --check repairs the drift it reports, or creates the adapter folders.
        before = self.entries()
        result = self.run_sync("--check")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(self.entries(), before)
        self.assertFalse((self.repo / ".claude").exists())
        self.assertFalse((self.repo / ".agents").exists())

    def test_refuses_a_skill_dir_that_leaves_the_tree(self) -> None:
        # Defect: the generator trusts skill.dir and writes outside the tree or into a folder that is not named after the skill.
        absolute = str(self.root / "abs" / "chebu-tutor")
        for bad in ("../outside/chebu-tutor", absolute, "/" + absolute, ".claude/skills/other"):
            with self.subTest(bad):
                self.edit_json("runtime-config/runtimes/claude.json", lambda runtime: runtime["skill"].update(dir=bad))
                before = self.entries()
                result = self.run_sync()
                self.assertEqual(result.returncode, 1, result.stdout)
                found = problems(result)
                self.assertEqual(len(found), 1, found)
                self.assertIn("runtime-config/runtimes/claude.json", found[0])
                self.assertIn("skill.dir", found[0])
                self.assertEqual(self.entries(), before)

    def test_check_fails_when_the_codex_path_is_a_folder_or_another_link(self) -> None:
        # Defect: --check accepts a copied folder or a file at the Codex path, follows the link and compares contents, or accepts an absolute link to the same folder.
        cases: dict[str, Callable[[Path], object]] = {
            "copy": lambda path: (path.unlink(), shutil.copytree(self.repo / FOLDER, path)),
            "file": lambda path: (path.unlink(), path.write_text("не ссылка", encoding="utf-8")),
            "elsewhere": lambda path: (path.unlink(), os.symlink("../../elsewhere/chebu-tutor", path)),
            "absolute": lambda path: (path.unlink(), os.symlink(self.repo / FOLDER, path)),
        }
        for name, breaks in cases.items():
            with self.subTest(name):
                self.generate()
                breaks(self.repo / LINK)
                found = self.assert_check_names(LINK)
                self.assertEqual(len(found), 1, found)
                if name == "file":
                    self.assertIn("core.symlinks", found[0])
                remove(self.repo / LINK)

    def test_write_refuses_to_replace_a_real_folder_or_file(self) -> None:
        # Defect: the write run deletes a folder or a file somebody put at the Codex path, repairs other drift before refusing, or dies with a traceback.
        obstacles: dict[str, Callable[[Path], object]] = {
            "folder": lambda path: shutil.copytree(self.repo / FOLDER, path),
            "file": lambda path: path.write_text("не ссылка", encoding="utf-8"),
        }
        for name, put in obstacles.items():
            with self.subTest(name):
                self.generate()
                (self.repo / LINK).unlink()
                put(self.repo / LINK)
                adapter = self.repo / FOLDER / "SKILL.md"
                adapter.write_bytes(adapter.read_bytes() + b"x")
                before = self.entries()
                result = self.run_sync()
                self.assertEqual(result.returncode, 1, result.stdout)
                found = problems(result)
                self.assertTrue(any(LINK in line for line in found), found)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual([line for line in result.stdout.splitlines() if line.startswith("записано:")], [])
                self.assertEqual(self.entries(), before)
                remove(self.repo / LINK)

    def test_check_fails_when_the_mode_enumeration_changes(self) -> None:
        # Defect: the generator keeps its own mode list or never reads TEMPLATE.md, so an added or removed mode passes --check.
        template = self.repo / ".handoff" / "TEMPLATE.md"
        text = template.read_text(encoding="utf-8")
        cases = (
            ("added", "execute / guide / walkthrough / sandbox / quiz / pair", "--pair"),
            ("removed", "execute / guide / walkthrough / sandbox", "нет строки использования"),
        )
        for name, modes, needle in cases:
            with self.subTest(name):
                self.generate()
                template.write_text(MODE_ROW.sub(lambda m: m.group(1) + modes + m.group(3), text), encoding="utf-8")
                result = self.run_sync("--check")
                self.assertEqual(result.returncode, 1, result.stdout)
                found = problems(result)
                self.assertEqual(len(found), 1, found)
                self.assertIn(needle, found[0])
                self.assertIn("source/SKILL.md", found[0])
                template.write_text(text, encoding="utf-8")

    def test_check_and_write_refuse_a_hand_added_file_in_the_adapter_folder(self) -> None:
        # Defect: --check passes when the generated folder holds a file that source/ does not produce, or the write run deletes it.
        self.generate()
        notes = self.repo / FOLDER / "notes.md"
        notes.write_text("заметка ученика\n", encoding="utf-8")
        found = self.assert_check_names("notes.md")
        self.assertEqual(len(found), 1, found)
        before = self.entries()
        result = self.run_sync()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertTrue(any("notes.md" in line for line in problems(result)), result.stderr)
        self.assertTrue(notes.is_file())
        self.assertEqual(self.entries(), before)

    def test_check_names_an_adapter_file_whose_source_was_deleted(self) -> None:
        # Defect: --check ignores an adapter file that no source file produces any more.
        self.generate()
        (self.repo / "chebu-tutor-skill" / "source" / "agents" / "openai.yaml").unlink()
        found = self.assert_check_names("agents/openai.yaml")
        self.assertEqual(len(found), 1, found)

    def test_check_ignores_dot_files_in_the_adapter_folder(self) -> None:
        # Defect: --check fails on the .DS_Store that macOS drops into the adapter folder.
        self.generate()
        (self.repo / FOLDER / ".DS_Store").write_bytes(b"\x00")
        (self.repo / FOLDER / "agents" / ".DS_Store").write_bytes(b"\x00")
        (self.repo / FOLDER / ".cache").mkdir()
        (self.repo / FOLDER / ".cache" / "index").write_bytes(b"\x00")
        self.assert_in_sync()

    def test_check_names_a_link_in_the_adapter_folder(self) -> None:
        # Defect: --check misses a symlink to a folder inside the generated folder, because the walk does not report links as files.
        self.generate()
        os.symlink(self.root, self.repo / FOLDER / "shortcut")
        found = self.assert_check_names("shortcut")
        self.assertEqual(len(found), 1, found)

    def test_write_refuses_a_link_in_the_adapter_path(self) -> None:
        # Defect: the write run follows a symlink at or above the adapter folder and creates files outside the tree.
        outside = self.root / "outside"
        for name, link in (("folder", f"{FOLDER}"), ("parent", ".claude/skills")):
            with self.subTest(name):
                outside.mkdir()
                (self.repo / link).parent.mkdir(parents=True, exist_ok=True)
                os.symlink(outside, self.repo / link)
                before = self.entries()
                result = self.run_sync()
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertTrue(any(link in line for line in problems(result)), result.stderr)
                self.assertEqual(os.listdir(outside), [])
                self.assertEqual(self.entries(), before)
                remove(self.repo / ".claude")
                remove(outside)

    def test_write_refuses_a_file_in_place_of_the_adapter_folder(self) -> None:
        # Defect: the write run creates the Codex link before it finds a file where the adapter folder belongs, then dies.
        folder = self.repo / FOLDER
        folder.parent.mkdir(parents=True)
        folder.write_text("не папка\n", encoding="utf-8")
        before = self.entries()
        result = self.run_sync()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertTrue(any(line.startswith(f"ошибка: {FOLDER}: ") for line in problems(result)), result.stderr)
        self.assertEqual(self.entries(), before)

    def test_a_link_in_place_of_the_adapter_file_is_replaced_not_followed(self) -> None:
        # Defect: --check accepts a symlink as the adapter file, or the write run writes through it into a file outside the tree.
        self.generate()
        outside = self.root / "outside.md"
        outside.write_text("чужой файл\n", encoding="utf-8")
        adapter = self.repo / FOLDER / "SKILL.md"
        adapter.unlink()
        os.symlink(outside, adapter)
        self.assert_check_names(f"{FOLDER}/SKILL.md")
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(adapter.is_file() and not adapter.is_symlink())
        self.assertEqual(outside.read_text(encoding="utf-8"), "чужой файл\n")
        self.assert_in_sync()

    def test_write_repairs_a_codex_link_that_points_elsewhere(self) -> None:
        # Defect: the write run leaves a link with the wrong target in place, or dies on the existing link.
        self.generate()
        link = self.repo / LINK
        link.unlink()
        os.symlink("../../elsewhere/chebu-tutor", link)
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(os.readlink(link), LINK_TEXT)
        self.assert_in_sync()

    def test_refuses_skill_blocks_that_are_misspelled_or_inconsistent(self) -> None:
        # Defect: the generator accepts a misspelled key, two blocks that disagree about one path, or a link to a folder that no block writes.
        codex = "runtime-config/runtimes/codex.json"
        claude = "runtime-config/runtimes/claude.json"
        cases = (
            ("typo key", codex, {"dir": LINK, "linkto": FOLDER}, (codex, "linkto")),
            ("blocks disagree", claude, {"dir": LINK}, ("claude", "codex", LINK)),
            ("link to an unwritten folder", codex, {"dir": LINK, "link_to": "z/chebu-tutor"}, (codex, "z/chebu-tutor")),
        )
        for name, rel, block, needles in cases:
            with self.subTest(name):
                original = (self.repo / rel).read_text(encoding="utf-8")
                self.edit_json(rel, lambda runtime: runtime.update(skill=block))
                before = self.entries()
                result = self.run_sync()
                self.assertEqual(result.returncode, 1, result.stdout)
                found = problems(result)
                self.assertEqual(len(found), 1, found)
                for needle in needles:
                    self.assertIn(needle, found[0])
                self.assertEqual(self.entries(), before)
                self.assertFalse((self.repo / ".claude").exists() or (self.repo / ".agents").exists())
                (self.repo / rel).write_text(original, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
