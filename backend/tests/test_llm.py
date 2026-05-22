import pytest

from app.services import llm
from app.services.llm import LLMError, extract_json


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_in_code_fence():
    text = 'ここ:\n```json\n{"a": [1, 2]}\n```\n以上'
    assert extract_json(text) == {"a": [1, 2]}


def test_extract_json_raises_on_garbage():
    with pytest.raises(LLMError):
        extract_json("no json here")


def test_call_json_uses_client(monkeypatch):
    class FakeBlock:
        text = '{"ok": true}'

    class FakeResp:
        content = [FakeBlock()]

    class FakeMessages:
        def create(self, **kwargs):
            assert kwargs["model"] == "test-model"
            assert kwargs["system"] == "sys"
            return FakeResp()

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(llm, "_client", lambda: FakeClient())
    out = llm.call_json(system="sys", user="hi", model="test-model")
    assert out == {"ok": True}


def test_call_json_wraps_network_error(monkeypatch):
    class FailingMessages:
        def create(self, **kwargs):
            raise ConnectionError("network down")

    class FakeClient:
        messages = FailingMessages()

    monkeypatch.setattr(llm, "_client", lambda: FakeClient())
    with pytest.raises(LLMError, match="LLM 调用失败"):
        llm.call_json(system="s", user="u", model="m")


def test_call_json_rejects_non_object_json(monkeypatch):
    class FakeBlock:
        text = "[1, 2, 3]"

    class FakeResp:
        content = [FakeBlock()]

    class FakeMessages:
        def create(self, **kwargs):
            return FakeResp()

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(llm, "_client", lambda: FakeClient())
    with pytest.raises(LLMError):
        llm.call_json(system="s", user="u", model="m")
