def test_register_login_and_me(client):
    registered = client.post("/api/auth/register", json={"username": "naruto", "password": "secret12"})
    assert registered.status_code == 200
    token = registered.json()["token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["username"] == "naruto"

    login = client.post("/api/auth/login", json={"username": "naruto", "password": "secret12"})
    assert login.status_code == 200
    assert client.post("/api/auth/login", json={"username": "naruto", "password": "badpass"}).status_code == 401


def test_duplicate_username(client):
    body = {"username": "same_user", "password": "secret12"}
    assert client.post("/api/auth/register", json=body).status_code == 200
    assert client.post("/api/auth/register", json=body).status_code == 409
