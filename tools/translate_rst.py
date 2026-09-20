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

MIN_REQUEST_INTERVAL = 0.25
RETRY_DELAYS = (2, 4, 8, 16, 32)

SKIP_EXTENSIONS = {".py", ".js", ".css", ".scss", ".json", ".yaml", ".yml", ".toml", ".xml"}
SKIP_LINE = re.compile(
    r"^\s*(\.\.|\|\s|\+[-=+]|\$ |>>> |#include\b|https?://|\.{3}\s+|:[\w-]+:|``[^`]+``\s*$)"
)
DIRECTIVE = re.compile(r"^\s*\.\.\s+[\w-]+::")
ROLE_OR_REF = re.compile(r"^\s*\.\.\s+_[^:]+:\s*$|^\s*\.\.\s+\|[^|]+\|\s+replace::")
HEADING = re.compile(r"^\s*[=\-`:." + "'\"~^_*+#<>" + r"]{3,}\s*$")


def key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TranslationError(RuntimeError):
    """Raised when a sentence cannot be translated safely."""


class ThrottledTranslator:
    def __init__(self) -> None:
        self.client = GoogleTranslator(source="en", target="zh-CN")
        self.last_request_at = 0.0

    def translate(self, text: str) -> str:
        for attempt, delay in enumerate((0, *RETRY_DELAYS)):
            if delay:
                time.sleep(delay)
            elapsed = time.monotonic() - self.last_request_at
            if elapsed < MIN_REQUEST_INTERVAL:
                time.sleep(MIN_REQUEST_INTERVAL - elapsed)
            try:
                value = self.client.translate(text)
                self.last_request_at = time.monotonic()
                return value
            except Exception as exc:
                self.last_request_at = time.monotonic()
                message = str(exc).lower()
                rate_limited = "too many requests" in message or "429" in message
                if not rate_limited or attempt == len(RETRY_DELAYS):
                    raise TranslationError(f"translation failed after retries: {exc}") from exc
                print(f"warning: Google rate limit; retry {attempt + 1}/{len(RETRY_DELAYS)}")
        raise AssertionError("unreachable")


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
    translator = ThrottledTranslator()
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
        pending: list[tuple[int, str, str, str]] = []

        def flush_pending() -> None:
            nonlocal translated, failed
            if not pending:
                return
            missing = [(i, text, digest, prefix) for i, text, digest, prefix in pending if digest not in cache]
            for _, text, digest, _ in missing:
                try:
                    cache[digest] = translator.translate(text)
                    translated += 1
                except TranslationError as exc:
                    failed += 1
                    raise TranslationError(f"{path}: {exc}") from exc
            translated_by_index = {i: cache.get(digest, text) for i, text, digest, _ in pending}
            for i, text, digest, prefix in pending:
                newline = "\n" if lines[i].endswith("\n") else ""
                output.append(prefix + translated_by_index[i] + newline)
            pending.clear()

        for index, line in enumerate(lines):
            indent = len(line) - len(line.lstrip(" "))
            if literal and line.strip() and indent <= literal_indent:
                literal = False
            if DIRECTIVE.match(line) and any(x in line for x in ("code-block", "code::", "parsed-literal", "literal::")):
                literal = True
                literal_indent = indent
            if should_skip(line, literal) or len(line.strip()) < 3:
                flush_pending()
                output.append(line)
                continue
            body = line.rstrip("\r\n")
            digest = key(body)
            prefix = body[: len(body) - len(body.lstrip())]
            pending.append((index, body.strip(), digest, prefix))
            if len(pending) >= 50:
                flush_pending()
                cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        flush_pending()
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
