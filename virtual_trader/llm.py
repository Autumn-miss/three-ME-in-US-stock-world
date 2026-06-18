from __future__ import annotations

import os


def optional_llm_note(prompt: str) -> str | None:
    """Return an optional LLM note when OpenAI is configured; otherwise stay offline."""
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI

        client = OpenAI()
        response = client.responses.create(
            model=os.environ.get("VIRTUAL_TRADER_MODEL", "gpt-4.1-mini"),
            input=prompt,
            max_output_tokens=220,
        )
        return response.output_text.strip()
    except Exception:
        return None
