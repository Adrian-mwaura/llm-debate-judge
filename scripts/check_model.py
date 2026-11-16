"""Check the DeepSeek setup with real API calls. Costs well under US$0.01.

    python scripts/check_model.py

1. Lists the models the key can use and confirms that `deepseek-flash` is one of them.
2. Makes one tiny call with thinking off and one with thinking `low`, through chat(),
   and prints the tokens and cost, so we can see that:
   - thinking off really gives 0 reasoning tokens, and
   - thinking on gives reasoning tokens, billed as output.
The calls are logged to logs/calls/check_model.jsonl.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from debate_judge.llm import MODEL, chat, get_client  # noqa: E402


def main() -> None:
    models = sorted(m.id for m in get_client().models.list().data)
    print("Models available:", ", ".join(models))
    if MODEL not in models:
        sys.exit(f"'{MODEL}' is not in the list. Update MODEL (or DEEPSEEK_MODEL in .env) and AGENTS.md.")
    print(f"OK: '{MODEL}' is available.\n")

    question = [{"role": "user", "content": "What is 17 * 23? Reply with the number only."}]
    for thinking in ("none", "low"):
        r = chat(question, thinking=thinking, max_tokens=2000, run="check_model", use_cache=False)
        print(f"thinking={thinking:5s} answer={r.text.strip()!r:8s} prompt={r.prompt_tokens} "
              f"completion={r.completion_tokens} reasoning={r.reasoning_tokens} "
              f"cost=${r.cost_usd:.6f} ({r.price_period}) finish={r.finish_reason}")
        if thinking == "none" and r.reasoning_tokens:
            print("  WARNING: thinking was off but reasoning tokens were billed. Check build_request().")
        if thinking == "low" and not r.reasoning_tokens:
            print("  WARNING: thinking was on but no reasoning tokens were reported. Check build_request().")


if __name__ == "__main__":
    main()
