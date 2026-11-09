"""Gemini embedder (feature set G) without calling Google: the HTTP layer is faked."""
import numpy as np
import pytest

from pipeline import features


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code, self._payload = status, payload or {}

    def json(self):
        return self._payload


def fake_post_factory(calls, fail_first=0):
    def fake_post(url, json, headers, timeout):
        calls.append((url, json, headers))
        if len(calls) <= fail_first:
            return FakeResponse(429)
        n = len(json["requests"])
        rng = np.random.default_rng(len(calls))
        return FakeResponse(200, {"embeddings": [{"values": rng.normal(size=8).tolist()} for _ in range(n)]})
    return fake_post


def test_gemini_batches_reads_key_from_env_and_retries(monkeypatch):
    import requests
    import time
    calls = []
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(requests, "post", fake_post_factory(calls, fail_first=1))
    monkeypatch.setattr(time, "sleep", lambda s: None)
    toks = [["word"] * 200, ["other"] * 50]          # 3 chunks + 1 chunk
    E = features.GeminiEmbedder(features.GEMINI_MODEL).raw(toks, batch_size=2)
    assert E.shape == (2, 8) and np.allclose(np.linalg.norm(E, axis=1), 1)
    assert all(h["x-goog-api-key"] == "test-key" for _, _, h in calls)
    assert all(r["taskType"] == "CLUSTERING" for _, b, _ in calls for r in b["requests"])
    assert len(calls) == 3                            # one 429 retried, then batches of 2 + 2


def test_gemini_without_key_or_service_raises_a_clear_error(monkeypatch):
    import requests
    import time
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(features.EmbeddingServiceError, match="GEMINI_API_KEY"):
        features.GeminiEmbedder().raw([["a"] * 30])
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse(403))
    monkeypatch.setattr(time, "sleep", lambda s: None)
    with pytest.raises(features.EmbeddingServiceError, match="403"):
        features.GeminiEmbedder().raw([["a"] * 30])


def test_gemini_embedder_pickles_without_the_key(monkeypatch):
    import pickle
    monkeypatch.setenv("GEMINI_API_KEY", "secret-value")
    emb = features.GeminiEmbedder()
    assert b"secret-value" not in pickle.dumps(emb)
