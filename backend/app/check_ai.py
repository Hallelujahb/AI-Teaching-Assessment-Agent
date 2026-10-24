"""Gate 0 check: discover OpenRouter free models that support tool calling, then probe
the best candidate to decide whether tools and a response format can be used together.

Run from the backend folder:  python -m app.check_ai

Owner: P3
Plan: section 2

Output is a human-readable report for P5 (docs/gate0-checklist.md). No secrets are
printed. At most 5 live requests are spent (4 candidate probes + 1 combined test).
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

FREE_MODELS_URL = "https://openrouter.ai/api/v1/models?supported_parameters=tools"
MAX_CANDIDATES = 4

# A tiny, unambiguous function-calling test.
_PROBE_TOOL = {
    "type": "function",
    "function": {
        "name": "get_number",
        "description": "Returns the secret number for a label.",
        "parameters": {
            "type": "object",
            "properties": {"label": {"type": "string"}},
            "required": ["label"],
        },
    },
}
_PROBE_MESSAGES = [
    {"role": "user", "content": "Use the tool to get the secret number labelled alpha."}
]
_PROBE_RESPONSE_FORMAT = {"type": "json_object"}


def _has_zero_pricing(model: dict) -> bool:
    """True when the model has a free tier with zero per-token cost."""
    pricing = model.get("pricing")
    if not pricing:
        return False
    vals = [pricing.get("prompt", 0), pricing.get("completion", 0), pricing.get("request", 0)]
    return all(float(v) == 0.0 for v in vals)


def list_free_tool_models() -> list[dict]:
    """Fetch the public models endpoint and return free models that support tools."""
    resp = httpx.get(FREE_MODELS_URL, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    results = data.get("data", [])
    out = []
    for m in results:
        mid = m.get("id", "")
        if not mid.endswith(":free"):
            continue
        if not _has_zero_pricing(m):
            continue
        context = m.get("context_length")
        supported = m.get("supported_parameters") or []
        out.append({
            "id": mid,
            "context_length": context,
            "structured_outputs": "structured_outputs" in supported or "json_schema" in supported,
            "supported_parameters": supported,
        })
    return out


def _probe_candidate(http: httpx.Client, model_id: str, *, with_format: bool = False) -> tuple[bool, str]:
    """Send one tiny chat request. Returns (ok, summary)."""
    tools = [_PROBE_TOOL]
    payload: dict[str, Any] = {
        "model": model_id,
        "messages": _PROBE_MESSAGES,
        "tools": tools,
        "max_tokens": 64,
        "temperature": 0,
        "max_retries": 0,  # B.2: never auto-retry on free tier
    }
    if with_format:
        payload["response_format"] = _PROBE_RESPONSE_FORMAT
    start = time.time()
    try:
        r = http.post(f"{_base_url()}/chat/completions", json=payload, timeout=30)
    except httpx.HTTPError as exc:
        return False, f"transport error: {type(exc).__name__}"
    elapsed = time.time() - start
    if r.status_code != 200:
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        return False, f"HTTP {r.status_code}: {body.get('error', {}).get('message', r.text[:120])}"
    data = r.json()
    # B.7: errors can arrive inside a 200 response
    if data.get("error"):
        return False, f"error in 200 body: {data['error'].get('message', data['error'])}"
    choices = data.get("choices") or []
    if not choices:
        return False, "empty choices in 200 response"
    msg = choices[0].get("message", {})
    has_tool = bool(msg.get("tool_calls"))
    if with_format:
        content = msg.get("content")
        has_json = bool(content and content.strip().startswith("{"))
        return has_tool and has_json, f"took {elapsed:.1f}s, tool={has_tool}, json={has_json}"
    return has_tool, f"took {elapsed:.1f}s, tool_call={has_tool}"


def _base_url() -> str:
    url = os.environ.get("AI_BASE_URL", "").rstrip("/")
    if not url:
        url = "https://openrouter.ai/api/v1"
    return url


def main() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    model = os.environ.get("AI_MODEL", "").strip()
    provider = os.environ.get("AI_PROVIDER", "").strip()

    print("=== Qeleme Gate 0 — OpenRouter free-model tool check ===")
    print(f"AI_PROVIDER={provider!r}  AI_MODEL={model!r}  (key {'set' if api_key else 'NOT SET'})")
    print()

    # ---- step 1: list candidates ----
    try:
        candidates = list_free_tool_models()
    except Exception as exc:
        print(f"FAILED to fetch models list: {exc}")
        sys.exit(1)

    print(f"Free models with tools: {len(candidates)}")
    if not candidates:
        print("No :free models with zero pricing and tool support found.")
        _suggest_alternative()
        sys.exit(1)

    for c in candidates[:MAX_CANDIDATES + 2]:
        s = "yes" if c["structured_outputs"] else "no"
        ctx = c["context_length"] or "?"
        print(f"  {c['id']:<55} ctx={ctx:<6} structured={s}")

    # Prefer models that also support structured_outputs
    candidates.sort(key=lambda c: (not c["structured_outputs"], c["id"]))
    candidates = candidates[:MAX_CANDIDATES]
    print(f"\nProbing up to {len(candidates)} candidates with one function-call request each:")

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    http = httpx.Client(headers=headers, timeout=30)

    passing = []
    for c in candidates:
        ok, summary = _probe_candidate(http, c["id"])
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {c['id']:<55} {summary}")
        if ok:
            passing.append(c)

    if not passing:
        print("\nNone of the candidates could make a tool call.")
        _suggest_alternative()
        sys.exit(1)

    best = passing[0]
    print(f"\nBest candidate: {best['id']}")

    # ---- step 2: tools + response_format together ----
    ok, summary = _probe_candidate(http, best["id"], with_format=True)
    print(f"\nTools + response_format=json_object on {best['id']}:")
    print(f"  [{'PASS' if ok else 'FAIL'}] {summary}")

    # ---- report ----
    print("\n=== Report for docs/gate0-checklist.md ===")
    print(f"Model ID:        {best['id']}")
    print(f"Structured:      {'supported' if best['structured_outputs'] else 'not supported'}")
    print(f"Tools:           supported (function calling works)")
    print(f"Tools+format:    {'works together' if ok else 'NOT supported — use prompt_only for final JSON call'}")
    print(f"Context length:  {best['context_length'] or 'unknown'}")
    print("Quotas:  20 req/min, 50 req/day on a non-billing account. No retries (max_retries=0).")
    print("Strategy: " + (
        "Single tool loop then final json_schema call."
        if ok else
        "Tool loop with prompt_only; final call is a plain prompt asking for JSON."
    ))

    http.close()
    sys.exit(0)


def _suggest_alternative() -> None:
    print("\nNo free model supports function calling.")
    print("A Gemini or Groq provider can drop into ai_provider.py with AI_PROVIDER=gemini|groq.")


if __name__ == "__main__":
    main()
