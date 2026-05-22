import httpx

API_BASE = "https://jimaku.cc/api"


class JimakuError(RuntimeError):
    pass


class JimakuClient:
    """Jimaku 字幕 API 客户端。鉴权：Authorization 头携带 API token。"""

    def __init__(self, token: str, http: httpx.Client | None = None):
        self._token = token
        self._http = http or httpx.Client(base_url=API_BASE, timeout=30.0)

    def _get(self, path: str, **kwargs) -> httpx.Response:
        resp = self._http.get(path, headers={"Authorization": self._token}, **kwargs)
        if resp.status_code != 200:
            raise JimakuError(f"Jimaku {path} 返回 {resp.status_code}: {resp.text[:200]}")
        return resp

    def search_entries(self, query: str) -> list[dict]:
        return self._get("/entries/search", params={"query": query}).json()

    def list_files(self, entry_id: int) -> list[dict]:
        return self._get(f"/entries/{entry_id}/files").json()

    def download_file(self, url: str) -> str:
        resp = self._http.get(url, headers={"Authorization": self._token})
        if resp.status_code != 200:
            raise JimakuError(f"下载字幕失败 {resp.status_code}: {url} — {resp.text[:200]}")
        return resp.text

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "JimakuClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
