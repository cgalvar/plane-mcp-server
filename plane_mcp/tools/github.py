"""Pull requests on GitHub, using the token in GITHUB_TOKEN.

Plane's own links only store a URL. These actions talk to GitHub: list the
open requests of a repository, read one diff, and leave a comment.
"""

from __future__ import annotations

import json
import os
from typing import Any, Literal
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from fastmcp import FastMCP

from plane_mcp.toolkit import Action, build_annotations, build_description, missing, needs

NAME = "github"
TITLE = "GitHub pull requests"

DIFF_LIMIT = 20_000

ACTIONS = (
    Action(
        "list_pulls",
        ("owner", "repo"),
        ("state",),
        note="state is open, closed, or all; open is the default",
        read=True,
    ),
    Action("read_diff", ("owner", "repo", "pull_number"), read=True),
    Action("comment", ("owner", "repo", "pull_number", "body")),
)

FOOTER = (
    "Uses GITHUB_TOKEN from the server environment. "
    "read_diff returns the unified diff and truncates it after 20000 characters. "
    "comment posts on the pull request conversation."
)

LEGACY: dict[str, str] = {}


def _request(method: str, path: str, payload: dict[str, Any] | None = None, accept: str | None = None) -> Any:
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        return "Error: GITHUB_TOKEN is not configured."
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": accept or "application/vnd.github+json",
        "User-Agent": "plane-mcp-github",
    }
    request = Request(f"https://api.github.com{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        return f"Error calling tool 'github': HTTP {exc.code}: {detail}"
    if accept == "application/vnd.github.diff":
        return raw.decode(errors="replace")
    if not raw:
        return None
    return json.loads(raw)


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name=NAME,
        description=build_description("Pull requests in a GitHub repository.", ACTIONS, FOOTER),
        annotations=build_annotations(TITLE, ACTIONS),
    )
    def github(
        action: Literal["list_pulls", "read_diff", "comment"],
        owner: str = "",
        repo: str = "",
        pull_number: int = 0,
        body: str = "",
        state: str = "",
    ) -> Any:
        if error := needs(action, owner=owner, repo=repo):
            return error

        if action == "list_pulls":
            which = state or "open"
            if which not in ("open", "closed", "all"):
                return "Error: state must be open, closed, or all."
            found = _request("GET", f"/repos/{owner}/{repo}/pulls?state={which}&per_page=20")
            if isinstance(found, str):
                return found
            return [
                {
                    "number": item["number"],
                    "title": item["title"],
                    "state": item["state"],
                    "user": (item.get("user") or {}).get("login"),
                    "html_url": item["html_url"],
                }
                for item in found
            ]

        if not pull_number:
            return missing(action, "pull_number")

        if action == "read_diff":
            diff = _request(
                "GET",
                f"/repos/{owner}/{repo}/pulls/{pull_number}",
                accept="application/vnd.github.diff",
            )
            if isinstance(diff, str) and diff.startswith("Error"):
                return diff
            text = diff or ""
            if len(text) > DIFF_LIMIT:
                return text[:DIFF_LIMIT] + "\n\n[diff truncated]"
            return text

        if not body:
            return missing(action, "body")
        return _request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{pull_number}/comments",
            {"body": body},
        )
