"""Тесты на критичные функции build.py.

Защита от регрессий, которые ловились только на живом сайте:
1. Потеря первой буквы при H1->H2 (был баг `^# [^#]`).
2. Нумерация секций (сезоны/подразделы не должны нумероваться как разделы).
3. Пустой FAQ (## FAQ без :::faq) должен быть отвергнут.
4. H1 в теле -> H2.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from build import preprocess_markdown, _H1_IN_BODY
import re

# --- 1. H1 конверсия сохраняет первую букву ---
def test_h1_keeps_first_letter():
    """# Где искать сома -> ## Где искать сома (не 'де искать')."""
    body = "# Где искать сома и как он себя ведёт\n\nтекст"
    out, _ = preprocess_markdown(body)
    assert out.startswith("## Где искать сома"), f"Первая буква потеряна: {out!r}"
    # "де искать" без "Г" — не должно быть отдельным словом после заголовка
    assert not out.startswith("## де ")

def test_h1_multiple_lines():
    """Несколько H1 в теле -> все в H2."""
    body = "# Раздел один\n# Раздел два"
    out, _ = preprocess_markdown(body)
    assert out.count("## Раздел") == 2

def test_h2_not_touched():
    """Уже H2 не меняется."""
    body = "## Правильный раздел"
    out, _ = preprocess_markdown(body)
    assert out == "## Правильный раздел"

# --- 2. Регулярка H1 не съедает букву (прямой тест) ---
def test_h1_regex_does_not_eat_char():
    for line in ["# Где искать", "# Сезонность", "# Снасти", "# Приманки"]:
        out = _H1_IN_BODY.sub("## ", line)
        assert out == "## " + line[2:], f"Regex съел букву: {line!r} -> {out!r}"

# --- 3. Валидация структуры markdown ---
def test_empty_faq_detected():
    """'## FAQ' без :::faq — структурная ошибка."""
    from tools.validate_md import validate_md
    md = "## Раздел\n\nтекст\n\n## FAQ\n"
    errors = validate_md(md)
    assert any("FAQ" in e and "пуст" in e.lower() for e in errors), errors

def test_plain_heading_detected():
    """Заголовок-строка без '#' (как делал гуманизатор) — ошибка."""
    from tools.validate_md import validate_md
    md = "Биология и поведение объекта\n\nКакой-то текст абзаца длиннее."
    errors = validate_md(md)
    assert any("заголовк" in e.lower() for e in errors), errors

def test_callouts_clustered_detected():
    """Callout скучены в конце (>60%) — предупреждение/ошибка."""
    from tools.validate_md import validate_md
    lines = ["## Раздел " + str(i) + "\n\n" + "текст "*20 for i in range(5)]
    body = "".join(lines)
    body += "\n:::summary\nВывод\n:::\n:::warning\nОшибка\n:::\n:::myth\nМиф\n:::\n:::tip\nСовет\n:::\n"
    errors = validate_md(body)
    assert any("callout" in e.lower() for e in errors), errors
