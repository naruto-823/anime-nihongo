def test_register_login_and_me(client):
    registered = client.post("/api/auth/register", json={"username": "naruto", "password": "secret12"})
    assert registered.status_code == 200
    assert "token" not in registered.json()
    assert registered.cookies.get("nihongo_session")
    me = client.get("/api/auth/me")
    assert me.json()["username"] == "naruto"

    login = client.post("/api/auth/login", json={"username": "naruto", "password": "secret12"})
    assert login.status_code == 200
    assert login.cookies.get("nihongo_session")
    assert client.post("/api/auth/login", json={"username": "naruto", "password": "badpass"}).status_code == 401


def test_duplicate_username(client):
    body = {"username": "same_user", "password": "secret12"}
    assert client.post("/api/auth/register", json=body).status_code == 200
    assert client.post("/api/auth/register", json=body).status_code == 409


def test_logout_clears_cookie_and_legacy_bearer_is_upgraded(client):
    from app.services.auth import create_token

    registered = client.post("/api/auth/register", json={"username": "legacy", "password": "secret12"})
    user_id = registered.json()["user"]["id"]
    client.cookies.clear()
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {create_token(user_id)}"})
    assert me.status_code == 200
    assert me.cookies.get("nihongo_session")
    logged_out = client.post("/api/auth/logout")
    assert logged_out.status_code == 204
    assert logged_out.headers["set-cookie"].startswith("nihongo_session=")
