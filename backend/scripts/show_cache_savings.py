"""
Show real cost savings from prompt caching across recent LangSmith traces.
Demonstrates the actual dollar difference between cached and uncached calls.
"""
from dotenv import load_dotenv
load_dotenv()

from langsmith import Client

ANTHROPIC_INPUT_PRICE = 3.00 / 1_000_000   # $3/MTok for claude-sonnet-5
ANTHROPIC_CACHE_READ_PRICE = 0.30 / 1_000_000  # $0.30/MTok (90% discount)
ANTHROPIC_OUTPUT_PRICE = 15.00 / 1_000_000  # $15/MTok

def main():
    c = Client()
    runs = list(c.list_runs(project_name="ProcureGPT", limit=30, run_type="llm"))

    parse_runs = []
    for r in runs:
        meta = (r.extra or {}).get("metadata", {})
        if meta.get("langgraph_node") == "parse_request":
            usage = meta.get("usage_metadata", {})
            details = usage.get("input_token_details", {})
            parse_runs.append({
                "id": str(r.id)[:8],
                "input_tokens": usage.get("input_tokens", r.prompt_tokens or 0),
                "output_tokens": usage.get("output_tokens", r.completion_tokens or 0),
                "cache_read": details.get("cache_read", 0),
                "cache_write": details.get("cache_write", 0),
                "latency": f"{r.latency:.2f}s" if r.latency else "?",
                "start_time": r.start_time,
            })

    if not parse_runs:
        print("No parse_request runs found in LangSmith.")
        return

    print(f"\n{'='*70}")
    print(f"  PROMPT CACHING COST ANALYSIS - parse_request node")
    print(f"  (Last {len(parse_runs)} calls from LangSmith)")
    print(f"{'='*70}\n")
    print(f"  {'Run':<10} {'Input':<8} {'Cache Read':<12} {'Status':<8} {'Actual Cost':<12} {'Without Cache':<14} {'Saved'}")
    print(f"  {'-'*10} {'-'*8} {'-'*12} {'-'*8} {'-'*12} {'-'*14} {'-'*8}")

    total_actual = 0
    total_without_cache = 0

    for r in reversed(parse_runs):
        input_tok = r["input_tokens"]
        output_tok = r["output_tokens"]
        cache_read = r["cache_read"]

        # Actual cost (with cache discount)
        uncached_input = input_tok - cache_read if cache_read else input_tok
        actual_cost = (
            uncached_input * ANTHROPIC_INPUT_PRICE +
            cache_read * ANTHROPIC_CACHE_READ_PRICE +
            output_tok * ANTHROPIC_OUTPUT_PRICE
        )

        # Hypothetical cost without cache
        without_cache_cost = (
            input_tok * ANTHROPIC_INPUT_PRICE +
            output_tok * ANTHROPIC_OUTPUT_PRICE
        )

        saved = without_cache_cost - actual_cost
        status = "HIT" if cache_read > 0 else "MISS"

        total_actual += actual_cost
        total_without_cache += without_cache_cost

        marker = "[HIT]" if cache_read else "[MISS]"
        print(
            f"  {r['id']:<10} {input_tok:<8} {cache_read:<12} "
            f"{marker:<8} "
            f"${actual_cost:.5f}   ${without_cache_cost:.5f}     "
            f"{'$' + f'{saved:.5f}' if saved > 0 else '-'}"
        )

    print(f"\n  {'='*70}")
    total_saved = total_without_cache - total_actual
    pct = (total_saved / total_without_cache * 100) if total_without_cache > 0 else 0
    print(f"  TOTAL:  Actual=${total_actual:.5f}  |  Without cache=${total_without_cache:.5f}")
    print(f"  SAVED:  ${total_saved:.5f} ({pct:.1f}% reduction)")
    print(f"  {'='*70}\n")


if __name__ == "__main__":
    main()
