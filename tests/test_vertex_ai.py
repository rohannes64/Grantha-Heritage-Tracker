import numpy as np
import pytest
from pipeline.features import VertexAIEmbedder

def test_vertex_ai_embedder():
    embedder = VertexAIEmbedder()
    tokens = ["vedic", "sanskrit", "heritage", "grantha", "manuscript", "ancient", "history", "text", "shloka", "rigveda"]
    result = embedder.raw([tokens], batch_size=1)
    assert isinstance(result, np.ndarray)
    assert result.shape == (1, 768)
    norm = np.linalg.norm(result[0])
    assert pytest.approx(norm, 0.01) == 1.0
