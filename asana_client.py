import asana

import config


class _Client:
    """Thin wrapper around the asana v5 SDK that mimics the legacy Client API."""

    def __init__(self, token: str):
        configuration = asana.Configuration()
        configuration.access_token = token
        self._api_client = asana.ApiClient(configuration)

    @classmethod
    def access_token(cls, token: str) -> "_Client":
        return cls(token)

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


def _client() -> _Client:
    return _Client.access_token(config.ASANA_TOKEN)


def get_unassigned_tasks(project_id: str) -> list[dict]:
    client = _client()
    print(f"Getting tasks for project: {project_id}")
    task_refs = client.tasks.get_tasks_for_project(
        project_id,
        opt_fields="gid,name",
        opt_pretty=True,
    )
    tasks = []
    for ref in task_refs:
        print(f"Getting task: {ref['gid']}")
        task = client.tasks.get_task(ref["gid"], opt_fields="gid,name,notes,assignee,custom_fields")
        if task.get("assignee") is None:
            tasks.append(task)
    return tasks


def assign_task(task_id: str, user_gid: str) -> None:
    client = _client()
    client.tasks.update_task(task_id, {"assignee": user_gid}, opt_pretty=True)


def add_comment(task_id: str, text: str) -> None:
    client = _client()
    client.stories.create_story_for_task(task_id, {"text": text}, opt_pretty=True)
