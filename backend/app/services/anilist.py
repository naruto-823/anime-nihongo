"""AniList GraphQL 客户端。公开免 key 端点 https://graphql.anilist.co。

单部番一次调用，无 batch，无 retry —— 单用户本地无并发压力。
返回主角 + 前若干配角的姓名与头像 URL。
"""
import httpx

API_BASE = "https://graphql.anilist.co"
TIMEOUT = 10.0

_QUERY = """
query ($search: String) {
  Media(search: $search, type: ANIME) {
    id
    characters(sort: ROLE, page: 1, perPage: 5) {
      edges {
        role
        node {
          name { full native }
          image { large }
        }
      }
    }
  }
}
""".strip()


class AniListError(RuntimeError):
    pass


def fetch_series_metadata(title: str, http: httpx.Client | None = None) -> dict | None:
    """查 AniList，返回 {"anilist_id": int, "characters": [...]}；无匹配返回 None。

    HTTP / GraphQL / JSON 错误一律抛 AniListError 由调用方处理。
    """
    owns_client = http is None
    if http is None:
        http = httpx.Client(base_url=API_BASE, timeout=TIMEOUT)
    try:
        resp = http.post("/", json={"query": _QUERY, "variables": {"search": title}})
    except httpx.HTTPError as exc:
        raise AniListError(f"AniList 网络错误: {exc}") from exc
    finally:
        if owns_client:
            http.close()

    if resp.status_code != 200:
        raise AniListError(
            f"AniList 返回 {resp.status_code}: {resp.text[:200]}"
        )
    try:
        body = resp.json()
    except ValueError as exc:
        raise AniListError(f"AniList 响应非 JSON: {resp.text[:200]}") from exc

    if body.get("errors"):
        raise AniListError(f"AniList GraphQL 错误: {body['errors']}")

    media = (body.get("data") or {}).get("Media")
    if media is None:
        return None

    chars = []
    for edge in (media.get("characters") or {}).get("edges") or []:
        node = edge.get("node") or {}
        name = node.get("name") or {}
        image = node.get("image") or {}
        chars.append({
            "name_en": name.get("full"),
            "name_jp": name.get("native"),
            "image_url": image.get("large"),
            "role": edge.get("role"),
        })

    return {"anilist_id": media.get("id"), "characters": chars}
