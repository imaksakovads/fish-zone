#!/usr/bin/env python3
"""critic.py — AI-marker critic for blog articles.

Reads a .md article, analyzes it through Claude API for 6 categories
of AI-generated markers, writes .critic.md with findings.

Usage:
    python3 critic.py --file content/article.md [--iteration 1]

Exit codes:
    0 — all categories PASS (article is clean)
    1 — at least one FAIL (article needs fixes)
    2 — CLI error (wrong args, file not found)
    3 — API error (timeout, auth, network)
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

CRITIC_DIR = Path("/Users/igor/project/fish-zone/.critic")
CONTENT_DIR = Path("/Users/igor/project/fish-zone/content")
# Backend selection: ANTHROPIC_API_KEY → Claude, else DEEPSEEK_API_KEY → DeepSeek
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

if ANTHROPIC_KEY:
    API_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/") + "/v1/messages"
    API_KEY = ANTHROPIC_KEY
    MODEL = os.environ.get("CRITIC_MODEL", "claude-sonnet-4-20250514")
    BACKEND = "anthropic"
elif DEEPSEEK_KEY:
    API_URL = DEEPSEEK_BASE.rstrip("/") + "/chat/completions"
    API_KEY = DEEPSEEK_KEY
    MODEL = os.environ.get("CRITIC_MODEL", "deepseek-v4-pro")
    BACKEND = "openai"
else:
    print("ERROR: Set ANTHROPIC_API_KEY or DEEPSEEK_API_KEY", file=sys.stderr)
    sys.exit(3)

TIMEOUT = 120  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

CATEGORIES = [
    {
        "id": "forbidden_words",
        "label": "Forbidden words",
        "description": (
            "AI-маркеры-слова: furthermore, moreover, delve, utilize, leverage, "
            "tapestry, landscape, robust, comprehensive, 'in today's rapidly evolving world', "
            "'в современном мире', 'в сегодняшних реалиях', 'стоит отметить', "
            "'несомненно важно', 'нельзя не упомянуть'"
        ),
    },
    {
        "id": "pattern_of_three",
        "label": "Pattern of three",
        "description": (
            "AI по умолчанию перечисляет всё группами по 3 (3 причины, 3 преимущества, "
            "3 совета). Должно быть 2, 4 или другое неровное количество."
        ),
    },
    {
        "id": "fractal_summaries",
        "label": "Fractal summaries",
        "description": (
            "Пересказ абзаца в конце того же абзаца его же словами. "
            "Каждый абзац должен развивать мысль, а не повторять её."
        ),
    },
    {
        "id": "symmetrical_paragraphs",
        "label": "Symmetrical paragraphs",
        "description": (
            "3+ абзаца подряд одинаковой длины (+-10 слов). "
            "Человеческий текст неровный: короткий удар, потом длинное развитие."
        ),
    },
    {
        "id": "punctuation_fingerprints",
        "label": "Punctuation fingerprints",
        "description": (
            "AI злоупотребляет em-dash (—) и двоеточиями — они создают ритмическую "
            "зависимость между частями предложения. Замена на точки делает текст "
            "авторитетнее. Допустимо 1-2 em-dash на 1000 знаков."
        ),
    },
    {
        "id": "polite_water",
        "label": "Polite water",
        "description": (
            "Фразы-паразиты: 'в заключение можно сказать', 'подводя итог', "
            "'стоит отметить, что', 'важно понимать, что', 'несомненно, ...', "
            "'нельзя не согласиться', 'хочется добавить', 'вполне очевидно'"
        ),
    },
]

SYSTEM_PROMPT = """You are a strict AI-marker critic for Russian-language beauty blog articles.

Analyze the article text for the 6 categories of AI-generated markers listed below.
For each category, return PASS if clean or FAIL if markers are found.

CRITICAL:
- Language of analysis: Russian (comments, suggestions)
- Be specific: provide exact quotes and line numbers for every FAIL
- Be conservative: if unsure, mark PASS (false negative > false positive)
- Do NOT suggest rewriting — only identify problems
- Output valid JSON only, no markdown fences, no extra text

JSON schema:
{
  "categories": {
    "forbidden_words": {
      "status": "PASS" | "FAIL",
      "findings": [{"quote": "...", "line": <number>, "suggestion": "..."}]
    },
    "pattern_of_three": {
      "status": "PASS" | "FAIL",
      "findings": [{"quote": "...", "line": <number>, "suggestion": "..."}]
    },
    "fractal_summaries": {
      "status": "PASS" | "FAIL",
      "findings": [{"quote": "...", "line": <number>, "suggestion": "..."}]
    },
    "symmetrical_paragraphs": {
      "status": "PASS" | "FAIL",
      "findings": [{"description": "...", "suggestion": "..."}]
    },
    "punctuation_fingerprints": {
      "status": "PASS" | "FAIL",
      "findings": [{"quote": "...", "line": <number>, "suggestion": "..."}]
    },
    "polite_water": {
      "status": "PASS" | "FAIL",
      "findings": [{"quote": "...", "line": <number>, "suggestion": "..."}]
    }
  },
  "summary": "Краткий вывод на русском (1-2 предложения)"
}"""


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments and validate."""
    parser = argparse.ArgumentParser(description="AI-marker critic for blog articles")
    parser.add_argument(
        "--file", "-f",
        required=True,
        help="Path to article .md file (absolute or relative to content/)",
    )
    parser.add_argument(
        "--iteration", "-i",
        type=int,
        default=1,
        help="Current iteration number (for .critic.md header)",
    )
    args = parser.parse_args()

    path = Path(args.file)
    if not path.is_absolute():
        # Strip "content/" prefix if present (CONTENT_DIR already includes it)
        if path.parts and path.parts[0] == "content":
            path = Path(*path.parts[1:])
        path = CONTENT_DIR / path
    args.file = path.resolve()

    if not args.file.exists():
        print(f"ERROR: File not found: {args.file}", file=sys.stderr)
        sys.exit(2)
    if args.file.suffix != ".md":
        print(f"ERROR: Not a .md file: {args.file}", file=sys.stderr)
        sys.exit(2)
    if args.iteration < 1 or args.iteration > 3:
        print(f"ERROR: iteration must be 1-3, got {args.iteration}", file=sys.stderr)
        sys.exit(2)

    return args


def read_article(path: Path) -> str:
    """Read article and strip frontmatter for analysis."""
    text = path.read_text(encoding="utf-8")
    # Strip YAML frontmatter (---...---)
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text.strip()


def _parse_sse(line: str) -> str | None:
    """Parse data from a single SSE line. Returns data content or None."""
    if line.startswith("data:"):
        return line[5:].strip()
    return None


def call_critic(text: str) -> dict:
    """Call AI API (Anthropic or DeepSeek) and return parsed JSON response."""
    if BACKEND == "anthropic":
        return _call_anthropic(text)
    else:
        return _call_openai(text)


def _call_anthropic(text: str) -> dict:
    """Call Claude API (SSE streaming) and return parsed JSON response."""
    payload = {
        "model": MODEL,
        "max_tokens": 8192,
        "temperature": 0,
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": f"Analyze this article for AI markers:\n\n{text}"},
        ],
    }

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                API_URL,
                headers={
                    "x-api-key": API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
                timeout=TIMEOUT,
                stream=True,
            )
            resp.raise_for_status()

            text_parts: list[str] = []
            for raw_line in resp.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                data_str = _parse_sse(raw_line)
                if not data_str:
                    continue
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                if event.get("type") == "content_block_delta":
                    delta = event.get("delta", {})
                    dtype = delta.get("type", "")
                    if dtype in ("text_delta", "input_json_delta"):
                        text_parts.append(delta.get("text", delta.get("partial_json", "")))
                    elif dtype == "thinking_delta":
                        text_parts.append(delta.get("thinking", ""))

            raw_content = "".join(text_parts).strip()
            if not raw_content:
                last_error = "Empty response from API"
                print(f"  WARN: Empty response (attempt {attempt}/{MAX_RETRIES})", file=sys.stderr)
                continue

            return _extract_json(raw_content)

        except requests.Timeout:
            last_error = f"Timeout after {TIMEOUT}s (attempt {attempt}/{MAX_RETRIES})"
            print(f"  WARN: {last_error}", file=sys.stderr)
        except requests.HTTPError as e:
            status = e.response.status_code
            body = e.response.text[:200]
            last_error = f"HTTP {status}: {body}"
            print(f"  WARN: {last_error}", file=sys.stderr)
            if status in (400, 401, 403):
                break
        except (json.JSONDecodeError, KeyError) as e:
            last_error = f"JSON parse error: {e}"
            print(f"  WARN: {last_error}", file=sys.stderr)
            break
        except requests.ConnectionError as e:
            last_error = f"Connection: {e}"
            print(f"  WARN: {last_error}", file=sys.stderr)

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    print(f"ERROR: API call failed: {last_error}", file=sys.stderr)
    sys.exit(3)


def _call_openai(text: str) -> dict:
    """Call DeepSeek/OpenAI-compatible API and return parsed JSON response.

    Используется НЕ-stream запрос: для reasoning-моделей (deepseek-v4) в
    stream-режиме финальный текст уходит в reasoning_content, а content
    остаётся пустым. В не-stream ответе message.content приходит гарантированно.
    """
    payload = {
        "model": MODEL,
        "max_tokens": 8192,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this article for AI markers:\n\n{text}"},
        ],
        "stream": False,
    }

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "content-type": "application/json",
                },
                json=payload,
                timeout=TIMEOUT,
            )
            resp.raise_for_status()

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                last_error = "No choices in response"
                print(f"  WARN: {last_error} (attempt {attempt}/{MAX_RETRIES})", file=sys.stderr)
                continue
            message = choices[0].get("message", {})
            raw_content = (message.get("content") or "").strip()

            # Fallback для reasoning-моделей: content может быть пустым,
            # но текст лежит в reasoning_details
            if not raw_content:
                reasoning_parts = []
                for rd in message.get("reasoning_details", []) or []:
                    t = rd.get("text", "")
                    if t:
                        reasoning_parts.append(t)
                raw_content = "".join(reasoning_parts).strip()

            if not raw_content:
                last_error = "Empty response from API"
                print(f"  WARN: Empty response (attempt {attempt}/{MAX_RETRIES})", file=sys.stderr)
                continue

            return _extract_json(raw_content)

        except requests.Timeout:
            last_error = f"Timeout after {TIMEOUT}s (attempt {attempt}/{MAX_RETRIES})"
            print(f"  WARN: {last_error}", file=sys.stderr)
        except requests.HTTPError as e:
            status = e.response.status_code
            body = e.response.text[:200]
            last_error = f"HTTP {status}: {body}"
            print(f"  WARN: {last_error}", file=sys.stderr)
            if status in (400, 401, 403, 404):
                break
        except (json.JSONDecodeError, KeyError) as e:
            last_error = f"JSON parse error: {e}"
            print(f"  WARN: {last_error}", file=sys.stderr)
            break
        except requests.ConnectionError as e:
            last_error = f"Connection: {e}"
            print(f"  WARN: {last_error}", file=sys.stderr)

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    print(f"ERROR: API call failed: {last_error}", file=sys.stderr)
    sys.exit(3)


def _extract_json(raw_content: str) -> dict:
    """Extract and parse JSON from raw API response, handling markdown fences and thinking blocks."""
    # Strip markdown fences if present
    content = raw_content
    if content.startswith("```"):
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
        if match:
            content = match.group(1).strip()

    # Try direct JSON parse first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # DeepSeek may wrap JSON in thinking/explanation text — extract brace pair
    last_brace = content.rfind("}")
    if last_brace != -1:
        depth = 0
        for i in range(last_brace, -1, -1):
            if content[i] == "}":
                depth += 1
            elif content[i] == "{":
                depth -= 1
                if depth == 0:
                    candidate = content[i:last_brace + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        pass
                    break

    print(f"ERROR: Response is not valid JSON ({len(raw_content)} chars)", file=sys.stderr)
    print(f"  First 150: {raw_content[:150]}", file=sys.stderr)
    sys.exit(3)


def write_critic_report(
    article_path: Path,
    result: dict,
    iteration: int,
) -> bool:
    """Write .critic.md report file. Returns True if PASS, False if FAIL."""
    slug = article_path.stem
    critic_dir = CRITIC_DIR
    critic_dir.mkdir(parents=True, exist_ok=True)

    categories = result.get("categories", {})
    summary = result.get("summary", "")
    all_pass = all(
        cat.get("status") == "PASS"
        for cat in categories.values()
    )

    lines = []
    lines.append(f"# Critic Report: {slug}")
    lines.append("")
    lines.append(f"Iteration: {iteration}/3")
    lines.append(f"Verdict: {'PASS' if all_pass else 'FAIL'}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for cat in CATEGORIES:
        cid = cat["id"]
        data = categories.get(cid, {"status": "PASS", "findings": []})
        status = data.get("status", "PASS")
        findings = data.get("findings", [])

        icon = "✓" if status == "PASS" else "✗"
        lines.append(f"## {icon} {cat['label']} — {status}")
        lines.append("")

        if status == "FAIL":
            for f in findings:
                quote = f.get("quote") or f.get("description", "")
                line_no = f.get("line")
                suggestion = f.get("suggestion", "")
                if line_no:
                    lines.append(f"- **Line {line_no}:** {quote}")
                else:
                    lines.append(f"- {quote}")
                if suggestion:
                    lines.append(f"  - {suggestion}")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"## Summary")
    lines.append("")
    lines.append(summary or ("All categories PASS." if all_pass else "See findings above."))

    report_path = critic_dir / f"{slug}.critic.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  Report: {report_path}")

    return all_pass


def write_counter(article_path: Path, iteration: int) -> None:
    """Write current iteration counter."""
    slug = article_path.stem
    counter_path = CRITIC_DIR / f"{slug}.counter.txt"
    counter_path.write_text(str(iteration), encoding="utf-8")
    print(f"  Counter: {counter_path} ({iteration}/3)")


def main() -> None:
    """Main entry point."""
    args = parse_args()

    print(f"Critic: {args.file.name} (iteration {args.iteration}/3)")
    text = read_article(args.file)
    print(f"  Text length: {len(text)} chars")

    print(f"  Calling {BACKEND.upper()} API ({MODEL})...")
    result = call_critic(text)

    all_pass = write_critic_report(args.file, result, args.iteration)
    write_counter(args.file, args.iteration)

    if all_pass:
        print(f"  Verdict: PASS — article is clean")
        sys.exit(0)
    else:
        print(f"  Verdict: FAIL — see .critic report")
        sys.exit(1)


if __name__ == "__main__":
    main()
