import pytest

from lora_dev.provider import _ollama_plan


@pytest.mark.asyncio
async def test_provider_module_exposes_local_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:1")
    assert callable(_ollama_plan)
