import pytest
from requests.adapters import HTTPAdapter
from pipeline.ia import IAClient
from pipeline import config

def test_ia_client_pool_size_and_pacing():
    client = IAClient(interval=0.2)
    adapter = client.s.get_adapter("https://archive.org")
    assert isinstance(adapter, HTTPAdapter)
    assert adapter._pool_maxsize >= 25
    assert client.interval == 0.2
