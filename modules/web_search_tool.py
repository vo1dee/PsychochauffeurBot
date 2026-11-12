"""web_search tool exposed to the GPT chat flow via OpenAI function calling.

The search itself runs through OpenRouter's web plugin: a separate completion with
``plugins: [{"id": "web"}]`` that returns a short summary of fresh search results plus
the source URLs. It is only called when the model decides it needs current information,
so ordinary questions don't pay for a search.
"""

import json
import os
from typing import Any, Dict, List

from modules.logger import error_logger, general_logger

WEB_SEARCH_TOOL_NAME = "web_search"
# Search results per call; OpenRouter bills the web plugin per result
WEB_SEARCH_MAX_RESULTS = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))
WEB_SEARCH_ENABLED = os.getenv("WEB_SEARCH_ENABLED", "1").lower() not in {"0", "false", "no", ""}
WEB_SEARCH_MODEL = os.getenv("WEB_SEARCH_MODEL", "openai/gpt-4o-mini")
WEB_SEARCH_MAX_TOKENS = 700
MAX_SOURCES = 5

WEB_SEARCH_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": WEB_SEARCH_TOOL_NAME,
        "description": (
            "Search the internet for current information: news, today's events, holidays, "
            "local happenings, recent releases, prices, sports results, anything that may have "
            "changed after your training data. Returns a summary of search results with sources."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Search query. Include the place and date when they matter, e.g. "
                        "'Goes Netherlands fireworks 12 November 2026'. Prefer the local or "
                        "English language of the topic for better results."
                    ),
                },
            },
            "required": ["query"],
        },
    },
}

WEB_SEARCH_TOOL_RULES = (
    "Web search rules: when the question depends on current or local information you cannot "
    "know (today's news or events, why something is happening right now, holidays, schedules, "
    "recent results or releases), call the web_search tool instead of guessing or listing "
    "generic possibilities. Answer from the results, mention the key source briefly, and say "
    "so plainly if the search found nothing relevant."
)

SEARCH_SYSTEM_PROMPT = (
    "Using the web search results, answer the query with the relevant facts only: what, where, "
    "when, and why. Be concise (up to ~8 sentences). If the results do not answer the query, "
    "say so. Do not invent facts."
)


def _extract_sources(message: Dict[str, Any]) -> List[Dict[str, str]]:
    sources: List[Dict[str, str]] = []
    seen = set()
    for annotation in message.get("annotations") or []:
        citation = annotation.get("url_citation") if isinstance(annotation, dict) else None
        url = (citation or {}).get("url")
        if url and url not in seen:
            seen.add(url)
            sources.append({"title": (citation.get("title") or "").strip(), "url": url})
        if len(sources) >= MAX_SOURCES:
            break
    return sources


async def web_search(query: str) -> Dict[str, Any]:
    """Run a web search for ``query`` and return a JSON-serialisable dict for the model."""
    query = (query or "").strip()
    if not query:
        return {"error": "No query provided."}

    # Imported lazily: modules.gpt imports this module.
    from modules.gpt import client

    try:
        response = await client.chat.completions.create(
            model=WEB_SEARCH_MODEL,
            messages=[
                {"role": "system", "content": SEARCH_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            max_tokens=WEB_SEARCH_MAX_TOKENS,
            temperature=0.2,
            plugins=[{"id": "web", "max_results": WEB_SEARCH_MAX_RESULTS}],
        )
        message = response["choices"][0]["message"]
    except Exception as e:
        error_logger.error(f"Web search failed for {query!r}: {e}")
        return {"error": "Web search is unavailable right now."}

    general_logger.info(f"Web search: {query!r}")
    return {
        "query": query,
        "summary": (message.get("content") or "").strip(),
        "sources": _extract_sources(message),
    }


async def web_search_tool_handler(tool_call: Dict[str, Any]) -> str:
    """Execute a web_search tool call and return its JSON result."""
    try:
        args = json.loads(tool_call.get("function", {}).get("arguments") or "{}")
    except (TypeError, ValueError):
        args = {}
    query = args.get("query", "") if isinstance(args, dict) else ""
    return json.dumps(await web_search(query), ensure_ascii=False)
