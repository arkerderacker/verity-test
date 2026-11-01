"""
Groq API via httpx only — no openai SDK (avoids jiter/maturin/Rust on Termux).
"""

from __future__ import annotations

import os
from typing import Any

import httpx

GROQ_BASE = "https://api.groq.com/openai/v1"


def _api_key() -> str:
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key or key.startswith("gsk_your"):
        raise RuntimeError("Set GROQ_API_KEY in .env")
    return key


def _flatten_content(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        bits: list[str] = []
        for part in content:
            if isinstance(part, str):
                bits.append(part)
            elif isinstance(part, dict):
                bits.append(str(part.get("text") or part.get("content") or ""))
            else:
                bits.append(str(part))
        return "".join(bits).strip()
    return str(content).strip()


def _message_text(message: dict[str, Any] | None) -> str:
    if not isinstance(message, dict):
        return ""
    text = _flatten_content(message.get("content"))
    if text:
        return text
    return _flatten_content(message.get("reasoning"))


def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str,
    temperature: float = 0.85,
    max_tokens: int = 320,
) -> str:
    reasoning = "gpt-oss" in str(model or "").lower()
    budget = max(int(max_tokens), 768) if reasoning else int(max_tokens)
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if reasoning:
        payload["max_completion_tokens"] = budget
        payload["reasoning_effort"] = "low"
        payload["include_reasoning"] = False
    else:
        payload["max_tokens"] = budget

    def _post(body: dict[str, Any]) -> dict[str, Any]:
        resp = httpx.post(
            f"{GROQ_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {_api_key()}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=90.0,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Groq chat HTTP {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    data = _post(payload)
    try:
        choice = data["choices"][0]
        reply = _message_text(choice.get("message"))
        finish = choice.get("finish_reason")
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Groq chat bad response: {data!r}") from exc

    if not reply and reasoning:
        print(
            f"[groq] empty content finish={finish!r} — retry with more tokens",
            flush=True,
        )
        payload["max_completion_tokens"] = max(budget, 1024)
        data = _post(payload)
        try:
            reply = _message_text(data["choices"][0].get("message"))
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Groq chat bad response: {data!r}") from exc
    return (reply or "").strip()


def transcribe_audio(
    file_path: str,
    *,
    model: str,
    language: str | None = None,
) -> tuple[str, str | None]:
    """
    Whisper STT. Returns (text, language_code).
    Accepts wav/m4a/mp3/ogg.
    """
    name = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        audio_bytes = f.read()

    # Guess MIME
    lower = name.lower()
    if lower.endswith(".wav"):
        mime = "audio/wav"
    elif lower.endswith(".mp3"):
        mime = "audio/mpeg"
    elif lower.endswith(".m4a"):
        mime = "audio/mp4"
    elif lower.endswith(".ogg"):
        mime = "audio/ogg"
    else:
        mime = "application/octet-stream"

    data: dict[str, Any] = {
        "model": model,
        "response_format": "verbose_json",
    }
    if language:
        data["language"] = language

    files = {"file": (name, audio_bytes, mime)}
    resp = httpx.post(
        f"{GROQ_BASE}/audio/transcriptions",
        headers={"Authorization": f"Bearer {_api_key()}"},
        data=data,
        files=files,
        timeout=120.0,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Groq STT HTTP {resp.status_code}: {resp.text[:300]}")

    # verbose_json → JSON; plain → text
    ctype = resp.headers.get("content-type", "")
    if "application/json" in ctype or resp.text.lstrip().startswith("{"):
        payload = resp.json()
        text = str(payload.get("text") or "").strip()
        lang = payload.get("language")
        if isinstance(lang, str) and lang.strip():
            lang = lang.strip().lower()
        else:
            lang = language
        return text, lang

    return resp.text.strip(), language
