"""Client tests using the `responses` library to mock HTTP — no live site."""

from __future__ import annotations

import responses

from frappe_smoke.client import FrappeAPIError, FrappeClient

BASE = "http://site.localhost:8000"


@responses.activate
def test_login_sets_user_and_host_header():
    responses.add(responses.POST, f"{BASE}/api/method/login", json={"message": "Logged In"})
    client = FrappeClient(BASE)
    user = client.login("Administrator", "secret")
    assert user == "Administrator"
    assert client.logged_in_user == "Administrator"
    # Host header inferred from URL host for multi-tenant routing.
    assert client.session.headers["Host"] == "site.localhost"


@responses.activate
def test_get_versions_returns_message_payload():
    payload = {"message": {"frappe": {"version": "16.0.0", "branch": "version-16"}}}
    responses.add(
        responses.POST,
        f"{BASE}/api/method/frappe.utils.change_log.get_versions",
        json=payload,
    )
    client = FrappeClient(BASE)
    versions = client.get_versions()
    assert versions["frappe"]["version"] == "16.0.0"


@responses.activate
def test_insert_posts_to_resource():
    responses.add(
        responses.POST,
        f"{BASE}/api/resource/ToDo",
        json={"data": {"name": "abc123", "description": "x"}},
    )
    client = FrappeClient(BASE)
    doc = client.insert({"doctype": "ToDo", "description": "x"})
    assert doc["name"] == "abc123"


@responses.activate
def test_token_auth_header():
    client = FrappeClient(BASE)
    client.use_token("KEY", "SECRET")
    assert client.session.headers["Authorization"] == "token KEY:SECRET"


@responses.activate
def test_error_raises_frappe_api_error():
    responses.add(
        responses.GET,
        f"{BASE}/api/resource/ToDo/missing",
        json={"exception": "DoesNotExistError"},
        status=404,
    )
    client = FrappeClient(BASE)
    try:
        client.get_doc("ToDo", "missing")
    except FrappeAPIError as exc:
        assert exc.status == 404
        assert "DoesNotExistError" in str(exc.server_messages)
    else:  # pragma: no cover
        raise AssertionError("expected FrappeAPIError")
