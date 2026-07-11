"""Thin GitHub Contents API client — commit, read, list, delete files per branch.

Only the operations the portfolio pipeline needs. Every write is a commit, so
git history is the audit trail. The token is a fine-grained PAT scoped to the
single portfolio repo with contents:write.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass

import httpx

API = "https://api.github.com"


@dataclass
class RepoFile:
    path: str
    sha: str
    data: dict


class GitHubError(Exception):
    pass


class GitHubClient:
    def __init__(self, repo: str, token: str) -> None:
        self.repo = repo
        self._client = httpx.Client(
            base_url=f"{API}/repos/{repo}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "portfolio-mcp",
            },
            timeout=30.0,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _raise(self, resp: httpx.Response, context: str) -> None:
        raise GitHubError(f"{context}: {resp.status_code} {resp.text}")

    # ── Reads ────────────────────────────────────────────────────────────────

    def get_file(self, path: str, branch: str) -> RepoFile | None:
        """Return the file (parsed JSON) and its blob sha, or None if absent."""
        resp = self._client.get(f"/contents/{path}", params={"ref": branch})
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            self._raise(resp, f"get_file {path}@{branch}")
        payload = resp.json()
        raw = base64.b64decode(payload["content"]).decode("utf-8")
        return RepoFile(path=path, sha=payload["sha"], data=json.loads(raw))

    def list_dir(self, path: str, branch: str) -> list[dict]:
        """List a directory's entries ([] if the dir doesn't exist on the branch)."""
        resp = self._client.get(f"/contents/{path}", params={"ref": branch})
        if resp.status_code == 404:
            return []
        if resp.status_code != 200:
            self._raise(resp, f"list_dir {path}@{branch}")
        return [e for e in resp.json() if e.get("type") == "file"]

    # ── Writes ───────────────────────────────────────────────────────────────

    def put_json(
        self, path: str, branch: str, data: dict, message: str, sha: str | None = None
    ) -> str:
        """Create or update a JSON file on a branch. Returns the new blob sha."""
        content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        body: dict = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if sha:
            body["sha"] = sha
        resp = self._client.put(f"/contents/{path}", json=body)
        if resp.status_code not in (200, 201):
            self._raise(resp, f"put_json {path}@{branch}")
        return resp.json()["content"]["sha"]

    def delete_file(self, path: str, branch: str, sha: str, message: str) -> None:
        resp = self._client.request(
            "DELETE",
            f"/contents/{path}",
            json={"message": message, "sha": sha, "branch": branch},
        )
        if resp.status_code != 200:
            self._raise(resp, f"delete_file {path}@{branch}")
