"""
Prompt-evaluation harness for ProcureGPT.

Runs the *actual* production prompt (the request parser) against a set of golden
cases and scores the structured output on concrete, checkable assertions —
turning "the prompt seems to work" into a repeatable pass-rate + token/cost
report. This is the "eval" leg of the LLM-app loop: change a prompt or swap a
model, re-run this, and see whether quality regressed *before* it ships.

Run:
    cd backend
    python -m scripts.eval_prompts
    python -m scripts.eval_prompts --provider anthropic --model claude-sonnet-5

It exercises the real code path (`llm_client.generate_json`) and the real token
tracker, so the cost figures are exactly what production would spend.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.agents.nodes.parse_request import PARSE_SYSTEM_PROMPT
from app.ai.llm_client import llm_client
from app.ai.token_tracker import track_usage

CASES_FILE = Path(__file__).parent / "eval_cases" / "parse_cases.json"

# ANSI colors (no-op on redirect)
_G, _R, _Y, _B, _X = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"


def _check(name: str, ok: bool, detail: str = "") -> dict:
    return {"check": name, "ok": bool(ok), "detail": detail}


def _first_item_name(parsed: dict) -> str:
    items = parsed.get("items") or []
    if not items:
        return ""
    return (items[0].get("product_name") or "").lower()


def score_case(expect: dict, parsed: dict | None) -> list[dict]:
    """Return one check result per assertion in `expect`."""
    checks: list[dict] = []
    if parsed is None:
        return [_check("parsed_ok", False, "LLM returned unparseable output")]

    items = parsed.get("items") or []

    if "is_complete" in expect:
        checks.append(_check(
            "is_complete", parsed.get("is_complete") == expect["is_complete"],
            f"got {parsed.get('is_complete')}",
        ))
    if "min_items" in expect:
        checks.append(_check(
            "min_items", len(items) >= expect["min_items"],
            f"got {len(items)} items",
        ))
    if "item_name_contains" in expect:
        kw = expect["item_name_contains"].lower()
        joined = " ".join((i.get("product_name") or "").lower() for i in items)
        checks.append(_check("item_name_contains", kw in joined, f"'{kw}' in '{joined[:60]}'"))
    if "quantity" in expect:
        qtys = [i.get("quantity") for i in items]
        checks.append(_check("quantity", expect["quantity"] in qtys, f"got {qtys}"))
    if "currency" in expect:
        checks.append(_check(
            "currency", (parsed.get("currency") or "").upper() == expect["currency"].upper(),
            f"got {parsed.get('currency')}",
        ))
    if "budget_max" in expect:
        checks.append(_check(
            "budget_max", parsed.get("budget_max") == expect["budget_max"],
            f"got {parsed.get('budget_max')}",
        ))
    if expect.get("direct_supplier_is_null"):
        checks.append(_check(
            "direct_supplier_is_null", not parsed.get("direct_supplier"),
            f"got {parsed.get('direct_supplier')!r}",
        ))
    if "direct_supplier_contains" in expect:
        got = (parsed.get("direct_supplier") or "")
        checks.append(_check(
            "direct_supplier_contains",
            expect["direct_supplier_contains"].lower() in got.lower(),
            f"got {got!r}",
        ))
    return checks


async def run() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the request-parsing prompt.")
    parser.add_argument("--provider", help="Override LLM provider (anthropic/openai/gemini)")
    parser.add_argument("--model", help="Override model id")
    parser.add_argument("--cases", default=str(CASES_FILE), help="Path to cases JSON")
    args = parser.parse_args()

    if args.provider or args.model:
        from app.core.config import settings
        provider = args.provider or llm_client.provider_name or "anthropic"
        key = {
            "anthropic": settings.ANTHROPIC_API_KEY,
            "openai": settings.OPENAI_API_KEY,
            "gemini": settings.GOOGLE_API_KEY,
        }.get(provider, "")
        model = args.model or llm_client.model
        llm_client.set_provider(provider, key, model)

    if not llm_client.is_configured:
        print(f"{_R}No LLM provider configured. Set ANTHROPIC_API_KEY (or --provider/--model).{_X}")
        return 2

    data = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    cases = data["cases"]

    print(f"\n{_B}ProcureGPT prompt eval{_X}  —  {len(cases)} cases")
    print(f"prompt : {data['prompt_under_test']}")
    print(f"model  : {llm_client.provider_name}/{llm_client.model}\n")

    total_checks = passed_checks = 0
    cases_fully_passed = 0

    with track_usage("prompt-eval") as usage:
        for case in cases:
            parsed = await llm_client.generate_json(
                system_prompt=PARSE_SYSTEM_PROMPT,
                user_prompt=case["input"],
            )
            results = score_case(case["expect"], parsed)
            case_pass = all(r["ok"] for r in results)
            cases_fully_passed += int(case_pass)
            total_checks += len(results)
            passed_checks += sum(r["ok"] for r in results)

            tag = f"{_G}PASS{_X}" if case_pass else f"{_R}FAIL{_X}"
            print(f"  [{tag}] {case['id']}")
            for r in results:
                if not r["ok"]:
                    print(f"         {_Y}✗ {r['check']}: {r['detail']}{_X}")

    pass_rate = (passed_checks / total_checks * 100) if total_checks else 0.0
    case_rate = (cases_fully_passed / len(cases) * 100) if cases else 0.0

    print(f"\n{_B}Results{_X}")
    print(f"  cases fully passed : {cases_fully_passed}/{len(cases)}  ({case_rate:.0f}%)")
    print(f"  checks passed      : {passed_checks}/{total_checks}  ({pass_rate:.0f}%)")
    print(f"\n{_B}Cost{_X} (real, via token_tracker)")
    s = usage.summary()
    print(f"  llm calls          : {s['calls']}")
    print(f"  tokens in/out      : {s['input_tokens']} / {s['output_tokens']}")
    print(f"  cache hit rate     : {s['cache_hit_rate'] * 100:.0f}%")
    print(f"  est. cost          : ${s['cost_usd']:.5f}\n")

    # Non-zero exit if quality dropped below the bar — lets CI gate on it.
    return 0 if case_rate >= 80 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
