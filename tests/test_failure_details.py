"""Failure details, precheck skipping, suite selection and the check helpers."""

from __future__ import annotations

import pytest

from release_tests.checks import expect_allowed, expect_denied, expect_rejected
from release_tests.client import FrappeAPIError
from release_tests.personas import Persona
from release_tests.report import write_failures
from release_tests.runner import TargetResult, run_suite, suite_selected
from release_tests.suites.base import CheckFailed, ReleaseSuite, Step


class _Who:
    """Stands in for a persona session."""

    persona = Persona("sales", "rt.sales@example.com", "RT Sales", ("Sales User",))
    logged_in_user = None


def _raise(exc):
    def fn():
        raise exc

    return fn


def _denied():
    return FrappeAPIError("403: You do not have access to this document", status=403)


def test_check_failed_details_reach_step_result(fake_client):
    class Fails(ReleaseSuite):
        name = "fails"

        def build_steps(self, versions):
            def step(client, ctx):
                raise CheckFailed(
                    "export refused",
                    expected="refused",
                    actual="allowed",
                    user="rt.reader@example.com",
                    roles=["RT Reader"],
                    endpoint="export_query",
                    guards="frappe#42577",
                )

            return [Step("export", step)]

    result = run_suite(fake_client(), Fails(), {})
    details = result.steps[0].details
    assert result.status == "fail"
    assert details["user"] == "rt.reader@example.com"
    assert details["roles"] == ["RT Reader"]
    assert details["expected"] == "refused" and details["actual"] == "allowed"
    assert details["guards"] == "frappe#42577"


def test_unexpected_api_error_still_reports_server_message(fake_client):
    class Errors(ReleaseSuite):
        name = "errors"

        def build_steps(self, versions):
            return [
                Step(
                    "x", lambda c, ctx: _raise(FrappeAPIError("boom", 500, "Traceback… KeyError"))()
                )
            ]

    details = run_suite(fake_client(), Errors(), {}).steps[0].details
    assert "HTTP 500" in details["actual"]


def test_precheck_reason_skips_suite_with_reason(fake_client):
    class NotHere(ReleaseSuite):
        name = "not_here"

        def precheck(self, client):
            return "not a polished site"

        def build_steps(self, versions):  # pragma: no cover - must not run
            raise AssertionError("steps built despite precheck skip")

    result = run_suite(fake_client(), NotHere(), {})
    assert result.status == "skip"
    assert result.skip_reason == "not a polished site"
    assert result.steps == []


@pytest.mark.parametrize(
    ("pattern", "name", "selected"),
    [
        (None, "anything", True),
        ("v16p_security", "v16p_security", True),
        ("v16p_*", "v16p_erpnext", True),
        ("v16p_*", "erpnext", False),
        ("core_frappe, v16p_hrms*", "v16p_hrms_security", True),
        ("core_frappe, v16p_hrms*", "erpnext", False),
    ],
)
def test_suite_selected(pattern, name, selected):
    assert suite_selected(name, pattern) is selected


def test_expect_denied_passes_on_permission_error():
    expect_denied(_Who(), "reader exports", _raise(_denied()), endpoint="export_query")


def test_expect_denied_fails_when_allowed_and_names_the_user():
    with pytest.raises(CheckFailed) as err:
        expect_denied(_Who(), "reader exports", lambda: None, endpoint="export_query")
    details = err.value.details
    assert details["user"] == "rt.sales@example.com"
    assert details["roles"] == ["Sales User"]
    assert "succeeded" in details["actual"]


def test_expect_denied_does_not_accept_a_server_error_as_denial():
    with pytest.raises(CheckFailed) as err:
        expect_denied(_Who(), "x", _raise(FrappeAPIError("500", 500, "KeyError")), endpoint="e")
    assert "HTTP 500" in err.value.details["actual"]


def test_expect_allowed_reports_server_message():
    with pytest.raises(CheckFailed) as err:
        expect_allowed(_Who(), "save own ToDo", _raise(_denied()), endpoint="frappe.client.save")
    assert err.value.details["expected"] == "allowed"
    assert "HTTP 403" in err.value.details["actual"]


def test_expect_rejected_matches_message():
    exc = FrappeAPIError("417: Employee must be a non-empty string.", 417)
    expect_rejected(_Who(), "bad input", _raise(exc), message="non-empty string", endpoint="e")
    with pytest.raises(CheckFailed):
        expect_rejected(_Who(), "bad input", lambda: None, message="non-empty string", endpoint="e")


def test_failures_file_lists_each_failure_with_details(tmp_path, fake_client):
    class Fails(ReleaseSuite):
        name = "v16p_demo"

        def build_steps(self, versions):
            def step(client, ctx):
                expect_denied(_Who(), "sales reads probe", lambda: None, endpoint="get_list")

            return [Step("probe [sales]", step), Step("fine", lambda c, ctx: None)]

    tr = TargetResult(label="site", url="http://x")
    tr.suites.append(run_suite(fake_client(), Fails(), {}, continue_on_fail=True))
    path = write_failures([tr], tmp_path / "f.md")
    text = path.read_text()
    assert "v16p_demo · probe [sales]" in text
    assert "rt.sales@example.com" in text and "Sales User" in text
    assert "**Expected:**" in text and "**Actual:**" in text
    assert "fine" not in text


def test_no_failures_file_when_all_pass(tmp_path):
    assert write_failures([TargetResult(label="s", url="u")], tmp_path / "f.md") is None


def test_failures_are_classified_and_run_rate_counts_only_verdicts(fake_client):
    from release_tests.report import summarise
    from release_tests.suites.base import SkipStep

    def skip(c, ctx):
        raise SkipStep("no worker")

    def product_bug(c, ctx):
        expect_denied(_Who(), "reader exports", lambda: None, endpoint="e")

    def server_error(c, ctx):
        raise FrappeAPIError("500", 500, "KeyError")

    def rejected(c, ctx):
        raise FrappeAPIError("417", 417, "HSN code required")

    def test_bug(c, ctx):
        raise KeyError("ctx['probe']")

    class Mixed(ReleaseSuite):
        name = "mixed"

        def build_steps(self, versions):
            return [
                Step("ok", lambda c, ctx: None),
                Step("bug", product_bug),
                Step("500", server_error),
                Step("417", rejected),
                Step("broken", test_bug),
                Step("skipped", skip),
            ]

    result = run_suite(fake_client(), Mixed(), {}, continue_on_fail=True)
    kinds = {s.step: (s.details or {}).get("kind") for s in result.steps}
    assert kinds == {
        "ok": None,
        "bug": "issue",
        "500": "issue",
        "417": "needs triage",
        "broken": "harness",
        "skipped": None,
    }
    tr = TargetResult(label="s", url="u")
    tr.suites.append(result)
    c = summarise([tr])
    # verdicts: ok + bug + 500 = 3 of 6
    assert (c["pass"], c["issue"], c["needs triage"], c["harness"], c["skip"]) == (1, 2, 1, 1, 1)
    assert c["run_rate"] == 50


def test_desk_page_csrf_token_is_sent_on_later_writes(monkeypatch):
    from release_tests.client import FrappeClient

    client = FrappeClient("http://site.test")

    class Page:
        text = '<script>frappe.csrf_token = "abc123";</script>'

    monkeypatch.setattr(client.session, "get", lambda *a, **k: Page())
    client.get_page("/desk")
    assert client.session.headers["X-Frappe-CSRF-Token"] == "abc123"


def test_csrf_refusal_is_a_harness_problem_not_an_issue(fake_client):
    def step(c, ctx):
        expect_allowed(
            _Who(),
            "save layout",
            _raise(FrappeAPIError("400", 400, "Invalid Request")),
            endpoint="List Filter",
        )

    class Csrf(ReleaseSuite):
        name = "csrf"

        def build_steps(self, versions):
            return [Step("save", step)]

    details = run_suite(fake_client(), Csrf(), {}).steps[0].details
    assert details["kind"] == "harness"


def test_independent_steps_keep_running_after_a_failure(fake_client):
    class Independent(ReleaseSuite):
        name = "independent"
        independent_steps = True

        def build_steps(self, versions):
            return [
                Step("fails", lambda c, ctx: _raise(RuntimeError("x"))()),
                Step("still runs", lambda c, ctx: None),
            ]

    statuses = [s.status for s in run_suite(fake_client(), Independent(), {}).steps]
    assert statuses == ["fail", "pass"]


def test_failed_setup_blocks_even_an_independent_suite(fake_client):
    class NeedsSetup(ReleaseSuite):
        name = "needs_setup"
        independent_steps = True

        def build_steps(self, versions):
            return [
                Step(
                    "setup",
                    lambda c, ctx: _raise(RuntimeError("no company"))(),
                    blocks_on_fail=True,
                ),
                Step("check", lambda c, ctx: None),
            ]

    steps = run_suite(fake_client(), NeedsSetup(), {}).steps
    assert [(s.status, s.error) for s in steps][1] == ("skip", "blocked by earlier failure")
