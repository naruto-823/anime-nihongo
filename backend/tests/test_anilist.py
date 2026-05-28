import httpx
import pytest

from app.services import anilist


def _client_with(handler):
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport, base_url=anilist.API_BASE)


def test_fetch_returns_id_and_characters_on_match():
    def handler(request):
        assert request.url.path == "/"
        body = request.read()
        assert b"$search" in body
        return httpx.Response(200, json={
            "data": {"Media": {
                "id": 130003,
                "characters": {"edges": [
                    {"role": "MAIN", "node": {
                        "name": {"full": "Hitori Gotoh", "native": "後藤ひとり"},
                        "image": {"large": "https://img.anili.st/h.png"}}},
                    {"role": "SUPPORTING", "node": {
                        "name": {"full": "Nijika Ijichi", "native": "伊地知虹夏"},
                        "image": {"large": "https://img.anili.st/n.png"}}},
                ]}
            }}
        })

    with _client_with(handler) as http:
        out = anilist.fetch_series_metadata("Bocchi the Rock", http=http)

    assert out is not None
    assert out["anilist_id"] == 130003
    assert out["characters"][0] == {
        "name_en": "Hitori Gotoh", "name_jp": "後藤ひとり",
        "image_url": "https://img.anili.st/h.png", "role": "MAIN",
    }
    assert out["characters"][1]["role"] == "SUPPORTING"


def test_fetch_returns_none_on_no_match():
    def handler(request):
        return httpx.Response(200, json={"data": {"Media": None}})

    with _client_with(handler) as http:
        assert anilist.fetch_series_metadata("no-such-anime-xxxx", http=http) is None


def test_fetch_raises_on_http_5xx():
    def handler(request):
        return httpx.Response(503, text="upstream down")

    with _client_with(handler) as http:
        with pytest.raises(anilist.AniListError):
            anilist.fetch_series_metadata("x", http=http)


def test_fetch_raises_on_graphql_errors():
    def handler(request):
        return httpx.Response(200, json={
            "errors": [{"message": "validation failed"}],
            "data": None,
        })

    with _client_with(handler) as http:
        with pytest.raises(anilist.AniListError):
            anilist.fetch_series_metadata("x", http=http)


def test_fetch_handles_missing_native_name():
    def handler(request):
        return httpx.Response(200, json={"data": {"Media": {
            "id": 1,
            "characters": {"edges": [{"role": "MAIN", "node": {
                "name": {"full": "Some Char", "native": None},
                "image": {"large": "https://x/c.png"}}}]}}}})

    with _client_with(handler) as http:
        out = anilist.fetch_series_metadata("x", http=http)
    assert out["characters"][0]["name_jp"] is None
    assert out["characters"][0]["name_en"] == "Some Char"
