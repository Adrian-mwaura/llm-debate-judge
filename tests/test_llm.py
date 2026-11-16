"""Tests for chat(). They use a fake API client, so they cost nothing and need no key."""
import importlib
import json
import threading
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from debate_judge import llm


class FakeCompletions:
    def __init__(self, usage=None):
        self.requests = []
        self.lock = threading.Lock()
        self.delay = 0.0          # seconds each call takes
        self.content = None       # fixed content; default "answer <n>"
        self.finish_reason = "stop"
        self.logprobs = None
        self.usage = usage or {
            "prompt_tokens": 1000,
            "prompt_cache_hit_tokens": 200,
            "completion_tokens": 500,
            "completion_tokens_details": {"reasoning_tokens": 300},
        }

    def create(self, **request):
        with self.lock:
            self.requests.append(request)
            n = len(self.requests)
        time.sleep(self.delay)
        content = f"answer {n}" if self.content is None else self.content
        message = SimpleNamespace(content=content, reasoning_content="thinking...")
        choice = SimpleNamespace(message=message, finish_reason=self.finish_reason, logprobs=self.logprobs)
        return SimpleNamespace(choices=[choice], usage=dict(self.usage), model="deepseek-flash")


@pytest.fixture
def fake(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "LOG_DIR", tmp_path)
    completions = FakeCompletions()
    llm.set_client(SimpleNamespace(chat=SimpleNamespace(completions=completions)))
    yield completions
    llm.set_client(None)


MSG = [{"role": "user", "content": "Which is right, A or B?"}]
OFFPEAK = lambda: datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)  # Saturday  # noqa: E731
PEAK = lambda: datetime(2026, 11, 16, 7, 30, tzinfo=timezone.utc)  # Monday 07:30 UTC  # noqa: E731


def read_log(tmp_path, run):
    return [json.loads(line) for line in (tmp_path / "calls" / f"{run}.jsonl").read_text(encoding="utf-8").splitlines()]


def test_thinking_must_be_set_explicitly(fake):
    with pytest.raises(TypeError):
        llm.chat(MSG, max_tokens=10, run="t")  # no thinking argument
    with pytest.raises(ValueError):
        llm.chat(MSG, thinking="medium", max_tokens=10, run="t")


def test_thinking_off_and_on_requests(fake):
    llm.chat(MSG, thinking="none", max_tokens=10, run="t")
    llm.chat(MSG, thinking="high", max_tokens=10, run="t")
    off, on = fake.requests
    assert off["model"] == "deepseek-flash"
    assert off["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "reasoning_effort" not in off
    assert on["extra_body"] == {"thinking": {"type": "enabled"}}
    assert on["reasoning_effort"] == "high"


def test_cache_serves_repeat_calls_for_free(fake, tmp_path):
    a = llm.chat(MSG, thinking="none", max_tokens=10, run="t", now=OFFPEAK)
    b = llm.chat(MSG, thinking="none", max_tokens=10, run="t", now=OFFPEAK)
    assert len(fake.requests) == 1
    assert (a.from_cache, b.from_cache) == (False, True)
    assert b.text == a.text
    assert a.cost_usd > 0 and b.cost_usd == 0
    assert b.cost_match_usd == a.cost_match_usd  # matching counts the compute, cached or not
    log = read_log(tmp_path, "t")
    assert [r["from_cache"] for r in log] == [False, True]


def test_sample_index_gives_independent_calls(fake):
    r = [llm.chat(MSG, thinking="none", max_tokens=10, run="t", sample=i) for i in range(3)]
    assert len(fake.requests) == 3
    assert len({x.key for x in r}) == 3


def test_settings_change_the_cache_key(fake):
    llm.chat(MSG, thinking="none", max_tokens=10, run="t")
    llm.chat(MSG, thinking="none", max_tokens=20, run="t")
    llm.chat(MSG, thinking="low", max_tokens=10, run="t")
    assert len(fake.requests) == 3


def test_use_cache_false_always_calls(fake):
    llm.chat(MSG, thinking="none", max_tokens=10, run="t", use_cache=False)
    llm.chat(MSG, thinking="none", max_tokens=10, run="t", use_cache=False)
    assert len(fake.requests) == 2


def test_cost_offpeak_and_peak(fake):
    off = llm.chat(MSG, thinking="none", max_tokens=10, run="t", now=OFFPEAK)
    # 800 miss * 0.15 + 200 hit * 0.003 + 500 out * 0.60, per million
    assert off.price_period == "offpeak"
    assert off.cost_usd == pytest.approx((800 * 0.15 + 200 * 0.003 + 500 * 0.60) / 1e6)
    peak = llm.chat(MSG, thinking="none", max_tokens=10, run="t", now=PEAK, sample=1)
    assert peak.price_period == "peak"
    assert peak.cost_usd == pytest.approx(2 * off.cost_usd)
    # match cost: list off-peak price, no cache discount, same at any time
    expected_match = (1000 * 0.15 + 500 * 0.60) / 1e6
    assert off.cost_match_usd == pytest.approx(expected_match)
    assert peak.cost_match_usd == pytest.approx(expected_match)


@pytest.mark.parametrize("when,period", [
    (datetime(2026, 11, 16, 0, 59, tzinfo=timezone.utc), "offpeak"),  # Monday
    (datetime(2026, 11, 16, 1, 0, tzinfo=timezone.utc), "peak"),
    (datetime(2026, 11, 16, 3, 59, tzinfo=timezone.utc), "peak"),
    (datetime(2026, 11, 16, 4, 0, tzinfo=timezone.utc), "offpeak"),
    (datetime(2026, 11, 16, 6, 0, tzinfo=timezone.utc), "peak"),
    (datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc), "offpeak"),
    (datetime(2026, 11, 20, 8, 0, tzinfo=timezone.utc), "peak"),  # Friday
    (datetime(2026, 11, 21, 8, 0, tzinfo=timezone.utc), "offpeak"),  # Saturday
])
def test_price_period(when, period):
    assert llm.price_period(when) == period


def test_log_records_settings_tokens_and_meta(fake, tmp_path):
    llm.chat(MSG, thinking="low", max_tokens=99, run="pilot", temperature=0.7,
             meta={"pair_id": 7, "role": "debater_A"}, now=OFFPEAK)
    (r,) = read_log(tmp_path, "pilot")
    assert r["thinking"] == "low" and r["max_tokens"] == 99 and r["temperature"] == 0.7
    assert r["complete"] is True and r["finish_reason"] == "stop"
    assert r["meta"] == {"pair_id": 7, "role": "debater_A"}
    assert (r["prompt_tokens"], r["cache_hit_tokens"], r["completion_tokens"], r["reasoning_tokens"]) == (1000, 200, 500, 300)
    assert r["text"] == "answer 1" and r["messages"] == MSG


def test_summarize_log(fake):
    llm.chat(MSG, thinking="none", max_tokens=10, run="s", now=OFFPEAK)
    llm.chat(MSG, thinking="none", max_tokens=10, run="s", now=OFFPEAK)  # cache hit
    s = llm.summarize_log("s")
    assert s["calls"] == 2 and s["from_cache"] == 1
    assert s["completion_tokens"] == 1000
    assert s["cost_match_usd"] == pytest.approx(2 * (1000 * 0.15 + 500 * 0.60) / 1e6)


def test_chat_many_keeps_order(fake):
    jobs = [{"messages": MSG, "thinking": "none", "max_tokens": 10, "run": "m", "sample": i} for i in range(20)]
    results = llm.chat_many(jobs, workers=8)
    assert len(results) == 20 and len(fake.requests) == 20
    assert [r.key for r in results] == [llm.cache_key(fake.requests[0], i) for i in range(20)]


# ---- Adrian's review of PR #4 -------------------------------------------------


@pytest.mark.parametrize("content,finish", [
    ("", "length"),            # thinking spent the whole budget on reasoning
    ("half an argu", "length"),  # cut off mid-answer
    ("   ", "stop"),           # blank JSON-mode reply
])
def test_incomplete_answers_are_returned_but_not_cached(fake, tmp_path, content, finish):
    fake.content, fake.finish_reason = content, finish
    a = llm.chat(MSG, thinking="high", max_tokens=10, run="t", now=OFFPEAK)
    assert a.complete is False and a.from_cache is False and a.cost_usd > 0
    assert not (tmp_path / "cache").exists() or not any((tmp_path / "cache").rglob("*.json"))
    b = llm.chat(MSG, thinking="high", max_tokens=10, run="t", now=OFFPEAK)
    assert len(fake.requests) == 2 and b.from_cache is False
    log = read_log(tmp_path, "t")
    assert [r["complete"] for r in log] == [False, False]
    assert llm.summarize_log("t")["incomplete"] == 2


def test_complete_answer_is_cached(fake):
    a = llm.chat(MSG, thinking="none", max_tokens=10, run="t")
    assert a.complete is True and a.finish_reason == "stop"


def test_env_file_settings_are_read_at_import(monkeypatch):
    """load_dotenv must run before MODEL is read, so DEEPSEEK_MODEL in .env takes effect."""
    import dotenv

    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    def fake_load_dotenv(*args, **kwargs):
        monkeypatch.setenv("DEEPSEEK_MODEL", "model-from-dotenv")  # undone after the test
        return True

    monkeypatch.setattr(dotenv, "load_dotenv", fake_load_dotenv)
    try:
        importlib.reload(llm)
        assert llm.MODEL == "model-from-dotenv"
    finally:
        monkeypatch.undo()
        importlib.reload(llm)
    assert llm.MODEL != "model-from-dotenv"


class FakeLogprobs:
    def model_dump(self):
        return {"content": [{"token": "A", "logprob": -0.1}]}


def test_logprobs_reach_the_caller_and_the_log(fake, tmp_path):
    fake.logprobs = FakeLogprobs()
    r = llm.chat(MSG, thinking="none", max_tokens=10, run="t", logprobs=True)
    assert fake.requests[0]["logprobs"] is True
    assert r.logprobs == {"content": [{"token": "A", "logprob": -0.1}]}
    assert read_log(tmp_path, "t")[0]["logprobs"] == r.logprobs
    again = llm.chat(MSG, thinking="none", max_tokens=10, run="t", logprobs=True)
    assert again.from_cache and again.logprobs == r.logprobs


def test_identical_concurrent_calls_are_paid_once(fake):
    fake.delay = 0.2
    jobs = [{"messages": MSG, "thinking": "none", "max_tokens": 10, "run": "c"} for _ in range(8)]
    results = llm.chat_many(jobs, workers=8)
    assert len(fake.requests) == 1
    assert sum(not r.from_cache for r in results) == 1
    assert len({r.text for r in results}) == 1


def test_different_concurrent_calls_still_run_in_parallel(fake):
    fake.delay = 0.3
    jobs = [{"messages": MSG, "thinking": "none", "max_tokens": 10, "run": "p", "sample": i} for i in range(8)]
    started = time.monotonic()
    llm.chat_many(jobs, workers=8)
    assert len(fake.requests) == 8
    assert time.monotonic() - started < 8 * 0.3 / 2  # not serialized


def test_temperature_not_sent_in_thinking_mode(fake, tmp_path):
    a = llm.chat(MSG, thinking="high", max_tokens=10, run="t", temperature=0.7)
    b = llm.chat(MSG, thinking="high", max_tokens=10, run="t")
    assert "temperature" not in fake.requests[0]
    assert len(fake.requests) == 1 and b.from_cache and a.key == b.key
    assert read_log(tmp_path, "t")[0]["temperature"] == 0.7  # still logged


def test_temperature_sent_with_thinking_off(fake):
    llm.chat(MSG, thinking="none", max_tokens=10, run="t", temperature=0.7)
    llm.chat(MSG, thinking="none", max_tokens=10, run="t")
    assert fake.requests[0]["temperature"] == 0.7
    assert len(fake.requests) == 2  # different temperatures are different requests


def test_missing_key_gives_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "LOG_DIR", tmp_path)
    monkeypatch.setattr(llm, "REPO_ROOT", tmp_path)  # no .env there
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    llm.set_client(None)
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        llm.chat(MSG, thinking="none", max_tokens=10, run="t")
