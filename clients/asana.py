import asyncio

import asana

from exceptions import AsanaError


class _Client:
    """Thin wrapper around the asana v5 SDK that mimics the legacy Client API."""

    def __init__(self, token: str):
        configuration = asana.Configuration()
        configuration.access_token = token
        self._api_client = asana.ApiClient(configuration)

    @property
    def tasks(self):
        return _TasksProxy(self._api_client)

    @property
    def stories(self):
        return _StoriesProxy(self._api_client)


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


class _StoriesProxy:
    def __init__(self, api_client):
        self._api = asana.StoriesApi(api_client)

    def create_story_for_task(self, task_id, body, opt_pretty=False):
        return self._api.create_story_for_task({"data": body}, task_id, {})


class AsanaClient:
    def __init__(self, token: str):
        self._client = _Client(token)

    def get_unassigned_tasks(self, project_id: str) -> list[dict]:
        try:
            print(f"Getting tasks for project: {project_id}")
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
                    print(f"  {task['gid']} - {task['name']}{suffix}")
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

    # Async wrappers — delegate to sync methods via to_thread to unblock the event loop.

    async def get_unassigned_tasks_async(self, project_id: str) -> list[dict]:
        return await asyncio.to_thread(self.get_unassigned_tasks, project_id)

    async def assign_task_async(self, task_id: str, user_gid: str | None) -> None:
        await asyncio.to_thread(self.assign_task, task_id, user_gid)

    async def add_comment_async(self, task_id: str, text: str) -> None:
        await asyncio.to_thread(self.add_comment, task_id, text)
