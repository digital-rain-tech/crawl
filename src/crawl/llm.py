"""LLM integration for business rule extraction.

Supports OpenRouter (default) with any model, or direct OpenAI-compatible APIs.
Logs all requests to a local SQLite database for audit and cost tracking.

Environment variables:
    OPENROUTER_API_KEY  -API key for OpenRouter (sk-or-v1-...)
    CRAWL_LLM_MODEL     -Model to use (default: arcee-ai/trinity-large-preview:free)
    CRAWL_LLM_BASE_URL  -Base URL override (default: https://openrouter.ai/api/v1)
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import httpx

# Defaults
DEFAULT_MODEL = "arcee-ai/trinity-large-preview:free"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 2048
LOG_DB_PATH = Path("crawl_llm_log.db")


@dataclass
class LLMResponse:
    """Response from an LLM call."""

    text: str
    model: str
    request_id: str
    response_time_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    raw_response: dict = field(default_factory=dict)


def _get_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise ValueError(
            "OPENROUTER_API_KEY environment variable not set. "
            "Get a free key at https://openrouter.ai/keys"
        )
    return key


def _init_log_db(db_path: Path = LOG_DB_PATH) -> sqlite3.Connection:
    """Initialize the SQLite logging database."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_requests (
            id TEXT PRIMARY KEY,
            created_at TEXT DEFAULT (datetime('now')),
            model TEXT NOT NULL,
            use_case TEXT,
            prompt_text TEXT,
            response_text TEXT,
            response_status INTEGER,
            error_message TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            response_time_ms INTEGER,
            raw_request TEXT,
            raw_response TEXT,
            metadata TEXT
        )
    """)
    conn.commit()
    return conn


def _log_request(
    db_path: Path,
    request_id: str,
    model: str,
    use_case: str,
    prompt_text: str,
    response_text: str | None,
    response_status: int | None,
    error_message: str | None,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    response_time_ms: int,
    raw_request: dict,
    raw_response: dict,
    metadata: dict | None = None,
) -> None:
    """Log an LLM request to SQLite."""
    conn = _init_log_db(db_path)
    try:
        conn.execute(
            """INSERT INTO llm_requests
               (id, model, use_case, prompt_text, response_text, response_status,
                error_message, prompt_tokens, completion_tokens, total_tokens,
                response_time_ms, raw_request, raw_response, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                request_id, model, use_case, prompt_text, response_text,
                response_status, error_message, prompt_tokens, completion_tokens,
                total_tokens, response_time_ms, json.dumps(raw_request),
                json.dumps(raw_response), json.dumps(metadata or {}),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def call_llm(
    prompt: str,
    system_prompt: str = "",
    use_case: str = "extraction",
    model: str | None = None,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    db_path: Path = LOG_DB_PATH,
) -> LLMResponse:
    """Call the LLM via OpenRouter and log the request.

    Uses the OpenAI-compatible chat completions endpoint.
    """
    api_key = _get_api_key()
    base_url = os.environ.get("CRAWL_LLM_BASE_URL", DEFAULT_BASE_URL)
    model = model or os.environ.get("CRAWL_LLM_MODEL", DEFAULT_MODEL)
    request_id = str(uuid.uuid4())

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/digital-rain-tech/crawl",
        "X-Title": "Crawl -Pre-migration Intelligence",
        "Content-Type": "application/json",
    }

    start_time = time.monotonic()
    response_status = None
    error_message = None
    response_text = None
    raw_response = {}
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response_status = resp.status_code
            raw_response = resp.json()

            if resp.status_code != 200:
                error_message = raw_response.get("error", {}).get("message", resp.text)
                raise ValueError(f"LLM API error ({resp.status_code}): {error_message}")

            # Extract response
            choices = raw_response.get("choices", [])
            if choices:
                response_text = choices[0].get("message", {}).get("content", "")

            usage = raw_response.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)

    except httpx.TimeoutException:
        error_message = "Request timed out after 60s"
        raise
    except Exception as e:
        if not error_message:
            error_message = str(e)
        raise
    finally:
        response_time_ms = int((time.monotonic() - start_time) * 1000)
        _log_request(
            db_path=db_path,
            request_id=request_id,
            model=model,
            use_case=use_case,
            prompt_text=prompt[:2000],  # Truncate for logging
            response_text=response_text,
            response_status=response_status,
            error_message=error_message,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            response_time_ms=response_time_ms,
            raw_request=payload,
            raw_response=raw_response,
        )

    return LLMResponse(
        text=response_text or "",
        model=model,
        request_id=request_id,
        response_time_ms=response_time_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        raw_response=raw_response,
    )


def explain_mapping(
    mapping_name: str,
    source_tables: list[str],
    target_tables: list[str],
    expressions: list[str],
    db_path: Path = LOG_DB_PATH,
) -> str:
    """Use LLM to explain a mapping in plain English."""
    system_prompt = (
        "You are a data engineering expert analyzing ETL mappings for a migration assessment. "
        "Given a mapping's source tables, target tables, and transformation expressions, "
        "explain what business logic this mapping implements in 2-3 clear sentences. "
        "Focus on WHAT the mapping does (business purpose), not HOW (technical details). "
        "If you can identify the business domain (e.g., customer analytics, sales reporting), mention it. "
        "Be specific about calculations, aggregations, and data transformations."
    )

    expr_text = "\n".join(f"  - {e}" for e in expressions[:30])  # Cap at 30
    prompt = (
        f"Mapping: {mapping_name}\n"
        f"Source tables: {', '.join(source_tables)}\n"
        f"Target tables: {', '.join(target_tables)}\n"
        f"Transformation expressions:\n{expr_text}\n\n"
        f"Explain what business logic this mapping implements:"
    )

    response = call_llm(
        prompt=prompt,
        system_prompt=system_prompt,
        use_case="explain_mapping",
        db_path=db_path,
    )
    return response.text.strip()
