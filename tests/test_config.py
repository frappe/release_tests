import pytest

from frappe_smoke.config import Target, load_targets, select_targets


def test_target_validation():
    with pytest.raises(ValueError):
        Target(label="x", url="http://x", auth="login")  # missing creds
    with pytest.raises(ValueError):
        Target(label="x", url="http://x", auth="bogus")
    # valid token target
    Target(label="x", url="http://x", auth="token", api_key="k", api_secret="s")


def test_load_targets_resolves_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PW", "hunter2")
    toml = tmp_path / "targets.toml"
    toml.write_text(
        """
[[target]]
label = "v16"
url = "http://mysite.localhost:8000"
auth = "login"
username = "Administrator"
password = "$PW"
"""
    )
    targets = load_targets(toml)
    assert len(targets) == 1
    assert targets[0].password == "hunter2"


def test_select_targets():
    a = Target(label="a", url="http://a", auth="token", api_key="k", api_secret="s")
    b = Target(label="b", url="http://b", auth="token", api_key="k", api_secret="s")
    assert select_targets([a, b], "all") == [a, b]
    assert select_targets([a, b], "b") == [b]
    with pytest.raises(ValueError):
        select_targets([a, b], "nope")
