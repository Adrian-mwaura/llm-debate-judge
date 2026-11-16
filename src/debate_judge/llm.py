"""The single entry point for every DeepSeek API call: chat().

Every call in the project goes through chat(), so that:

- it uses the model `deepseek-flash` with thinking set explicitly (thinking is on by default
  in the API and billed as output, so leaving it unset silently costs money);
- repeated calls are served from a disk cache under logs/cache/, which is committed,
  so neither team member pays twice for the same call;
- each call appends one JSON line to logs/calls/<run>.jsonl with its settings,
  tokens, cost and response, which the cost matching and the budget ledger read.

Typical use:

    from debate_judge.llm import chat
    r = chat([{"role": "user", "content": "2+2?"}], thinking="none", max_tokens=50, run="pilot_judge")
    r.text, r.cost_usd, r.cost_match_usd

Costs:

- cost_usd is what the call actually cost: peak or off-peak price at the time of the call,
  with the cache-hit discount. It is 0 when the answer came from our own disk cache.
- cost_match_usd is the cost at off-peak list price with no cache discount. It does not
  depend on the time of day or on caching, so use it to match methods on cost.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
DEFAULT_BASE_URL = "https://api.deepseek.com"

THINKING_LEVELS = ("none", "low", "high", "max")

# US$ per million tokens, from docs/research/question_selection.md (DeepSeek pricing page, 2026-11-16).
# Peak prices are double off-peak. The cache-hit peak price is assumed to double as well.
PRICES = {
    "offpeak": {"input_miss": 0.15, "input_hit": 0.003, "output": 0.60},
    "peak": {"input_miss": 0.30, "input_hit": 0.006, "output": 1.20},
}
# Peak hours in UTC, Monday to Friday: [start, end) in hours.
PEAK_HOURS_UTC = ((1, 4), (6, 10))

REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = Path(os.environ.get("DEBATE_JUDGE_LOG_DIR", REPO_ROOT / "logs"))

Message = dict[str, str]


@dataclass
class ChatResult:
    text: str
    reasoning: str | None
    finish_reason: str | None
    prompt_tokens: int
    cache_hit_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    cost_usd: float
    cost_match_usd: float
    price_period: str
    from_cache: bool
    key: str
    raw_usage: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------- pricing


def price_period(when: datetime) -> str:
    """Return "peak" or "offpeak" for a moment in time."""
    t = when.astimezone(timezone.utc)
    if t.weekday() >= 5:  # Saturday, Sunday
        return "offpeak"
    for start, end in PEAK_HOURS_UTC:
        if start <= t.hour < end:
            return "peak"
    return "offpeak"


def compute_cost(prompt_tokens: int, cache_hit_tokens: int, completion_tokens: int, period: str) -> float:
    p = PRICES[period]
    miss = prompt_tokens - cache_hit_tokens
    return (miss * p["input_miss"] + cache_hit_tokens * p["input_hit"] + completion_tokens * p["output"]) / 1e6


def match_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Cost at off-peak list price with no cache discount: the number to match methods on."""
    p = PRICES["offpeak"]
    return (prompt_tokens * p["input_miss"] + completion_tokens * p["output"]) / 1e6


# ---------------------------------------------------------------- request building


def build_request(
    messages: Sequence[Message],
    *,
    thinking: str,
    max_tokens: int,
    temperature: float | None,
    json_mode: bool,
    logprobs: bool,
) -> dict[str, Any]:
    """The keyword arguments for client.chat.completions.create()."""
    if thinking not in THINKING_LEVELS:
        raise ValueError(f"thinking must be one of {THINKING_LEVELS}, got {thinking!r}")
    req: dict[str, Any] = {"model": MODEL, "messages": list(messages), "max_tokens": max_tokens}
    if thinking == "none":
        req["extra_body"] = {"thinking": {"type": "disabled"}}
    else:
        req["extra_body"] = {"thinking": {"type": "enabled"}}
        req["reasoning_effort"] = thinking
    if temperature is not None:
        # The API ignores temperature in thinking mode; we still record it.
        req["temperature"] = temperature
    if json_mode:
        req["response_format"] = {"type": "json_object"}
    if logprobs:
        req["logprobs"] = True
    return req


def cache_key(request: dict[str, Any], sample: int) -> str:
    """Hash of everything that determines the answer, plus the sample index.

    The API has no `n` or `seed`, so k independent samples are k calls with sample=0..k-1.
    """
    blob = json.dumps({"request": request, "sample": sample}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- client, cache and log

_client = None
_client_lock = threading.Lock()
_log_lock = threading.Lock()


def get_client():
    global _client
    with _client_lock:
        if _client is None:
            from dotenv import load_dotenv
            from openai import OpenAI

            load_dotenv(REPO_ROOT / ".env")
            key = os.environ.get("DEEPSEEK_API_KEY")
            if not key or key.startswith("sk-your"):
                raise RuntimeError("Set DEEPSEEK_API_KEY in .env (see .env.example).")
            base_url = os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)
            _client = OpenAI(api_key=key, base_url=base_url, max_retries=0, timeout=600)
        return _client


def set_client(client) -> None:
    """Replace the API client, e.g. with a fake one in tests."""
    global _client
    with _client_lock:
        _client = client


def _cache_path(key: str) -> Path:
    return LOG_DIR / "cache" / key[:2] / f"{key}.json"


def _read_cache(key: str) -> dict[str, Any] | None:
    path = _cache_path(key)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_cache(key: str, entry: dict[str, Any]) -> None:
    path = _cache_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(entry, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def _append_log(run: str, record: dict[str, Any]) -> None:
    path = LOG_DIR / "calls" / f"{run}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    with _log_lock, open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _usage_dict(usage: Any) -> dict[str, Any]:
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    return dict(usage)


def _parse_response(resp: Any) -> dict[str, Any]:
    choice = resp.choices[0]
    msg = choice.message
    usage = _usage_dict(resp.usage)
    prompt = int(usage.get("prompt_tokens") or 0)
    hit = int(usage.get("prompt_cache_hit_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    details = usage.get("completion_tokens_details") or {}
    reasoning_tokens = int(details.get("reasoning_tokens") or 0)
    logprobs = None
    if getattr(choice, "logprobs", None) is not None and hasattr(choice.logprobs, "model_dump"):
        logprobs = choice.logprobs.model_dump()
    return {
        "text": msg.content or "",
        "reasoning": getattr(msg, "reasoning_content", None),
        "finish_reason": choice.finish_reason,
        "prompt_tokens": prompt,
        "cache_hit_tokens": hit,
        "completion_tokens": completion,
        "reasoning_tokens": reasoning_tokens,
        "logprobs": logprobs,
        "usage": usage,
        "model": getattr(resp, "model", None),
    }


def _call_with_retries(request: dict[str, Any], retries: int) -> Any:
    from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

    retryable = (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)
    for attempt in range(retries + 1):
        try:
            return get_client().chat.completions.create(**request)
        except retryable:
            if attempt == retries:
                raise
            time.sleep(min(60, 2**attempt) + random.random())


# ---------------------------------------------------------------- public API


def chat(
    messages: Sequence[Message],
    *,
    thinking: str,
    max_tokens: int,
    run: str,
    temperature: float | None = None,
    json_mode: bool = False,
    logprobs: bool = False,
    sample: int = 0,
    meta: dict[str, Any] | None = None,
    use_cache: bool = True,
    retries: int = 5,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> ChatResult:
    """Make one API call (or serve it from the disk cache) and log it.

    thinking:   "none", "low", "high" or "max". Required, so nobody pays for thinking by accident.
    max_tokens: required; with thinking on, it must leave room for the reasoning tokens too.
    run:        name of the log file, logs/calls/<run>.jsonl, e.g. "pilot_judge".
    sample:     index of an independent sample (0..k-1) for voting; part of the cache key.
    meta:       anything to record with the call, e.g. {"pair_id": ..., "role": "debater_A"}.
    """
    request = build_request(
        messages, thinking=thinking, max_tokens=max_tokens,
        temperature=temperature, json_mode=json_mode, logprobs=logprobs,
    )
    key = cache_key(request, sample)
    called_at = now()

    entry = _read_cache(key) if use_cache else None
    from_cache = entry is not None
    if entry is None:
        started = time.monotonic()
        resp = _call_with_retries(request, retries)
        parsed = _parse_response(resp)
        period = price_period(called_at)
        entry = {
            "key": key,
            "request": request,
            "sample": sample,
            "response": parsed,
            "called_at": called_at.isoformat(),
            "price_period": period,
            "cost_usd": compute_cost(parsed["prompt_tokens"], parsed["cache_hit_tokens"],
                                     parsed["completion_tokens"], period),
            "latency_s": round(time.monotonic() - started, 3),
        }
        if use_cache:
            _write_cache(key, entry)

    parsed = entry["response"]
    result = ChatResult(
        text=parsed["text"],
        reasoning=parsed["reasoning"],
        finish_reason=parsed["finish_reason"],
        prompt_tokens=parsed["prompt_tokens"],
        cache_hit_tokens=parsed["cache_hit_tokens"],
        completion_tokens=parsed["completion_tokens"],
        reasoning_tokens=parsed["reasoning_tokens"],
        cost_usd=0.0 if from_cache else entry["cost_usd"],
        cost_match_usd=match_cost(parsed["prompt_tokens"], parsed["completion_tokens"]),
        price_period=entry["price_period"],
        from_cache=from_cache,
        key=key,
        raw_usage=parsed["usage"],
    )

    _append_log(run, {
        "logged_at": now().isoformat(),
        "run": run,
        "key": key,
        "from_cache": from_cache,
        "model": MODEL,
        "thinking": thinking,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "json_mode": json_mode,
        "sample": sample,
        "meta": meta or {},
        "prompt_tokens": result.prompt_tokens,
        "cache_hit_tokens": result.cache_hit_tokens,
        "completion_tokens": result.completion_tokens,
        "reasoning_tokens": result.reasoning_tokens,
        "cost_usd": result.cost_usd,
        "cost_match_usd": result.cost_match_usd,
        "price_period": result.price_period,
        "finish_reason": result.finish_reason,
        "messages": list(messages),
        "text": result.text,
    })
    return result


def chat_many(jobs: Sequence[dict[str, Any]], *, workers: int = 32) -> list[ChatResult]:
    """Run many chat() calls in parallel. Each job is a dict of chat() keyword arguments
    plus "messages". Results come back in the same order as the jobs."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda job: chat(**job), jobs))


def summarize_log(run: str) -> dict[str, Any]:
    """Totals for one run's call log: calls, cache hits, tokens and both costs."""
    path = LOG_DIR / "calls" / f"{run}.jsonl"
    totals = {"run": run, "calls": 0, "from_cache": 0, "prompt_tokens": 0, "completion_tokens": 0,
              "reasoning_tokens": 0, "cost_usd": 0.0, "cost_match_usd": 0.0}
    if not path.exists():
        return totals
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            totals["calls"] += 1
            totals["from_cache"] += bool(r["from_cache"])
            for k in ("prompt_tokens", "completion_tokens", "reasoning_tokens", "cost_usd", "cost_match_usd"):
                totals[k] += r[k]
    return totals


__all__ = [
    "ChatResult", "chat", "chat_many", "summarize_log", "set_client",
    "price_period", "compute_cost", "match_cost", "build_request", "cache_key",
    "MODEL", "THINKING_LEVELS", "PRICES",
]
