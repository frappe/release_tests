from frappe_smoke import gating

V = {
    "frappe": {"version": "16.0.0", "branch": "version-16"},
    "erpnext": {"version": "15.42.1", "branch": "version-15"},
    "crm": {"branch": "develop"},  # develop branch, no parseable version
}


def test_app_installed():
    assert gating.app_installed(V, "erpnext")
    assert not gating.app_installed(V, "hrms")


def test_version_of():
    assert str(gating.version_of(V, "frappe")) == "16.0.0"
    assert gating.version_of(V, "hrms") is None
    # develop branch with no version string is unparseable -> None
    assert gating.version_of(V, "crm") is None


def test_at_least():
    assert gating.at_least(V, "frappe", "16")
    assert not gating.at_least(V, "erpnext", "16")
    assert gating.at_least(V, "erpnext", "15")
    # develop/no-version is treated as "latest" -> satisfies any minimum
    assert gating.at_least(V, "crm", "99")
    # absent app never satisfies
    assert not gating.at_least(V, "hrms", "1")


def test_major_of():
    assert gating.major_of(V, "frappe") == 16
    assert gating.major_of(V, "hrms") is None
