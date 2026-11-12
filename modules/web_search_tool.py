"""web_search tool exposed to the GPT chat flow via OpenAI function calling.

The search itself runs through OpenRouter's web plugin (Exa engine): a separate completion with
``plugins: [{"id": "web", ...}]`` whose model extracts dated facts from the results. The tool
returns those facts plus the raw result snippets and sources, so the answering model can check
claims against the sources instead of retelling a summary of a summary.

It is only called when the model decides it needs current information, and each user request
gets a small search budget, so ordinary questions don't pay for a search.
"""

import json
import os
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

import pytz

from modules.logger import error_logger, general_logger

WEB_SEARCH_TOOL_NAME = "web_search"
WEB_SEARCH_ENABLED = os.getenv("WEB_SEARCH_ENABLED", "1").lower() not in {"0", "false", "no", ""}
# Model that reads the raw results and extracts facts. Engine is pinned to Exa below, so a model
# with native search (GPT-4.1+, Claude, Gemini 3) doesn't switch to that provider's search pricing.
WEB_SEARCH_MODEL = os.getenv("WEB_SEARCH_MODEL", "openai/gpt-4.1-mini")
# Exa bills per request and includes up to 10 results, so 10 costs the same as 5
WEB_SEARCH_MAX_RESULTS = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "10"))
# Exa modes: "auto" ($0.007/search) for normal lookups, "deep-lite" ($0.012) for deep=true calls
WEB_SEARCH_MODE = os.getenv("WEB_SEARCH_MODE", "auto")
WEB_SEARCH_DEEP_MODE = os.getenv("WEB_SEARCH_DEEP_MODE", "deep-lite")
# Searches allowed per user request (a news digest may need a few focused queries)
WEB_SEARCH_MAX_PER_REQUEST = int(os.getenv("WEB_SEARCH_MAX_PER_REQUEST", "4"))
WEB_SEARCH_MAX_TOKENS = 900
MAX_SOURCES = 8
MAX_SNIPPET_CHARS = 500

_TZ = pytz.timezone("Europe/Kyiv")

WEB_SEARCH_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": WEB_SEARCH_TOOL_NAME,
        "description": (
            "Search the internet for current information: news, today's events, holidays, "
            "local happenings, recent releases, prices, sports results, anything that may have "
            "changed after your training data. Returns dated facts with sources and the raw "
            "result snippets. One query per topic: for a broad question (e.g. 'today's news') "
            "make several focused calls (e.g. Ukraine, world, tech) rather than one vague one. "
            "Not for weather: use get_weather."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Focused search query. Include the place and the date or month when "
                        "they matter, e.g. 'Goes Netherlands fireworks November 2026', "
                        "'Jensen Huang Nvidia CEO resignation'. English or the topic's local "
                        "language usually gives better results."
                    ),
                },
                "deep": {
                    "type": "boolean",
                    "description": (
                        "true for a deeper, slower search: a developing story, a follow-up the "
                        "first search didn't answer, or details like market reaction. Default false."
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
    "recent results or releases, stock moves), call the web_search tool instead of guessing or "
    "listing generic possibilities. For a broad news question, make 2-4 focused searches by "
    "topic. Grounding: state only facts that appear in the search results; never fill gaps "
    "with likely-sounding details (stock moves, reasons, numbers, quotes). If a detail is not "
    "in the results, say it is unknown or search again with deep=true. Check dates: \"today\" "
    "means the last 24 hours; don't present older items as today's news, and mention the date "
    "when an item is older. If sources disagree, say so. Never take weather from news results; "
    "use get_weather or leave weather out. Mention the key source briefly; say plainly if the "
    "search found nothing relevant."
)


def _now() -> datetime:
    return datetime.now(pytz.utc).astimezone(_TZ)


def _search_system_prompt(now: datetime) -> str:
    return (
        f"Today is {now.strftime('%A, %d %B %Y')}, {now.strftime('%H:%M')} Kyiv time. "
        "You extract facts from web search results for another assistant. Rules:\n"
        "- Output a short bullet list. Each bullet: one fact, then in brackets the source "
        "domain and the publication date if the result shows one, e.g. "
        "\"[reuters.com, 12 Nov 2026]\" or \"[reuters.com, date unknown]\".\n"
        "- Only facts explicitly stated in the results. Never infer or add details such as "
        "market reactions, reasons, numbers or quotes. If the query asks for something the "
        "results don't state, add a bullet \"Not in results: ...\".\n"
        "- Prefer the most recent results. Mark anything older than 2 days as \"(older)\".\n"
        "- If sources contradict each other, list both and say they conflict.\n"
        "- At most ~10 bullets. No introduction or conclusion."
    )


def _extract_sources(message: Dict[str, Any]) -> List[Dict[str, str]]:
    sources: List[Dict[str, str]] = []
    seen = set()
    for annotation in message.get("annotations") or []:
        citation = annotation.get("url_citation") if isinstance(annotation, dict) else None
        url = (citation or {}).get("url")
        if url and url not in seen:
            seen.add(url)
            source = {"title": (citation.get("title") or "").strip(), "url": url}
            snippet = " ".join((citation.get("content") or "").split())
            if snippet:
                source["snippet"] = snippet[:MAX_SNIPPET_CHARS]
            sources.append(source)
        if len(sources) >= MAX_SOURCES:
            break
    return sources


async def web_search(query: str, deep: bool = False, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Run a web search for ``query`` and return a JSON-serialisable dict for the model."""
    query = (query or "").strip()
    if not query:
        return {"error": "No query provided."}

    # Imported lazily: modules.gpt imports this module.
    from modules.gpt import client

    now = now or _now()
    plugin = {
        "id": "web",
        "engine": "exa",
        "mode": WEB_SEARCH_DEEP_MODE if deep else WEB_SEARCH_MODE,
        "max_results": WEB_SEARCH_MAX_RESULTS,
        "search_prompt": (
            f"A web search was conducted on {now.strftime('%d %B %Y')}. Results "
            "(check each one's date):"
        ),
    }
    try:
        response = await client.chat.completions.create(
            model=WEB_SEARCH_MODEL,
            messages=[
                {"role": "system", "content": _search_system_prompt(now)},
                {"role": "user", "content": query},
            ],
            max_tokens=WEB_SEARCH_MAX_TOKENS,
            temperature=0,
            plugins=[plugin],
        )
        message = response["choices"][0]["message"]
    except Exception as e:
        error_logger.error(f"Web search failed for {query!r}: {e}")
        return {"error": "Web search is unavailable right now."}

    general_logger.info(f"Web search ({plugin['mode']}): {query!r}")
    return {
        "query": query,
        "searched_at": now.strftime("%Y-%m-%d %H:%M Kyiv"),
        "facts": (message.get("content") or "").strip(),
        "sources": _extract_sources(message),
    }


def make_web_search_handler(
    max_searches: int = WEB_SEARCH_MAX_PER_REQUEST,
) -> Callable[[Dict[str, Any]], Awaitable[str]]:
    """Return a web_search tool handler for one user request, limited to ``max_searches`` calls."""
    remaining = max_searches

    async def handle(tool_call: Dict[str, Any]) -> str:
        nonlocal remaining
        try:
            args = json.loads(tool_call.get("function", {}).get("arguments") or "{}")
        except (TypeError, ValueError):
            args = {}
        if not isinstance(args, dict):
            args = {}
        if remaining <= 0:
            result: Dict[str, Any] = {
                "error": "Search limit for this question reached; answer from the results you have."
            }
        else:
            remaining -= 1
            result = await web_search(args.get("query", ""), deep=bool(args.get("deep")))
        return json.dumps(result, ensure_ascii=False)

    return handle
