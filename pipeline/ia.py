"""Polite Internet Archive client: rate-limited, retried, cached."""
import gzip
import json
import time
from pathlib import Path

import requests

from . import config


class IAClient:
    def __init__(self, interval: float = config.REQUEST_INTERVAL, cache_dir: Path = config.CACHE_DIR):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = config.USER_AGENT
        self.interval = interval
        self.cache_dir = cache_dir
        self._last = 0.0

    def _get(self, url: str, params=None, stream=False, tries: int = 5) -> requests.Response:
        for attempt in range(tries):
            wait = self.interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                r = self.s.get(url, params=params, timeout=60, stream=stream)
            except requests.RequestException:
                time.sleep(2 ** attempt * 2)
                continue
            if r.status_code == 200:
                return r
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(int(r.headers.get("Retry-After", 2 ** attempt * 5)))
                continue
            r.raise_for_status()
        raise RuntimeError(f"gave up after {tries} tries: {url}")

    # -- search -------------------------------------------------------------
    def scrape(self, query: str, fields: list[str], page_size: int = 10000):
        """Yield every item matching `query` (cursor-paged scrape API)."""
        cursor = None
        while True:
            params = {"q": query, "fields": ",".join(fields), "count": page_size}
            if cursor:
                params["cursor"] = cursor
            d = self._get(config.IA_SEARCH, params=params).json()
            yield from d.get("items", [])
            cursor = d.get("cursor")
            if not cursor:
                return

    # -- items --------------------------------------------------------------
    def metadata(self, identifier: str) -> dict:
        path = self.cache_dir / "metadata" / f"{identifier}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        d = self._get(config.IA_METADATA.format(id=identifier)).json()
        if not d or "metadata" not in d:
            raise RuntimeError(f"no metadata for {identifier}")
        keep = {"metadata": d["metadata"],
                "files": [{"name": f["name"], "format": f.get("format"), "size": f.get("size")}
                          for f in d.get("files", [])]}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(keep, ensure_ascii=False), encoding="utf-8")
        return keep

    def page_image(self, identifier: str, leaf: int, dest: Path, width: int = config.PAGE_WIDTH) -> Path:
        if dest.exists() and dest.stat().st_size > 0:
            return dest
        r = self._get(config.IA_PAGE.format(id=identifier, leaf=leaf, width=width))
        if not r.headers.get("Content-Type", "").startswith("image/"):
            raise RuntimeError(f"not an image: {identifier} leaf {leaf}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".part")
        tmp.write_bytes(r.content)
        tmp.replace(dest)
        return dest

    def ia_page_texts(self, identifier: str, searchtext: str, pageindex: str) -> list[str]:
        """The archive's own OCR, split per page (only items with hOCR search text)."""
        cache = self.cache_dir / "ia_ocr" / f"{identifier}.json"
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))
        text = gzip.decompress(self._get(config.IA_DOWNLOAD.format(id=identifier, name=searchtext)).content
                               ).decode("utf-8", errors="replace")
        index = json.loads(gzip.decompress(
            self._get(config.IA_DOWNLOAD.format(id=identifier, name=pageindex)).content))
        pages = [text[start:end] for start, end, *_ in index]
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
        return pages
