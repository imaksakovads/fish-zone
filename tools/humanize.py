#!/usr/bin/env python3
"""Компактный CLI-гуманизатор для Fish Zone (без веб-сервера).

Вызывает RobustHumanizer напрямую (DeepSeek/Gemini fallback) и выводит
очеловеченный текст. Ключи читаются из ../.env (DEEPSEEK_API_KEY,
GEMINI_API_KEY).

Использование:
    python3 humanize.py "текст или промпт"            # вывод в stdout
    python3 humanize.py --file raw.md --out clean.md  # файл → файл
    cat raw.md | python3 humanize.py -                # из stdin
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Загружаем ключи из .env (верхний уровень проекта)
ENV_PATH = ROOT.parent / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())
# fallback: .env рядом с инструментами
ENV2 = ROOT / ".env"
if ENV2.exists():
    for line in ENV2.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(ROOT))
from models import DEFAULT_PROVIDERS, HumanizeRequest  # noqa: E402
from robust_humanizer import RobustHumanizer  # noqa: E402


async def run(text: str, max_tokens: int = 4096) -> str:
    req = HumanizeRequest(content=text, max_tokens=max_tokens)
    humanizer = RobustHumanizer(providers=DEFAULT_PROVIDERS)
    fragments: list[str] = []
    try:
        async for event_json in humanizer.humanize_stream(req):
            try:
                data = json.loads(event_json)
                if data.get("type") == "fragment":
                    fragments.append(data.get("text", ""))
                elif data.get("type") == "error":
                    sys.stderr.write(f"[ошибка] {data.get('text','')}\n")
            except json.JSONDecodeError:
                pass
    finally:
        await humanizer.close()
    return "".join(fragments)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fish Zone humanizer")
    parser.add_argument("text", nargs="?", help="текст или '-' для stdin")
    parser.add_argument("--file", help="входной файл")
    parser.add_argument("--out", help="выходной файл (иначе stdout)")
    parser.add_argument("--max-tokens", type=int, default=4096)
    args = parser.parse_args()

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.text == "-":
        text = sys.stdin.read()
    elif args.text:
        text = args.text
    else:
        parser.print_help()
        return 2

    print(f"🔨 Гуманизация ({len(text)} симв)...", file=sys.stderr)
    result = asyncio.run(run(text, max_tokens=args.max_tokens))

    if not result:
        print("❌ Пустой результат (нет ключей или ошибка провайдеров)", file=sys.stderr)
        return 1

    if args.out:
        Path(args.out).write_text(result.strip() + "\n", encoding="utf-8")
        print(f"✅ Записано: {args.out} ({len(result)} симв)", file=sys.stderr)
    else:
        print(result.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
