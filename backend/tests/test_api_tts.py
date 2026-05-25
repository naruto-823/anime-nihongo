from unittest.mock import MagicMock, patch

import httpx

from app.api import tts as tts_module


def _make_client_mock(audio_query_json, synthesis_content):
    """Return a mock httpx.Client context manager that simulates VOICEVOX."""
    mock_client = MagicMock()
    mock_client.__enter__ = lambda s: s
    mock_client.__exit__ = MagicMock(return_value=False)

    q_resp = MagicMock()
    q_resp.status_code = 200
    q_resp.raise_for_status = MagicMock()
    q_resp.json = MagicMock(return_value=audio_query_json)

    a_resp = MagicMock()
    a_resp.status_code = 200
    a_resp.raise_for_status = MagicMock()
    a_resp.content = synthesis_content
    a_resp.headers = {"Content-Type": "audio/wav"}

    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        if url.endswith("/audio_query"):
            return q_resp
        if url.endswith("/synthesis"):
            return a_resp
        raise ValueError(f"Unexpected URL: {url}")

    mock_client.post = fake_post
    return mock_client, calls


def test_synthesize_proxies_voicevox(client):
    mock_client, calls = _make_client_mock({"q": "x"}, b"WAVDATA")
    with patch("app.api.tts.httpx.Client", return_value=mock_client):
        resp = client.post("/api/tts/synthesize",
                           json={"text": "こんにちは", "speaker": 3})
    assert resp.status_code == 200
    assert resp.content == b"WAVDATA"
    assert resp.headers["content-type"] == "audio/wav"
    assert any("/audio_query" in c for c in calls)
    assert any("/synthesis" in c for c in calls)


def test_synthesize_returns_503_when_voicevox_offline(client):
    mock_client = MagicMock()
    mock_client.__enter__ = lambda s: s
    mock_client.__exit__ = MagicMock(return_value=False)

    def fake_post(url, **kwargs):
        raise httpx.ConnectError("connection refused")

    mock_client.post = fake_post

    with patch("app.api.tts.httpx.Client", return_value=mock_client):
        resp = client.post("/api/tts/synthesize", json={"text": "テスト"})
    assert resp.status_code == 503
    assert "VOICEVOX" in resp.json()["detail"]


def test_synthesize_rejects_empty_text(client):
    resp = client.post("/api/tts/synthesize", json={"text": "  "})
    assert resp.status_code == 400


def test_speakers_returns_503_when_offline(client, monkeypatch):
    def fake_get(url, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", fake_get)
    resp = client.get("/api/tts/speakers")
    assert resp.status_code == 503

    # The import keeps tts_module referenced (silences any unused-import linter)
    assert tts_module.DEFAULT_SPEAKER == 3
