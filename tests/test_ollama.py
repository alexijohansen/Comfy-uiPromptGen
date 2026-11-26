import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from promptgen.core import ollama_client


def test_strip_thinking():
    assert ollama_client.strip_thinking("<|channel>thought\nhmm<channel|>A cat.") == "A cat."
    assert ollama_client.strip_thinking("<think>x</think> B") == "B"
    assert ollama_client.strip_thinking("no marker <channel|>C") == "C"
    assert ollama_client.strip_thinking("plain") == "plain"


class FakeOllama(BaseHTTPRequestHandler):
    reject_think = False
    requests = []

    def do_GET(self):
        self._reply(200, {"models": [{"name": "b:latest"}, {"name": "a:latest"}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOllama.requests.append(body)
        if "think" in body and FakeOllama.reject_think:
            return self._reply(400, {"error": "model does not support thinking"})
        self._reply(200, {"response": "<|channel>thought\n...<channel|>REWRITTEN " + body["prompt"]})

    def _reply(self, code, data):
        self.send_response(code)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *args):
        pass


@pytest.fixture
def ollama():
    server = HTTPServer(("127.0.0.1", 0), FakeOllama)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    FakeOllama.requests, FakeOllama.reject_think = [], False
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_list_models_sorted(ollama):
    assert ollama_client.list_models(ollama) == ["a:latest", "b:latest"]


def test_list_models_unreachable_is_empty():
    assert ollama_client.list_models("http://127.0.0.1:9") == []


def test_generate_sends_think_false_and_cleans_reply(ollama):
    assert ollama_client.generate(ollama, "m", "do it", "a cat", seed=2**40 + 5, temperature=0.7) == "REWRITTEN a cat"
    sent = FakeOllama.requests[0]
    assert sent["think"] is False and sent["system"] == "do it" and sent["options"]["seed"] == 5


def test_generate_retries_without_think(ollama):
    FakeOllama.reject_think = True
    assert ollama_client.generate(ollama, "m", "i", "x", 1, 0.7) == "REWRITTEN x"
    assert "think" not in FakeOllama.requests[-1]


def test_generate_unreachable_raises():
    with pytest.raises(ollama_client.OllamaError, match="Could not reach"):
        ollama_client.generate("http://127.0.0.1:9", "m", "i", "x", 1, 0.7)
