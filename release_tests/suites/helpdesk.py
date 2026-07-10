"""Frappe Helpdesk: create an Agent, then open a Ticket.

Both idempotent — the Agent is keyed on its user email, the Ticket on its subject
— so re-runs against the same site stay clean.

NOTE: written against the Helpdesk HD Agent / HD Ticket schema but not yet
validated end-to-end in this environment (Helpdesk pulls in the ``telephony``
app, which wasn't available here). It auto-skips where Helpdesk isn't installed
and will be exercised on the first target that has it.
"""

from __future__ import annotations

from .. import factories
from ..client import FrappeClient
from ..gating import Versions
from .base import ReleaseSuite, Step


def _agent(client: FrappeClient, ctx: dict) -> None:
    ctx["agent"] = factories.ensure_hd_agent(client)


def _ticket(client: FrappeClient, ctx: dict) -> None:
    ctx["ticket"] = factories.ensure_hd_ticket(client, raised_by=factories.RT_HD_AGENT_EMAIL)


def _verify(client: FrappeClient, ctx: dict) -> None:
    ticket = client.get_doc("HD Ticket", ctx["ticket"])
    if ticket.get("subject") != factories.RT_HD_TICKET_SUBJECT:
        raise AssertionError("HD Ticket read back with unexpected subject")


class HelpdeskSuite(ReleaseSuite):
    name = "helpdesk"
    required_app = "helpdesk"
    description = "Helpdesk: create an Agent and open a Ticket."

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("create HD Agent", _agent),
            Step("create HD Ticket", _ticket),
            Step("verify ticket", _verify),
        ]
