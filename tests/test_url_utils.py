import asyncio
import re
import time
import pytest

from main import sanitize_url, shorten_url, _url_shortener_cache, _shortener_calls, _SHORTENER_MAX_CALLS_PER_MINUTE

class DummyShortener:
    def __init__(self, mapping=None):
        self.called = 0
        self.mapping = mapping or {}
    @property
    def tinyurl(self):
        return self
    def short(self, url):
        self.called += 1
        return self.mapping.get(url, f"short_{url}")

@pytest.fixture(autouse=True)
def clear_cache_and_calls(monkeypatch):
    # Clear cache and calls before each test
    _url_shortener_cache.clear()
    _shortener_calls.clear()
    # Reset rate limit to small number for tests
    monkeypatch.setenv('SHORTENER_MAX_CALLS_PER_MINUTE', '2')
    # Monkeypatch constant
    from importlib import reload
    import main
    reload(main)
    yield

@pytest.mark.parametrize("url,expected", [
    ("http://example.com/path", "http://example.com/path"),
    ("https://example.com", "https://example.com"),
])
def test_sanitize_url_valid(url, expected):
    assert sanitize_url(url) == expected

@pytest.mark.parametrize("url", [
    "http://127.0.0.1/path",  # IP address
    "http://user:pass@example.com/path",  # with credentials
    "http://exa_mple.com/path",  # invalid hostname char
])
def test_sanitize_url_invalid(url):
    assert sanitize_url(url) == ""

@pytest.mark.asyncio
async def test_shorten_url_short():
    url = "http://a.co/short"
    result = await shorten_url(url)
    assert result == url

@pytest.mark.asyncio
async def test_shorten_url_long_and_cache(monkeypatch):
    # prepare a dummy shortener
    # URL length must exceed 110 characters to trigger shortening
    base = "http://long.url/"
    path = "x" * 200
    url = base + path
    # prepare a dummy shortener mapping this URL to 'tiny'
    dummy = DummyShortener({url: "tiny"})
    monkeypatch.setattr('pyshorteners.Shortener', lambda timeout=None: dummy)
    # first call should shorten using dummy mapping
    result1 = await shorten_url(url)
    assert result1 == "tiny"
    # second call uses cache; mapping not invoked again
    result2 = await shorten_url(url)
    assert result2 == "tiny"
    assert dummy.called == 1

@pytest.mark.asyncio
async def test_shorten_url_rate_limit(monkeypatch):
    # set max calls to 1 and reload constants
    monkeypatch.setenv('SHORTENER_MAX_CALLS_PER_MINUTE', '1')
    # reload main module to pick up new rate limit
    import importlib
    import main
    importlib.reload(main)
    # Create two long URLs
    base = "http://rate.limit/"
    long1 = base + "a" * 200
    long2 = base + "b" * 200
    # patch shortener mapping
    dummy = DummyShortener({long1: "s1", long2: "s2"})
    monkeypatch.setattr('pyshorteners.Shortener', lambda timeout=None: dummy)
    # first long URL shortened
    r1 = await main.shorten_url(long1)
    assert r1 == "s1"
    # second long URL should be rate limited (max 1 per minute)
    r2 = await main.shorten_url(long2)
    assert r2 == long2