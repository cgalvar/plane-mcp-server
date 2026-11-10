"""Shared done criteria for every work item in a project.

Plane Community 1.4.3 has no custom properties. This fork reads and writes the
project-level field added for that edition. The text is the same on an epic,
a story, and a task. `workitem_id` names the item the caller is looking at;
it does not store a separate value.
"""

from __future__ import annotations

from html import escape
from typing import Any, Literal

from fastmcp import FastMCP
from plane.api.base_resource import BaseResource
from plane.errors.errors import HttpError

from plane_mcp.client import get_plane_client_context
from plane_mcp.toolkit import Action, build_annotations, build_description, missing

NAME = "done_criteria"
TITLE = "Done criteria"

ACTIONS = (
    Action(
        "retrieve",
        ("project_id",),
        ("workitem_id",),
        note="the text is shared by every work item in the project",
        read=True,
    ),
    Action(
        "update",
        ("project_id",),
        ("workitem_id", "description_html", "text"),
        note="pass description_html or text; text is stored as one bullet per line",
    ),
)

FOOTER = (
    "This is one field per project, shown on every epic, story, and task. "
    "workitem_id does not select a different value. "
    "text is plain lines; description_html wins when both are sent."
)

LEGACY: dict[str, str] = {}


def _as_html(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "<p></p>"
    return "<ul>" + "".join(f"<li>{escape(line)}</li>" for line in lines) + "</ul>"


class _DoneCriteria(BaseResource):
    def __init__(self, config: Any) -> None:
        # Configuration.base_path already ends in /api/v1.
        super().__init__(config, "")

    def retrieve(self, workspace_slug: str, project_id: str) -> Any:
        return self._get(f"workspaces/{workspace_slug}/projects/{project_id}/done-criteria")

    def update(self, workspace_slug: str, project_id: str, description_html: str) -> Any:
        return self._patch(
            f"workspaces/{workspace_slug}/projects/{project_id}/done-criteria",
            {"description_html": description_html},
        )


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name=NAME,
        description=build_description(
            "Shared done criteria for the work items of a project.",
            ACTIONS,
            FOOTER,
        ),
        annotations=build_annotations(TITLE, ACTIONS),
    )
    def done_criteria(
        action: Literal["retrieve", "update"],
        project_id: str = "",
        workitem_id: str = "",
        description_html: str = "",
        text: str = "",
    ) -> dict[str, Any] | str:
        client, workspace_slug = get_plane_client_context()
        del workitem_id

        if not project_id:
            return missing(action, "project_id")
        if not workspace_slug:
            return "Error: workspace slug is not configured."

        resource = _DoneCriteria(client.config)
        try:
            if action == "retrieve":
                return resource.retrieve(workspace_slug, project_id)
            html = description_html or (_as_html(text) if text else "")
            if not html:
                return missing(action, "description_html or text")
            return resource.update(workspace_slug, project_id, html)
        except HttpError as exc:
            return f"Error calling tool 'done_criteria': {exc}"
