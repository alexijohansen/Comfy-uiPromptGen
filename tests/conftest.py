import pytest

from promptgen.core import counting, ollama_client, templating


@pytest.fixture(autouse=True)
def _fresh_state():
    counting.reset_all()
    templating.reset_bags()
    ollama_client._model_cache.clear()
    yield
