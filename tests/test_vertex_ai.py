"""Vertex AI embedder (feature set V) without calling Google: the HTTP layer and token are faked."""
import numpy as np

from pipeline import features


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code, self._payload, self.text = status, payload or {}, ""

    def json(self):
        return self._payload


def test_vertex_embeds_and_refreshes_an_expired_token(monkeypatch):
    import requests
    import time
    calls, tokens = [], iter(["old-token", "new-token"])

    def fake_post(url, json, headers, timeout):
        calls.append(headers["Authorization"])
        if len(calls) == 1:
            return FakeResponse(401)
        rng = np.random.default_rng(len(calls))
        return FakeResponse(200, {"predictions": [{"embeddings": {"values": rng.normal(size=8).tolist()}}
                                                  for _ in json["instances"]]})

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    emb = features.VertexAIEmbedder()
    monkeypatch.setattr(emb, "_get_token", lambda: next(tokens))
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    E = emb.raw([["vedic", "sanskrit", "grantha"] * 10], batch_size=1)
    assert E.shape == (1, 8) and np.allclose(np.linalg.norm(E, axis=1), 1)
    assert calls == ["Bearer old-token", "Bearer new-token"]     # the 401 was retried with a fresh token


def test_vertex_embedder_pickles_without_the_token():
    import pickle
    emb = features.VertexAIEmbedder()
    emb._token, emb._token_expiry = "secret-access-token", 9e9
    restored = pickle.loads(pickle.dumps(emb))
    assert b"secret-access-token" not in pickle.dumps(emb)
    assert restored._token is None and restored._token_expiry == 0


def test_vertex_needs_a_project(monkeypatch):
    import pytest
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(features.EmbeddingServiceError, match="GOOGLE_CLOUD_PROJECT"):
        features.VertexAIEmbedder()._url()
