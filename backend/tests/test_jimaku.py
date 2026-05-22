import httpx
import pytest

from app.services.jimaku import JimakuClient, JimakuError


def _client(handler):
    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, base_url="https://jimaku.cc/api")
    return JimakuClient(token="t", http=http)


def test_search_entries():
    def handler(request):
        assert request.url.path == "/api/entries/search"
        assert request.headers["Authorization"] == "t"
        return httpx.Response(200, json=[{"id": 9, "name": "Test Anime"}])

    entries = _client(handler).search_entries("test")
    assert entries[0]["id"] == 9


def test_list_files():
    def handler(request):
        assert request.url.path == "/api/entries/9/files"
        return httpx.Response(200, json=[{"name": "ep1.srt", "url": "https://x/ep1.srt"}])

    files = _client(handler).list_files(9)
    assert files[0]["name"] == "ep1.srt"


def test_download_file():
    def handler(request):
        if request.url.host == "x":
            return httpx.Response(200, text="1\n00:00:01,000 --> 00:00:02,000\nやあ\n")
        return httpx.Response(404)

    content = _client(handler).download_file("https://x/ep1.srt")
    assert "やあ" in content


def test_error_on_non_200():
    def handler(request):
        return httpx.Response(500, text="boom")

    with pytest.raises(JimakuError):
        _client(handler).search_entries("test")
