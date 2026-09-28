"""Target configuration: parse ``targets.toml`` into ``Target`` objects.

Each target describes one site the harness can run against (URL + how to
authenticate). Credentials live in a gitignored ``targets.toml``; passwords and
secrets may be given inline or via ``$ENV_VAR`` references resolved at load time.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # py311+
    import tomllib
except ModuleNotFoundError:  # py310
    import tomli as tomllib  # type: ignore


@dataclass
class Target:
    label: str
    url: str
    auth: str  # "login" | "token"
    username: str | None = None
    password: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    host_header: str | None = None
    # Opt-in, because the customisations suite *writes* schema to the target:
    # custom fields, scripts and DocTypes. Off by default so running "all suites"
    # against an ordinary site can never customise it by accident.
    allow_customisations: bool = False

    def __post_init__(self) -> None:
        if self.auth not in ("login", "token"):
            raise ValueError(f"target {self.label!r}: auth must be 'login' or 'token'")
        if self.auth == "login" and not (self.username and self.password):
            raise ValueError(f"target {self.label!r}: login auth requires username + password")
        if self.auth == "token" and not (self.api_key and self.api_secret):
            raise ValueError(f"target {self.label!r}: token auth requires api_key + api_secret")


def _resolve(value: str | None) -> str | None:
    """Resolve ``$ENV_VAR`` references against the environment."""
    if isinstance(value, str) and value.startswith("$"):
        return os.environ.get(value[1:], "")
    return value


def load_targets(path: str | Path) -> list[Target]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"targets file not found: {path}")
    data = tomllib.loads(path.read_text())
    raw_targets = data.get("target", [])
    if not raw_targets:
        raise ValueError(f"no [[target]] entries found in {path}")
    targets = []
    for raw in raw_targets:
        targets.append(
            Target(
                label=raw["label"],
                url=raw["url"],
                auth=raw.get("auth", "login"),
                username=_resolve(raw.get("username")),
                password=_resolve(raw.get("password")),
                api_key=_resolve(raw.get("api_key")),
                api_secret=_resolve(raw.get("api_secret")),
                host_header=raw.get("host_header"),
            )
        )
    return targets


def select_targets(targets: list[Target], label: str) -> list[Target]:
    """Return targets matching ``label`` (or all when ``label == 'all'``)."""
    if label == "all":
        return targets
    matched = [t for t in targets if t.label == label]
    if not matched:
        available = ", ".join(t.label for t in targets)
        raise ValueError(f"no target labelled {label!r}; available: {available}")
    return matched


def connect(target: Target):
    """Build an authenticated :class:`FrappeClient` for a target."""
    from .client import FrappeClient

    client = FrappeClient(target.url, host_header=target.host_header)
    if target.auth == "token":
        client.use_token(target.api_key, target.api_secret)  # type: ignore[arg-type]
    else:
        client.login(target.username, target.password)  # type: ignore[arg-type]
    # Carried on the client because a suite's steps receive the client, not the
    # Target; this is how the customisations suite sees its opt-in.
    client.allow_customisations = target.allow_customisations
    return client
