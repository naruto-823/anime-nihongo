from app.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.anthropic_model == "claude-sonnet-4-6"
    assert s.database_url.startswith("sqlite")


def test_validate_ai_false_when_unset():
    s = Settings(_env_file=None, anthropic_api_key="")
    assert s.validate_ai() is False


def test_validate_ai_true_when_set():
    s = Settings(_env_file=None, anthropic_api_key="real-key")
    assert s.validate_ai() is True
