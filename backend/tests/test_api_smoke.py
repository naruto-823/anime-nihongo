def test_openapi_lists_all_routers(client):
    paths = client.get("/openapi.json").json()["paths"]
    for prefix in ("/api/series", "/api/episodes/{episode_id}",
                   "/api/study/today", "/api/srs/due",
                   "/api/grammar/checklist", "/api/conversation/turn",
                   "/api/progress"):
        assert prefix in paths, f"缺少路由 {prefix}"
