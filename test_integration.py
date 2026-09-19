"""End-to-end checks for account, persistence, and every MoneyMate page."""

from datetime import date
import os

import pytest

import wsgi as webapp
import persistent_store as storage


@pytest.fixture
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATABASE_URL", "")
    monkeypatch.setattr(
        storage,
        "_path",
        lambda value: os.path.join(str(tmp_path), os.path.basename(str(value))),
    )
    return tmp_path


def csrf(client):
    client.get("/page1")
    with client.session_transaction() as flask_session:
        return flask_session["csrf_token"]


def post(client, path, data):
    payload = dict(data)
    with client.session_transaction() as flask_session:
        payload["csrf_token"] = flask_session["csrf_token"]
    return client.post(path, data=payload, follow_redirects=True)


def register_and_login(client, username="tester", password="secret12"):
    csrf(client)
    response = post(client, "/page1", {
        "action": "register",
        "username": username,
        "password": password,
    })
    assert response.status_code == 200
    response = post(client, "/page1", {
        "action": "login",
        "username": username,
        "password": password,
    })
    assert response.status_code == 200
    with client.session_transaction() as flask_session:
        assert flask_session["user"] == username
        assert flask_session.permanent


def test_complete_user_flow_and_all_pages(isolated_storage):
    client = webapp.app.test_client()
    register_and_login(client)

    response = post(client, "/page3", {
        "action": "add",
        "type": "income",
        "amount": "25000",
        "category": "เงินเดือน",
        "date": date.today().isoformat(),
        "description": "integration-income",
    })
    assert "integration-income" in response.get_data(as_text=True)

    response = post(client, "/page6", {
        "action": "budget",
        "period": "monthly",
        "amount": "12000",
    })
    assert response.status_code == 200

    response = post(client, "/page7", {
        "action": "add_goal",
        "name": "integration-goal",
        "target": "10000",
        "saved": "0",
        "deadline": "",
    })
    assert response.status_code == 200
    goals = storage.read_json("savings_data.json", [])
    goal_id = next(goal["id"] for goal in goals if goal["name"] == "integration-goal")

    response = post(client, "/page7", {
        "action": "add_saving",
        "goal_id": goal_id,
        "amount": "1500",
    })
    assert response.status_code == 200
    saved_goal = next(
        goal for goal in storage.read_json("savings_data.json", [])
        if goal["id"] == goal_id
    )
    assert saved_goal["saved"] == 1500

    response = post(client, "/page8", {
        "action": "save",
        "name": "integration-expense",
        "type": "expense",
        "amount": "250",
        "category": "อาหาร",
    })
    assert response.status_code == 200

    for page in ["/", "/page2", "/page3", "/page4", "/page5", "/page6",
                 "/page7", "/page8", "/page9", "/page11", "/team"]:
        response = client.get(page)
        assert response.status_code == 200, page
        assert "ยังไม่พร้อม" not in response.get_data(as_text=True), page

    with client.session_transaction() as flask_session:
        flask_session["is_admin"] = True
    assert client.get("/page10").status_code == 200


def test_account_and_data_survive_new_browser_session(isolated_storage):
    first_client = webapp.app.test_client()
    register_and_login(first_client, "remember-me", "secret12")
    post(first_client, "/page3", {
        "action": "add",
        "type": "income",
        "amount": "999",
        "category": "งานเสริม",
        "date": date.today().isoformat(),
        "description": "persistent-record",
    })

    second_client = webapp.app.test_client()
    csrf(second_client)
    response = post(second_client, "/page1", {
        "action": "login",
        "username": "remember-me",
        "password": "secret12",
    })
    assert response.status_code == 200
    dashboard = second_client.get("/page2").get_data(as_text=True)
    assert "999" in dashboard


def test_sidebar_is_single_open_accordion():
    source = open(
        os.path.join(os.path.dirname(__file__), "templates", "_money_base.html"),
        encoding="utf-8",
    ).read()
    assert "menuGroups.forEach" in source
    assert "other.open = false" in source
    assert "event.preventDefault()" in source
