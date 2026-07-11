"""Runtime configuration, all from the environment or local files.

Secrets never live in the repo. The GitHub token comes from the MCP `env`
block; the denylist is a local-only file (default ~/.portfolio-mcp/denylist.json).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DENYLIST = Path.home() / ".portfolio-mcp" / "denylist.json"


@dataclass
class Config:
    repo: str  # "owner/name"
    token: str
    drafts_branch: str = "drafts"
    main_branch: str = "main"
    denylist_path: Path = DEFAULT_DENYLIST
    denylist: list[str] = field(default_factory=list)

    @property
    def owner(self) -> str:
        return self.repo.split("/", 1)[0]

    @property
    def name(self) -> str:
        return self.repo.split("/", 1)[1]


def load_denylist(path: Path) -> list[str]:
    """Client/employer names that must never appear in content.

    File shape: {"names": ["Acme Corp", "Client X"]}. Missing file = empty list
    (the LLM's category-based sanitization is still the first line of defense).
    """
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    names = data.get("names", []) if isinstance(data, dict) else data
    return [n.strip() for n in names if isinstance(n, str) and n.strip()]


def load_config() -> Config:
    repo = os.environ.get("PORTFOLIO_REPO", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not repo or "/" not in repo:
        raise RuntimeError(
            "PORTFOLIO_REPO must be set to 'owner/name' in the MCP env config."
        )
    if not token:
        raise RuntimeError("GITHUB_TOKEN must be set in the MCP env config.")

    denylist_path = Path(
        os.environ.get("PORTFOLIO_DENYLIST", str(DEFAULT_DENYLIST))
    ).expanduser()

    return Config(
        repo=repo,
        token=token,
        drafts_branch=os.environ.get("PORTFOLIO_DRAFTS_BRANCH", "drafts"),
        main_branch=os.environ.get("PORTFOLIO_MAIN_BRANCH", "main"),
        denylist_path=denylist_path,
        denylist=load_denylist(denylist_path),
    )
