from release_tests.gating import Versions
from release_tests.runner import run_suite, run_target
from release_tests.suites.base import ReleaseSuite, Step


class _PassThenFail(ReleaseSuite):
    name = "demo"
    required_app = None

    def build_steps(self, versions: Versions):
        return [
            Step("ok", lambda c, ctx: ctx.update(ran_ok=True)),
            Step("boom", lambda c, ctx: (_ for _ in ()).throw(RuntimeError("kaboom"))),
            Step("never", lambda c, ctx: ctx.update(ran_never=True)),
        ]


def test_stop_on_fail_blocks_dependents(fake_client):
    result = run_suite(fake_client(), _PassThenFail(), {})
    statuses = [(s.step, s.status) for s in result.steps]
    assert statuses == [("ok", "pass"), ("boom", "fail"), ("never", "skip")]
    assert result.status == "fail"
    assert "kaboom" in result.steps[1].error


def test_continue_on_fail_runs_all(fake_client):
    result = run_suite(fake_client(), _PassThenFail(), {}, continue_on_fail=True)
    statuses = [s.status for s in result.steps]
    assert statuses == ["pass", "fail", "pass"]


def test_suite_skips_when_app_absent(fake_client):
    class Needs(ReleaseSuite):
        name = "needs"
        required_app = "erpnext"

        def build_steps(self, versions):
            return [Step("x", lambda c, ctx: None)]

    # no erpnext in versions -> skipped, no steps run
    result = run_suite(fake_client(), Needs(), {})
    assert result.status == "skip"
    assert result.steps == []


def test_run_target_records_versions_and_runs_core(fake_client):
    client = fake_client({"frappe": {"version": "16.0.0", "branch": "version-16"}})
    tr = run_target("local", "http://x", client, only_suite="core_frappe")
    assert tr.versions["frappe"]["version"] == "16.0.0"
    assert len(tr.suites) == 1
    assert tr.suites[0].suite == "core_frappe"
    assert tr.ok


def test_run_target_handles_detect_failure():
    class Boom:
        def get_versions(self):
            raise ConnectionError("refused")

    tr = run_target("local", "http://x", Boom())
    assert not tr.ok
    assert "refused" in tr.error
