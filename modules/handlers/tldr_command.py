"""TLDR command handler — fetches URL content or summarizes replied message text."""

import html as html_lib
import re
from typing import Optional
from urllib.parse import urlparse, urlunparse

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from modules.gpt import GPT_MODEL_TEXT, client
from modules.logger import error_logger
from config_v2.compat import get_shared_config_manager

CHUNK_SIZE = 4000
MAX_CONTENT_LENGTH = 40_000
URL_PATTERN = re.compile(r'https?://\S+')
REDDIT_DOMAIN_PATTERN = re.compile(r'https?://(?:www\.)?reddit\.com/', re.IGNORECASE)
REDDIT_POST_PATTERN = re.compile(r'https?://(?:www\.)?reddit\.com/r/\w+/comments/\w+', re.IGNORECASE)

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_SYSTEM_PROMPTS = {
    "ukrainian": "Ти асистент, який підсумовує контент. Надай стислий та інформативний підсумок українською мовою.",
    "english": "You are a summarization assistant. Provide a concise and informative summary in English.",
    "original": "You are a summarization assistant. Provide a concise and informative summary. Preserve the original language of the content.",
}

_CHUNK_PROMPTS = {
    "ukrainian": "Підсумуй цю частину тексту стисло українською:",
    "english": "Summarize this part of the text concisely in English:",
    "original": "Summarize this part of the text concisely, preserving the original language:",
}

_MERGE_PROMPTS = {
    "ukrainian": "Об'єднай ці часткові підсумки в один зв'язний підсумок українською мовою:",
    "english": "Combine these partial summaries into one coherent summary in English:",
    "original": "Combine these partial summaries into one coherent summary, preserving the original language:",
}


async def _fetch_reddit_text(url: str) -> Optional[str]:
    """Fetch a Reddit post via the public JSON API."""
    try:
        parsed = urlparse(url)
        clean = urlunparse(parsed._replace(query='', fragment=''))
        json_url = clean.rstrip('/') + '.json'
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            follow_redirects=True,
            headers={"User-Agent": "TLDRBot/1.0 (summarization; contact: bot@example.com)"},
        ) as http_client:
            response = await http_client.get(json_url)
            response.raise_for_status()
            data = response.json()

        post = data[0]['data']['children'][0]['data']
        title = post.get('title', '')
        selftext = post.get('selftext', '').strip()

        parts = [title]
        if selftext and selftext != '[removed]' and selftext != '[deleted]':
            parts.append(selftext)

        # Include top-level comments (up to 10) for context
        comments = data[1]['data']['children']
        comment_texts = []
        for child in comments[:10]:
            body = child.get('data', {}).get('body', '').strip()
            if body and body not in ('[removed]', '[deleted]'):
                comment_texts.append(body)
        if comment_texts:
            parts.append("Top comments:\n" + "\n".join(f"- {c}" for c in comment_texts))

        text = '\n\n'.join(parts)
        if len(text) > MAX_CONTENT_LENGTH:
            text = text[:MAX_CONTENT_LENGTH]
        return text if len(text) > 20 else None
    except Exception as e:
        error_logger.error(f"Failed to fetch Reddit URL {url}: {e}")
        return None


async def _fetch_url_text(url: str) -> Optional[str]:
    """Fetch a webpage and return cleaned plain text, or None on failure."""
    if REDDIT_DOMAIN_PATTERN.match(url):
        # Follow redirects first (share links use /s/ and redirect to the actual post)
        resolved = url
        if not REDDIT_POST_PATTERN.match(url):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(10.0),
                    follow_redirects=True,
                    headers={"User-Agent": "TLDRBot/1.0 (summarization; contact: bot@example.com)"},
                ) as http_client:
                    resp = await http_client.head(url)
                    resolved = str(resp.url)
            except Exception:
                resolved = url
        if REDDIT_POST_PATTERN.match(resolved):
            return await _fetch_reddit_text(resolved)
        # Fell through (e.g. profile/subreddit page) — try generic fetch below

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            follow_redirects=True,
            headers=_BROWSER_HEADERS,
        ) as http_client:
            response = await http_client.get(url)
            response.raise_for_status()
            html_content = response.text

        # Remove script/style blocks before stripping tags
        html_content = re.sub(
            r'<(script|style)[^>]*>.*?</(script|style)>',
            ' ',
            html_content,
            flags=re.DOTALL | re.IGNORECASE,
        )
        text = re.sub(r'<[^>]+>', ' ', html_content)
        text = html_lib.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()

        if len(text) > MAX_CONTENT_LENGTH:
            text = text[:MAX_CONTENT_LENGTH]

        return text if len(text) > 50 else None
    except httpx.HTTPStatusError as e:
        error_logger.warning(f"HTTP {e.response.status_code} fetching {url}")
        return None
    except Exception as e:
        error_logger.error(f"Failed to fetch URL {url}: {e}")
        return None


async def _gpt_call(system_prompt: str, user_content: str) -> Optional[str]:
    """Make a single GPT call and return the response text."""
    try:
        response = await client.chat.completions.create(
            model=GPT_MODEL_TEXT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            max_tokens=500,
            temperature=0.4,
        )
        return response["choices"][0]["message"]["content"].strip() or None
    except Exception as e:
        error_logger.error(f"GPT call failed in tldr: {e}")
        return None


async def _summarize_chunked(text: str, lang: str) -> str:
    """Chunk text, summarize each chunk, then merge into a final summary."""
    chunks = [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
    system_prompt = _SYSTEM_PROMPTS[lang]
    chunk_prompt = _CHUNK_PROMPTS[lang]

    if len(chunks) == 1:
        result = await _gpt_call(system_prompt, f"{chunk_prompt}\n\n{chunks[0]}")
        return result or "Не вдалося згенерувати підсумок."

    chunk_summaries = []
    for i, chunk in enumerate(chunks):
        summary = await _gpt_call(
            system_prompt,
            f"{chunk_prompt} ({i + 1}/{len(chunks)})\n\n{chunk}",
        )
        if summary:
            chunk_summaries.append(summary)

    if not chunk_summaries:
        return "Не вдалося згенерувати підсумок."
    if len(chunk_summaries) == 1:
        return chunk_summaries[0]

    merge_prompt = _MERGE_PROMPTS[lang]
    merged = await _gpt_call(
        system_prompt,
        f"{merge_prompt}\n\n" + "\n\n---\n\n".join(chunk_summaries),
    )
    return merged or "\n\n".join(chunk_summaries)


async def tldr_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Summarize a replied-to message or URL. Usage: /tldr [english|original]"""
    if not update.message:
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "Використовуйте /tldr у відповідь на повідомлення або посилання.\n"
            "Мова: /tldr (укр), /tldr english, /tldr original"
        )
        return

    # Respect per-chat GPT enable/disable config
    if update.effective_chat:
        chat_config = await get_shared_config_manager().get_config(
            str(update.effective_chat.id),
            update.effective_chat.type,
            chat_name=update.effective_chat.title,
        )
        gpt_module = chat_config.get("config_modules", {}).get("gpt", {})
        if gpt_module and not gpt_module.get("enabled", True):
            return

    # Determine target language
    arg = context.args[0].lower() if context.args else ""
    if arg == "english":
        lang = "english"
    elif arg == "original":
        lang = "original"
    else:
        lang = "ukrainian"

    replied = update.message.reply_to_message
    replied_text = replied.text or replied.caption or ""
    url_match = URL_PATTERN.search(replied_text)

    status_msg = await update.message.reply_text("🔄 Читаю та аналізую...")

    content: Optional[str] = None
    url_error: Optional[str] = None

    if url_match:
        url = url_match.group(0).rstrip(".,;)")
        content = await _fetch_url_text(url)
        if content is None:
            url_error = f"Не вдалося завантажити сторінку ({url[:60]})."

    # Fallback text is the message minus any bare URL (no point asking GPT to summarize a URL string)
    non_url_text = URL_PATTERN.sub('', replied_text).strip()
    text_to_summarize = content or non_url_text or replied_text

    if not text_to_summarize:
        await status_msg.edit_text("❌ Немає тексту для підсумовування.")
        return

    if url_error:
        if non_url_text:
            await update.message.reply_text(f"⚠️ {url_error} Підсумовую текст повідомлення.")
        else:
            await status_msg.edit_text(f"❌ {url_error}")
            return

    summary = await _summarize_chunked(text_to_summarize, lang)

    try:
        await status_msg.edit_text(summary)
    except Exception:
        await update.message.reply_text(summary)
