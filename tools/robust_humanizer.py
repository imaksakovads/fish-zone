"""
Robust Humanizer — отказоустойчивый конвейер для "очеловечивания" текстов.

Pipeline:
  raw_text → pre_clean (AI-клише) → chunk (абзацы) → provider fallback (DeepSeek↔Gemini↔Local) → stream

Архитектура:
  - Полностью async (asyncio + httpx)
  - Streaming-ответ (SSE-совместимый)
  - Автоматический fallback между провайдерами
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import AsyncGenerator, Optional

import httpx

from models import (
    Chunk,
    HumanizeRequest,
    ProviderConfig,
    ProviderResult,
    CHUNK_SIZE_CHARS,
    HUMANIZER_SYSTEM_PROMPT,
    MAX_CONCURRENT_REQUESTS,
    PROVIDER_PRIORITY,
)

logger = logging.getLogger("robust_humanizer")


# ═══════════════════════════════════════════════════════════════════
# 1. AI-клише (детокс)
# ═══════════════════════════════════════════════════════════════════

# Словарь клише — не просто список, а категоризированный dict для гибкости
AI_CLICHES: dict[str, list[str]] = {
    "start_markers": [
        r"в начале этого материала[^.]*\.",
        r"таким образом[^.]*\n",
        r"в этой статье мы (рассмотрим|поговорим|узнаем)[^.]*\.",
        r"давайте (разберём|рассмотрим|поговорим о)[^.]*\.",
    ],
    "end_markers": [
        r"в заключени[ие][^.]*\.",
        r"подводя итог[^.]*\.",
        r"к концу (статьи|речи|текста)[^.]*\.",
        r"надеюсь, эта статья была[^.]*\.",
        r"спасибо за внимание[^.]*",
    ],
    "hedge_words": [
        r"\bважно отметить\b",
        r"\bстоит отметить\b",
        r"\bнесомненно\b",
        r"\bбезусловно\b",
        r"\bследует подчеркнуть\b",
        r"\bнельзя не упомянуть\b",
        r"\bочевидно, что\b",
        r"\bкак уже было сказано\b",
        r"\bбез сомнения\b",
        r"\bнадо заметить\b",
        r"\bкратко\b",
    ],
}

# Компилируем регулярки один раз при импорте
_CLICHE_PATTERNS: list[re.Pattern] = [
    re.compile(pattern, re.IGNORECASE | re.DOTALL)
    for patterns in AI_CLICHES.values()
    for pattern in patterns
]


# ═══════════════════════════════════════════════════════════════════
# 1.1 Постобработка — чистка AI-артефактов после генерации
# ═══════════════════════════════════════════════════════════════════

# Паттерны для постобработки сгенерированного текста
_AI_POST_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Тире (длинное и короткое) → точка и пробел
    (re.compile(r"\s*[—–-]\s+"), ". "),
    # Восклицательные знаки (оставить первый, убрать остальные)
    (re.compile(r"(?<!!)!(?!$)"), "."),
    # Множественные точки
    (re.compile(r"\.{4,}"), "."),
    # Двойные пробелы
    (re.compile(r" {2,}"), " "),
    # Пробелы перед точкой
    (re.compile(r"\s+\."), "."),
]


def post_process_text(text: str) -> str:
    """
    Чистит AI-артефакты после генерации: тире, лишние !, пробелы.
    Не трогает структуру и смысл — только пунктуационный мусор.
    """
    if not text:
        return text

    result = text
    for pattern, replacement in _AI_POST_PATTERNS:
        result = pattern.sub(replacement, result)

    # Убираем пустые абзацы
    result = re.sub(r"\n{3,}", "\n\n", result)
    result = result.strip()

    if result != text:
        logger.info("post_process: %d → %d символов (убраны AI-артефакты)", len(text), len(result))
    return result


def pre_clean_text(text: str) -> str:
    """
    Удаляет AI-клише из текста до вызова модели.

    Проходит по всем паттернам из AI_CLICHES и удаляет совпадения.
    Регистронезависимый поиск.
    """
    cleaned = text
    for pattern in _CLICHE_PATTERNS:
        cleaned = pattern.sub("", cleaned)

    # Чистим двойные пробелы и лишние пустые строки
    cleaned = re.sub(r" {2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    result = cleaned.strip()
    if len(result) < len(text) * 0.5:
        # Если удалили больше половины текста — что-то пошло не так, возвращаем оригинал
        logger.warning("pre_clean удалил >50%% текста (%d → %d), возвращаю оригинал", len(text), len(result))
        return text.strip()

    logger.info("pre_clean: %d → %d символов (-%d%%)", len(text), len(result),
                (1 - len(result) / max(len(text), 1)) * 100)
    return result


# ═══════════════════════════════════════════════════════════════════
# 2. Чанкинг текста
# ═══════════════════════════════════════════════════════════════════

def _estimate_tokens(text: str) -> int:
    """Грубая оценка токенов (1 токен ≈ 0.75 символа для смешанного текста)."""
    return int(len(text) * 4 / 3)


def chunk_text(text: str) -> list[Chunk]:
    """
    Разбивает текст на чанки по абзацам.

    Правила:
      - Граница только по \n\n (не режем предложения)
      - Макс. размер: CHUNK_SIZE_CHARS (~1500 символов / ~2000 токенов)
      - Если абзац больше лимита — всё равно берём целиком (не режем)
    """
    paragraphs = text.split("\n\n")
    chunks: list[Chunk] = []
    current_parts: list[str] = []
    current_size = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_size = len(para)
        # Если текущий чанк + новый абзац превышают лимит — финализируем чанк
        if current_parts and current_size + para_size > CHUNK_SIZE_CHARS:
            chunk_text = "\n\n".join(current_parts)
            chunks.append(Chunk(
                index=len(chunks),
                text=chunk_text,
                char_count=current_size,
                token_estimate=_estimate_tokens(chunk_text),
            ))
            current_parts = []
            current_size = 0

        current_parts.append(para)
        current_size += para_size

    # Последний чанк
    if current_parts:
        chunk_text = "\n\n".join(current_parts)
        chunks.append(Chunk(
            index=len(chunks),
            text=chunk_text,
            char_count=current_size,
            token_estimate=_estimate_tokens(chunk_text),
        ))

    if not chunks:
        # Пустой текст → один пустой чанк (чтобы конвейер не остановился)
        chunks.append(Chunk(index=0, text="", char_count=0, token_estimate=0))

    logger.info("chunk_text: %d абзацев → %d чанков", len(paragraphs), len(chunks))
    return chunks


# ═══════════════════════════════════════════════════════════════════
# 3. Парсеры стриминга для каждого провайдера
# ═══════════════════════════════════════════════════════════════════

def _parse_openai_line(line: str) -> Optional[str]:
    """Парсит строку стрима от OpenAI/DeepSeek формата 'data: {...}'."""
    if not line.startswith("data: "):
        return None
    payload = line[6:].strip()
    if payload == "[DONE]":
        return None
    try:
        data = json.loads(payload)
        # OpenAI-формат: choices[0].delta.content
        choices = data.get("choices", [])
        if choices:
            delta = choices[0].get("delta", {})
            return delta.get("content", None)
        # Альтернативный формат: data.text
        if "text" in data:
            return data["text"]
    except json.JSONDecodeError:
        pass
    return None


def _parse_gemini_line(line: str) -> Optional[str]:
    """Парсит SSE-строку от Gemini формата 'data: {...}'."""
    line = line.strip()
    if not line:
        return None
    # Gemini использует SSE: data: {...}
    if line.startswith("data: "):
        line = line[6:]
    try:
        data = json.loads(line)
        candidates = data.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if parts:
                return parts[0].get("text", None)
    except json.JSONDecodeError:
        pass
    return None


def _parse_ollama_line(line: str) -> Optional[str]:
    """Парсит строку стрима от Ollama."""
    line = line.strip()
    if not line:
        return None
    try:
        data = json.loads(line)
        message = data.get("message", {})
        content = message.get("content", None)
        if content is not None:
            return content
    except json.JSONDecodeError:
        pass
    return None


_STREAM_PARSERS = {
    "deepseek": _parse_openai_line,
    "gemini": _parse_gemini_line,
    "local": _parse_ollama_line,
}


# ═══════════════════════════════════════════════════════════════════
# 4. Основной класс
# ═══════════════════════════════════════════════════════════════════

class RobustHumanizer:
    """
    Асинхронный обработчик текстов с отказоустойчивым переключением провайдеров.

    Использование:
        humanizer = RobustHumanizer()
        async for chunk in humanizer.humanize_stream(HumanizeRequest(content="...")):
            print(chunk)
    """

    def __init__(
        self,
        providers: Optional[list[ProviderConfig]] = None,
        system_prompt: str = HUMANIZER_SYSTEM_PROMPT,
    ):
        self._providers: dict[str, ProviderConfig] = {
            p.name: p for p in (providers or [])
        }
        self._system_prompt = system_prompt
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self._last_used_provider = "unknown"

        # Единый HTTP-клиент на весь экземпляр
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=60.0, write=30.0, pool=30.0),
            limits=httpx.Limits(
                max_keepalive_connections=MAX_CONCURRENT_REQUESTS,
                max_connections=MAX_CONCURRENT_REQUESTS,
            ),
        )

    async def close(self) -> None:
        """Закрывает HTTP-клиент."""
        await self._client.aclose()

    # ── 4.1 Вызов одного провайдера ────────────────────────────────

    async def _call_provider(
        self,
        provider: ProviderConfig,
        text: str,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """
        Вызывает одного провайдера и стримит ответ.

        Генерирует фрагменты текста по мере поступления.
        При ошибке (4xx/5xx/таймаут) логирует и завершает генерацию.
        """
        logger.info("call_provider: %s | text=%d chars | max_tokens=%d",
                    provider.name, len(text), max_tokens)

        if not provider.api_key and provider.name != "local":
            logger.warning("call_provider: %s — нет API-ключа, пропускаю", provider.name)
            return

        async with self._semaphore:
            payload = self._build_payload(text, provider.name, max_tokens)
            headers = self._build_headers(provider)

            try:
                async with self._client.stream(
                    "POST",
                    provider.api_url,
                    json=payload,
                    headers=headers,
                ) as response:

                    if response.status_code == 429:
                        logger.warning("call_provider: %s rate limit (429), жду 2s", provider.name)
                        await asyncio.sleep(2)
                        return

                    if response.status_code >= 500:
                        logger.warning("call_provider: %s ошибка сервера (%d), пропускаю",
                                       provider.name, response.status_code)
                        return

                    if not response.is_success:
                        error_body = await response.aread()
                        logger.error("call_provider: %s HTTP %d: %s",
                                     provider.name, response.status_code, error_body[:200])
                        return

                    parser = _STREAM_PARSERS.get(provider.name, _parse_openai_line)

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        fragment = parser(line)
                        if fragment:
                            yield fragment

            except httpx.TimeoutException:
                logger.error("call_provider: %s таймаут (connect=%ss, read=%ss)",
                             provider.name, provider.connect_timeout, provider.read_timeout)
                return

            except httpx.ConnectError as e:
                logger.error("call_provider: %s connect error: %s", provider.name, e)
                return

            except Exception as e:
                logger.error("call_provider: %s неожиданная ошибка: %s: %s",
                             provider.name, type(e).__name__, e)
                return

    # ── 4.2 Fallback-цепь провайдеров ──────────────────────────────

    async def _call_with_fallback(
        self,
        text: str,
        max_tokens: int,
        preferred: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Пытается вызвать провайдеров в порядке приоритета.

        При ошибке (4xx/5xx/таймаут) переходит к следующему.
        Если все провайдеры исчерпаны — генерирует сообщение об ошибке.
        """
        # Определяем порядок: preferred первый, остальные по приоритету
        provider_order = PROVIDER_PRIORITY.copy()
        if preferred and preferred in provider_order:
            provider_order.remove(preferred)
            provider_order.insert(0, preferred)

        tried: list[str] = []
        for name in provider_order:
            provider = self._providers.get(name)
            if provider is None:
                logger.warning("call_with_fallback: провайдер '%s' не найден в конфиге", name)
                continue

            if not provider.api_key and provider.name != "local":
                logger.info("call_with_fallback: %s нет ключа, пропускаю", name)
                continue

            tried.append(name)

            # Собираем фрагменты от этого провайдера
            fragments: list[str] = []
            async for fragment in self._call_provider(provider, text, max_tokens):
                fragments.append(fragment)
                yield fragment

            if fragments:
                # Успешно получили ответ — запоминаем провайдера и выходим
                self._last_used_provider = name
                logger.info("call_with_fallback: %s ✅ (%d фрагментов)", name, len(fragments))
                return

            # Провайдер ничего не вернул — логируем и пробуем следующий
            logger.info("call_with_fallback: %s ❌ пустой ответ, смена провайдера", name)

        # Все провайдеры исчерпаны
        error_msg = (
            f"Не удалось обработать текст: все провайдеры недоступны "
            f"(попробованы: {', '.join(tried) or 'нет'}). "
            f"Проверьте API-ключи и соединение."
        )
        logger.error(error_msg)
        yield error_msg

    # ── 4.3 Полный конвейер ────────────────────────────────────────

    async def humanize_stream(
        self,
        request: HumanizeRequest,
    ) -> AsyncGenerator[str, None]:
        """
        Полный конвейер обработки текста.

        Pipeline:
          1. pre_clean_text() — удаление AI-клише
          2. chunk_text() — разбиение на абзацы
          3. Для каждого чанка — _call_with_fallback() со стримингом
          4. Склейка результатов
          5. post_process_text() — regexp-чистка AI-артефактов
          6. self-review — необязательный второй проход с critique
        """
        t_start = time.monotonic()
        logger.info("humanize_stream: начало | text=%d chars", len(request.content))

        cleaned = pre_clean_text(request.content)
        if not cleaned:
            yield json.dumps({"type": "error", "text": "Текст пуст после очистки."}) + "\n\n"
            return

        chunks = chunk_text(cleaned)
        if not chunks:
            yield json.dumps({"type": "error", "text": "Не удалось разбить текст на чанки."}) + "\n\n"
            return

        total_chunks = len(chunks)
        all_fragments: list[str] = []

        for i, chunk in enumerate(chunks):
            if not chunk.text.strip():
                continue

            logger.info("humanize_stream: чанк %d/%d | %d chars | ~%d токенов",
                        i + 1, total_chunks, chunk.char_count, chunk.token_estimate)

            async for fragment in self._call_with_fallback(
                text=chunk.text,
                max_tokens=request.max_tokens,
                preferred=request.provider,
            ):
                all_fragments.append(fragment)
                yield json.dumps({"type": "fragment", "text": fragment, "done": False}) + "\n\n"

            if i < total_chunks - 1:
                yield json.dumps({"type": "fragment", "text": "\n\n", "done": False}) + "\n\n"

        full_text = "".join(all_fragments)

        # Постобработка
        cleaned = post_process_text(full_text)
        if cleaned and cleaned != full_text:
            yield json.dumps({"type": "fragment", "text": "(правка пунктуации)", "done": False}) + "\n\n"

        # Self-review (только для текстов > 100 символов)
        final_text = cleaned
        if len(cleaned) > 100:
            reviewed = await self._self_review_non_streaming(cleaned)
            if reviewed and reviewed != cleaned and len(reviewed) > len(cleaned) * 0.6:
                logger.info("humanize_stream: self-review улучшил (%d → %d символов)",
                           len(cleaned), len(reviewed))
                final_text = reviewed
                yield json.dumps({"type": "review", "text": reviewed}) + "\n\n"

        duration = (time.monotonic() - t_start) * 1000
        yield json.dumps({
            "type": "done",
            "duration_ms": duration,
            "char_count": len(final_text),
            "provider": self._last_used_provider,
        }) + "\n\n"

    # ── 4.4 Self-review ─────────────────────────────────────────

    async def _self_review_non_streaming(self, text: str) -> str:
        """Нестриминговый self-review через Gemini Pro."""
        # Сначала пробуем Gemini, fallback на DeepSeek
        for provider_name in ("gemini", "deepseek"):
            provider = self._providers.get(provider_name)
            if not provider or not provider.api_key:
                continue

            result = await self._call_review(provider, text)
            if result:
                return result

        return text

    async def _call_review(self, provider: ProviderConfig, text: str) -> str | None:
        """Вызывает один провайдер для self-review."""
        review_prompt = (
            "Ниже текст, который нужно сделать максимально человечным.\n\n"
            "Что исправить:\n"
            "1. Убрать все длинные тире — заменить на точки.\n"
            "2. Убрать шаблонные вводные: «Кроме того», «Более того», "
            "«Следовательно», «Важно отметить».\n"
            "3. Разбить длинные предложения (больше 15 слов).\n"
            "4. Добавить разговорные связки: «Спойлер:», «Дело вот в чем» "
            "(но не более 1-2 на весь текст).\n"
            "5. Один-два абзаца сделать длиной в 1 предложение.\n"
            "6. Убрать псевдотермины: «считывается», «геометрия», «система».\n"
            "7. Использовать активный залог.\n\n"
            "НЕ менять смысл и факты. Только стиль.\n\n"
            f"Текст:\n{text}"
        )

        try:
            async with self._semaphore:
                if provider.name == "gemini":
                    payload = {
                        "contents": [
                            {"role": "user", "parts": [{"text": review_prompt}]},
                        ],
                        "generationConfig": {
                            "maxOutputTokens": max(2048, len(text) * 2),
                            "temperature": 0.3,
                        },
                    }
                else:
                    payload = {
                        "model": provider.model,
                        "messages": [
                            {"role": "user", "content": review_prompt},
                        ],
                        "max_tokens": max(2048, len(text) * 2),
                        "temperature": 0.3,
                        "stream": False,
                    }

                headers = self._build_headers(provider)
                # Для Gemini: заменяем stream-URL на non-streaming
                url = provider.api_url
                if provider.name == "gemini":
                    url = url.replace("streamGenerateContent?alt=sse", "generateContent")
                resp = await self._client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=30,
                )

                if not resp.is_success:
                    return None

                data = resp.json()
                content = None
                if provider.name == "gemini":
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            content = parts[0].get("text")
                else:
                    content = data.get("choices", [{}])[0].get("message", {}).get("content")

                if content:
                    return post_process_text(content.strip())
                return None

        except Exception as e:
            logger.warning("self-review(%s): ошибка %s — пропускаю", provider.name, e)
            return None

    # ── 4.4 Вспомогательные методы ─────────────────────────────────

    def _build_payload(self, text: str, provider: str, max_tokens: int) -> dict:
        """Формирует тело запроса в зависимости от провайдера."""
        if provider in ("nous", "deepseek", "local"):
            return {
                "model": self._providers[provider].model,
                "messages": [
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": text},
                ],
                "max_tokens": max_tokens,
                "stream": True,
                "temperature": 0.4,
                # reasoning-модели иначе тратят токены на рассуждения
                "reasoning": {"effort": "low"},
                "include_reasoning": False,
            }
        # Gemini
        return {
            "contents": [
                {"role": "user", "parts": [{"text": f"{self._system_prompt}\n\n{text}"}]},
            ],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.4,
            },
        }

    def _build_headers(self, provider: ProviderConfig) -> dict[str, str]:
        """Формирует HTTP-заголовки для конкретного провайдера."""
        headers: dict[str, str] = {"Content-Type": "application/json"}

        if provider.name == "gemini":
            # Gemini передаёт ключ в URL, но можем и в заголовке x-goog-api-key
            headers["x-goog-api-key"] = provider.api_key
        elif provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"

        return headers
