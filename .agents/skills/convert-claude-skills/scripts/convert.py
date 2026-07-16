#!/usr/bin/env python3
"""Synchronize project-local Claude Code skills into Codex's .agents/skills."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path


TEXT_EXTENSIONS = {
    ".md", ".txt", ".yaml", ".yml", ".json", ".toml", ".py", ".js",
    ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".bash", ".zsh",
    ".html", ".css", ".scss", ".xml", ".csv", ".tsv",
}
REPLACEMENTS = (
    ("~/.claude/skills/", "~/.codex/skills/"),
    (".claude/skills/", ".agents/skills/"),
    ("CLAUDE.md", "AGENTS.md"),
    ("Claude Code", "Codex"),
    ("Claude", "Codex"),
)
RESERVED_SKILLS = {"convert-claude-skills"}


def find_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".claude" / "skills").is_dir():
            return candidate
    raise FileNotFoundError("找不到 .claude/skills；請在專案內執行。")


def is_text(path: Path) -> bool:
    if path.name in {"SKILL.md", "AGENTS.md", "CLAUDE.md"}:
        return True
    return path.suffix.lower() in TEXT_EXTENSIONS


def convert_text(value: str) -> str:
    for old, new in REPLACEMENTS:
        value = value.replace(old, new)
    if value.startswith("---\n"):
        match = re.match(r"^(---\n)(.*?)(\n---)", value, re.DOTALL)
        if match:
            frontmatter = match.group(2)
            lines = []
            for line in frontmatter.splitlines():
                if line.startswith("description:"):
                    line = line.replace("<", "[").replace(">", "]")
                lines.append(line)
            value = match.group(1) + "\n".join(lines) + match.group(3) + value[match.end():]
    return value


def sync_skill(source: Path, target: Path) -> tuple[int, int]:
    text_count = binary_count = 0
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        output = target / relative
        if item.is_dir():
            output.mkdir(parents=True, exist_ok=True)
        elif is_text(item):
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(convert_text(item.read_text(encoding="utf-8")), encoding="utf-8")
            shutil.copymode(item, output)
            text_count += 1
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, output)
            binary_count += 1
    return text_count, binary_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="檢查是否同步，不寫入檔案")
    parser.add_argument("--root", type=Path, help="專案根目錄；預設自動尋找")
    args = parser.parse_args()

    try:
        root = args.root.resolve() if args.root else find_root(Path.cwd().resolve())
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    source_root = root / ".claude" / "skills"
    target_root = root / ".agents" / "skills"
    sources = sorted(path for path in source_root.iterdir() if path.is_dir())
    errors = 0
    changed = 0

    for source in sources:
        if source.name in RESERVED_SKILLS:
            print(f"SKIP  {source.name}: 保留給 Codex 轉換器")
            continue
        if not (source / "SKILL.md").is_file():
            print(f"ERROR {source.name}: 缺少 SKILL.md", file=sys.stderr)
            errors += 1
            continue
        target = target_root / source.name
        if args.check:
            expected = {p.relative_to(source): p for p in source.rglob("*") if p.is_file()}
            mismatch = not target.is_dir()
            for relative, item in expected.items():
                output = target / relative
                if not output.is_file():
                    mismatch = True
                    break
                if is_text(item):
                    mismatch |= output.read_text(encoding="utf-8") != convert_text(item.read_text(encoding="utf-8"))
                else:
                    mismatch |= output.read_bytes() != item.read_bytes()
                if mismatch:
                    break
            print(f"{'STALE' if mismatch else 'OK   '} {source.name}")
            changed += int(mismatch)
        else:
            text_count, binary_count = sync_skill(source, target)
            print(f"SYNC  {source.name}: {text_count} 個文字檔、{binary_count} 個其他檔案")
            changed += 1

    if errors:
        print(f"完成，但有 {errors} 個錯誤。", file=sys.stderr)
        return 1
    if args.check and changed:
        print(f"有 {changed} 個 skill 尚未同步。")
        return 1
    print(f"完成：{len(sources)} 個 Claude skill 已檢查{'並同步' if not args.check else ''}。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
