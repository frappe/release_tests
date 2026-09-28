"""HTTP client for the Frappe REST API.

A thin wrapper over a ``requests.Session`` that handles the two things every
suite needs: authentication (token or login) and CRUD/method calls. It is
deliberately framework-agnostic — it only speaks HTTP, so the same client works
against a local bench site or a remote press-deployed site.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import requests


class FrappeAPIError(Exception):
    """Raised when the Frappe server returns a non-2xx response.

    Carries the HTTP status and any server-side messages so failures surface
    cleanly in the release-test report instead of as opaque tracebacks.
    """

    def __init__(self, message: str, status: int | None = None, server_messages: Any = None):
        super().__init__(message)
        self.status = status
        self.server_messages = server_messages


class FrappeClient:
    """Authenticated HTTP client bound to a single Frappe site."""

    def __init__(
        self,
        url: str,
        *,
        host_header: str | None = None,
        timeout: int = 30,
    ):
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        # Don't read proxy/CA config from the environment or the OS. We hit known
        # URLs directly, and on macOS the system-proxy lookup (_scproxy) aborts
        # with SIGABRT when requests runs inside a forked process (e.g. an RQ
        # work-horse). Disabling it keeps runs working under background workers.
        self.session.trust_env = False
        # Local benches are multi-tenant by Host header. Send an explicit Host so
        # the correct site is served regardless of local DNS / hosts entries.
        host = host_header or urlsplit(self.url).hostname
        if host:
            self.session.headers["Host"] = host
        self.session.headers["Accept"] = "application/json"
        self.logged_in_user: str | None = None
        # Set by config.connect() from the Target. Default False so a client built
        # directly (tests, ad-hoc scripts) can never provision customisations.
        self.allow_customisations = False
        # Counts submitted documents — a proxy for "transactions created" in a run.
        self.submitted_count = 0

    # ------------------------------------------------------------------ auth
    def use_token(self, api_key: str, api_secret: str) -> None:
        """Authenticate every request with a Frappe API key/secret pair."""
        self.session.headers["Authorization"] = f"token {api_key}:{api_secret}"

    def login(self, username: str, password: str) -> str:
        """Perform a real ``/api/method/login`` and retain the session cookie.

        This is itself the first release check the user cares about — proving the
        auth + web stack is up. Returns the logged-in user on success.
        """
        resp = self.session.post(
            f"{self.url}/api/method/login",
            data={"usr": username, "pwd": password},
            timeout=self.timeout,
        )
        self._raise_for_status(resp)
        self.logged_in_user = username
        return username

    # -------------------------------------------------------------- requests
    def get_versions(self) -> dict[str, dict[str, Any]]:
        """Return ``{app: {title, branch, version}}`` for every installed app.

        Single source of truth for both app gating (presence) and version
        gating (the ``version`` field). Uses Frappe's whitelisted endpoint.
        """
        data = self.call("frappe.utils.change_log.get_versions")
        return data or {}

    def get_doc(self, doctype: str, name: str) -> dict[str, Any]:
        resp = self.session.get(
            f"{self.url}/api/resource/{doctype}/{requests.utils.quote(name, safe='')}",
            timeout=self.timeout,
        )
        self._raise_for_status(resp)
        return resp.json().get("data", {})

    def get_list(
        self,
        doctype: str,
        *,
        filters: list | dict | None = None,
        fields: list[str] | None = None,
        order_by: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit_page_length": limit}
        if filters is not None:
            params["filters"] = _json(filters)
        if fields is not None:
            params["fields"] = _json(fields)
        if order_by is not None:
            params["order_by"] = order_by
        resp = self.session.get(
            f"{self.url}/api/resource/{doctype}",
            params=params,
            timeout=self.timeout,
        )
        self._raise_for_status(resp)
        return resp.json().get("data", [])

    def insert(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Insert a document (draft). ``doc`` must include ``doctype``."""
        doctype = doc["doctype"]
        resp = self.session.post(
            f"{self.url}/api/resource/{doctype}",
            json=doc,
            timeout=self.timeout,
        )
        self._raise_for_status(resp)
        return resp.json().get("data", {})

    def submit(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Submit a document via the whitelisted ``frappe.client.submit``."""
        result = self.call("frappe.client.submit", doc=_json(doc))
        self.submitted_count += 1
        return result

    def cancel(self, doctype: str, name: str) -> dict[str, Any]:
        """Cancel a submitted document."""
        return self.call("frappe.client.cancel", doctype=doctype, name=name)

    def delete(self, doctype: str, name: str) -> Any:
        """Delete a document."""
        return self.call("frappe.client.delete", doctype=doctype, name=name)

    def call(self, method: str, **kwargs: Any) -> Any:
        """POST to ``/api/method/<method>`` and return the ``message`` payload."""
        resp = self.session.post(
            f"{self.url}/api/method/{method}",
            data=kwargs or None,
            timeout=self.timeout,
        )
        self._raise_for_status(resp)
        body = resp.json()
        return body.get("message", body)

    # --------------------------------------------------------------- helpers
    def _raise_for_status(self, resp: requests.Response) -> None:
        if resp.ok:
            return
        server_messages = None
        try:
            payload = resp.json()
            server_messages = (
                payload.get("_server_messages")
                or payload.get("exception")
                or payload.get("message")
            )
        except ValueError:
            server_messages = resp.text[:500]
        raise FrappeAPIError(
            f"{resp.request.method} {resp.url} -> {resp.status_code}: {server_messages}",
            status=resp.status_code,
            server_messages=server_messages,
        )


def _json(value: Any) -> str:
    import json

    return json.dumps(value, default=str)
