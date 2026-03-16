import asyncio
import logging

import asana

from exceptions import AsanaError

logger = logging.getLogger(__name__)


class _Client:
    """Thin wrapper around the asana v5 SDK that mimics the legacy Client API."""

    def __init__(self, token: str):
        configuration = asana.Configuration()
        configuration.access_token = token
        self._api_client = asana.ApiClient(configuration)

    @property
    def users(self):
        return _UsersProxy(self._api_client)

    @property
    def workspaces(self):
        return _WorkspacesProxy(self._api_client)

    @property
    def projects(self):
        return _ProjectsProxy(self._api_client)

    @property
    def tasks(self):
        return _TasksProxy(self._api_client)

    @property
    def stories(self):
        return _StoriesProxy(self._api_client)

    @property
    def time_tracking(self):
        return _TimeTrackingProxy(self._api_client)


class _UsersProxy:
    def __init__(self, api_client):
        self._api = asana.UsersApi(api_client)

    def get_me(self):
        return self._api.get_me({"opt_fields": "gid,name,email"})


class _WorkspacesProxy:
    def __init__(self, api_client):
        self._api = asana.WorkspacesApi(api_client)

    def get_workspaces(self):
        return self._api.get_workspaces({"opt_fields": "gid,name"})


class _ProjectsProxy:
    def __init__(self, api_client):
        self._api = asana.ProjectsApi(api_client)

    def get_projects_for_workspace(self, workspace_gid):
        return self._api.get_projects_for_workspace(workspace_gid, {"opt_fields": "gid,name"})


class _TasksProxy:
    def __init__(self, api_client):
        self._api = asana.TasksApi(api_client)

    def get_tasks_for_project(self, project_id, opt_fields=None, opt_pretty=False):
        opts = {}
        if opt_fields:
            opts["opt_fields"] = opt_fields
        return self._api.get_tasks_for_project(project_id, opts)

    def get_task(self, task_id, opt_fields=None, **kwargs):
        opts = {}
        if opt_fields:
            opts["opt_fields"] = opt_fields
        return self._api.get_task(task_id, opts)

    def update_task(self, task_id, body, opt_pretty=False):
        return self._api.update_task({"data": body}, task_id, {})

    def create_task(self, body):
        return self._api.create_task({"data": body}, {})


class _StoriesProxy:
    def __init__(self, api_client):
        self._api = asana.StoriesApi(api_client)

    def create_story_for_task(self, task_id, body, opt_pretty=False):
        return self._api.create_story_for_task({"data": body}, task_id, {})


class _TimeTrackingProxy:
    def __init__(self, api_client):
        self._api = asana.TimeTrackingEntriesApi(api_client)

    def create_time_tracking_entry(self, task_gid, body):
        return self._api.create_time_tracking_entry({"data": body}, task_gid, {})


class AsanaClient:
    def __init__(self, token: str):
        self._client = _Client(token)

    def get_current_user(self) -> dict:
        try:
            return self._client.users.get_me()
        except Exception as exc:
            raise AsanaError(f"Failed to get current user: {exc}") from exc

    def get_workspaces(self) -> list[dict]:
        try:
            return list(self._client.workspaces.get_workspaces())
        except Exception as exc:
            raise AsanaError(f"Failed to get workspaces: {exc}") from exc

    def get_projects(self, workspace_gid: str) -> list[dict]:
        try:
            return list(self._client.projects.get_projects_for_workspace(workspace_gid))
        except Exception as exc:
            raise AsanaError(f"Failed to get projects for workspace {workspace_gid}: {exc}") from exc

    def get_unassigned_tasks(self, project_id: str) -> list[dict]:
        try:
            logger.info("Getting tasks for project: %s", project_id)
            task_refs = self._client.tasks.get_tasks_for_project(
                project_id,
                opt_fields="gid,name,completed",
                opt_pretty=True,
            )
            tasks = []
            for ref in task_refs:
                if ref.get("completed"):
                    continue
                task = self._client.tasks.get_task(
                    ref["gid"], opt_fields="gid,name,notes,assignee,custom_fields"
                )
                if task.get("assignee") is None:
                    fields = " - ".join(
                        cf["display_value"]
                        for cf in task.get("custom_fields", [])
                        if cf.get("display_value")
                    )
                    suffix = f" - {fields}" if fields else ""
                    logger.info("  %s - %s%s", task['gid'], task['name'], suffix)
                    tasks.append(task)
            return tasks
        except Exception as exc:
            raise AsanaError(f"Failed to fetch tasks for project {project_id}: {exc}") from exc

    def assign_task(self, task_id: str, user_gid: str | None) -> None:
        try:
            self._client.tasks.update_task(task_id, {"assignee": user_gid}, opt_pretty=True)
        except Exception as exc:
            raise AsanaError(f"Failed to assign task {task_id}: {exc}") from exc

    def add_comment(self, task_id: str, text: str) -> None:
        try:
            self._client.stories.create_story_for_task(task_id, {"text": text}, opt_pretty=True)
        except Exception as exc:
            raise AsanaError(f"Failed to add comment to task {task_id}: {exc}") from exc

    def add_time_tracking_entry(self, task_id: str, duration_minutes: int, entered_on: str) -> None:
        """Create a time tracking entry on a task.

        Args:
            task_id: The Asana task GID.
            duration_minutes: Time spent, in whole minutes.
            entered_on: Date string in YYYY-MM-DD format.
        """
        try:
            self._client.time_tracking.create_time_tracking_entry(
                task_id, {"duration_minutes": duration_minutes, "entered_on": entered_on}
            )
        except Exception as exc:
            raise AsanaError(f"Failed to add time tracking entry to task {task_id}: {exc}") from exc

    def create_task(self, project_id: str, name: str, notes: str) -> dict:
        try:
            body = {"name": name, "projects": [project_id], "notes": notes}
            result = self._client.tasks.create_task(body)
            return result
        except Exception as exc:
            raise AsanaError(f"Failed to create task in project {project_id}: {exc}") from exc

    def get_tasks(self, project_id: str) -> list[dict]:
        try:
            task_refs = self._client.tasks.get_tasks_for_project(
                project_id,
                opt_fields="gid,name,completed",
                opt_pretty=True,
            )
            return [
                {"gid": ref["gid"], "name": ref["name"]}
                for ref in task_refs
                if not ref.get("completed")
            ]
        except Exception as exc:
            raise AsanaError(f"Failed to get tasks for project {project_id}: {exc}") from exc

    # Async wrappers — delegate to sync methods via to_thread to unblock the event loop.

    async def get_unassigned_tasks_async(self, project_id: str) -> list[dict]:
        return await asyncio.to_thread(self.get_unassigned_tasks, project_id)

    async def assign_task_async(self, task_id: str, user_gid: str | None) -> None:
        await asyncio.to_thread(self.assign_task, task_id, user_gid)

    async def add_comment_async(self, task_id: str, text: str) -> None:
        await asyncio.to_thread(self.add_comment, task_id, text)

    async def add_time_tracking_entry_async(self, task_id: str, duration_minutes: int, entered_on: str) -> None:
        await asyncio.to_thread(self.add_time_tracking_entry, task_id, duration_minutes, entered_on)

    async def create_task_async(self, project_id: str, name: str, notes: str) -> dict:
        return await asyncio.to_thread(self.create_task, project_id, name, notes)

    async def get_tasks_async(self, project_id: str) -> list[dict]:
        return await asyncio.to_thread(self.get_tasks, project_id)
