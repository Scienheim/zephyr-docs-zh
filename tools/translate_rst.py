#!/usr/bin/env python3
"""Translate prose in a Sphinx source tree while preserving RST structure.

This intentionally skips directives, roles, labels, code, tables, URLs and
indented literal blocks. It is a machine-translation bootstrapper, not a
substitute for technical review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

from deep_translator import GoogleTranslator

SKIP_EXTENSIONS = {".py", ".js", ".css", ".scss", ".json", ".yaml", ".yml", ".toml", ".xml"}
SKIP_LINE = re.compile(
    r"^\s*(\.\.|\|\s|\+[-=+]|\$ |>>> |#include\b|https?://|\.{3}\s+|:[\w-]+:|\*\*?\s+|``[^`]+``\s*$)"
)
DIRECTIVE = re.compile(r"^\s*\.\.\s+[\w-]+::")
ROLE_OR_REF = re.compile(r"^\s*\.\.\s+_[^:]+:\s*$|^\s*\.\.\s+\|[^|]+\|\s+replace::")
HEADING = re.compile(r"^\s*[=\-`:." + "'\"~^_*+#<>" + r"]{3,}\s*$")


def key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def should_skip(line: str, literal: bool) -> bool:
    stripped = line.strip()
    if not stripped or literal or HEADING.fullmatch(stripped):
        return True
    if SKIP_LINE.match(line) or DIRECTIVE.match(line) or ROLE_OR_REF.match(line):
        return True
    if stripped.startswith(("..", "|", "+---", "----")):
        return True
    return False


def translate_tree(root: Path, cache_path: Path) -> tuple[int, int]:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    translator = GoogleTranslator(source="en", target="zh-CN")
    translated = 0
    failed = 0

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".rst", ".md"}:
            continue
        original = path.read_text(encoding="utf-8")
        lines = original.splitlines(keepends=True)
        output: list[str] = []
        literal = False
        literal_indent = 0
        for line in lines:
            indent = len(line) - len(line.lstrip(" "))
            if literal and line.strip() and indent <= literal_indent:
                literal = False
            if DIRECTIVE.match(line) and any(x in line for x in ("code-block", "code::", "parsed-literal", "literal::")):
                literal = True
                literal_indent = indent
            if should_skip(line, literal) or len(line.strip()) < 3:
                output.append(line)
                continue
            body = line.rstrip("\r\n")
            digest = key(body)
            if digest in cache:
                value = cache[digest]
            else:
                try:
                    value = translator.translate(body.strip())
                    cache[digest] = value
                    translated += 1
                    if translated % 25 == 0:
                        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
                    time.sleep(0.15)
                except Exception as exc:  # keep source usable when a quota is hit
                    failed += 1
                    print(f"warning: translation failed for {path}: {exc}")
                    value = body.strip()
            prefix = body[: len(body) - len(body.lstrip())]
            newline = "\n" if line.endswith("\n") else ""
            output.append(prefix + value + newline)
        path.write_text("".join(output), encoding="utf-8")
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    return translated, failed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True, help="Sphinx doc/ directory")
    parser.add_argument("--cache", type=Path, default=Path(".cache/translation.json"))
    args = parser.parse_args()
    translated, failed = translate_tree(args.tree, args.cache)
    print(f"translated={translated} failed={failed}")


if __name__ == "__main__":
    main()
