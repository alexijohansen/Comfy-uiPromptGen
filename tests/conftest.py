import pytest

from promptgen.core import counting, ollama_client


@pytest.fixture(autouse=True)
def _fresh_state():
    counting.reset_all()
    ollama_client._model_cache.clear()
    yield
