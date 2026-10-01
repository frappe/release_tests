"""Frappe app metadata.

This file exists so bench and Frappe Cloud recognise the repository as an
installable app — nothing more. The harness itself stays Frappe-free (see
CONTRIBUTING, rule 1): no module here imports frappe, and the engine continues to
speak plain HTTP, which is what lets it run in CI and against remote sites.

The app ships no DocTypes, no scheduler events, no hooks into site behaviour. It
is a delivery vehicle for the Python package that release_manager imports.
"""

app_name = "release_tests"
app_title = "Release Tests"
app_publisher = "Release Tests Contributors"
app_description = (
    "External HTTP release-test harness for Frappe sites — the execution engine "
    "behind Release Manager."
)
app_email = "umair_sayyed@yahoo.com"
app_license = "MIT"
