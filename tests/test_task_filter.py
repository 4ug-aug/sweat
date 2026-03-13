import pytest

from task_filter import filter_and_rank_tasks, _to_minutes


# --- Duration parsing tests ---

@pytest.mark.parametrize("value,expected", [
    ("90", 90.0),
    ("30m", 30.0),
    ("45m", 45.0),
    ("2h", 120.0),
    ("2h 00m", 120.0),
    ("1h 30m", 90.0),
    ("5h 00m", 300.0),
])
def test_to_minutes_valid(value, expected):
    assert _to_minutes(value) == expected


@pytest.mark.parametrize("value", ["ABT", "TBD", "M", "", None])
def test_to_minutes_unparseable(value):
    assert _to_minutes(value) is None


def _task(gid, work_type=None, estimated_time=None, priority=None, domain=None):
    custom_fields = []
    if work_type is not None:
        custom_fields.append({"name": "Work Type", "display_value": work_type})
    if estimated_time is not None:
        custom_fields.append({"name": "Estimated Time", "display_value": estimated_time})
    if priority is not None:
        custom_fields.append({"name": "Priority", "display_value": priority})
    if domain is not None:
        custom_fields.append({"name": "Domain", "display_value": domain})
    return {"gid": gid, "name": f"Task {gid}", "custom_fields": custom_fields}


FIELD_NAMES = {
    "priority": "Priority",
    "estimated_time": "Estimated Time",
    "work_type": "Work Type",
    "domain": "Domain",
}


# --- Filter tests ---

def test_enum_filter_includes_matching():
    tasks = [_task("1", work_type="Bug")]
    cfg = {"field_names": FIELD_NAMES, "field_filters": {"work_type": ["Bug"]}}
    result = filter_and_rank_tasks(tasks, cfg)
    assert len(result) == 1
    assert result[0]["gid"] == "1"


def test_enum_filter_excludes_non_matching():
    tasks = [_task("1", work_type="Feature")]
    cfg = {"field_names": FIELD_NAMES, "field_filters": {"work_type": ["Bug"]}}
    result = filter_and_rank_tasks(tasks, cfg)
    assert result == []


def test_enum_filter_excludes_missing_field():
    tasks = [_task("1")]  # no work_type field
    cfg = {"field_names": FIELD_NAMES, "field_filters": {"work_type": ["Bug"]}}
    result = filter_and_rank_tasks(tasks, cfg)
    assert result == []


def test_numeric_filter_max():
    tasks = [_task("1", estimated_time="1h 00m"), _task("2", estimated_time="3h 00m")]
    cfg = {"field_names": FIELD_NAMES, "field_filters": {"estimated_time": {"max": 120}}}
    result = filter_and_rank_tasks(tasks, cfg)
    assert [t["gid"] for t in result] == ["1"]


def test_numeric_filter_non_numeric_excluded():
    tasks = [_task("1", estimated_time="ABT")]
    cfg = {"field_names": FIELD_NAMES, "field_filters": {"estimated_time": {"max": 120}}}
    result = filter_and_rank_tasks(tasks, cfg)
    assert result == []


def test_multiple_filters_all_must_pass():
    tasks = [
        _task("1", work_type="Bug", estimated_time="1"),
        _task("2", work_type="Bug", estimated_time="5"),
        _task("3", work_type="Feature", estimated_time="1"),
    ]
    cfg = {
        "field_names": FIELD_NAMES,
        "field_filters": {"work_type": ["Bug"], "estimated_time": {"max": 2}},
    }
    result = filter_and_rank_tasks(tasks, cfg)
    assert [t["gid"] for t in result] == ["1"]


# --- Ranking & cap tests ---

def test_sorts_by_priority():
    tasks = [
        _task("1", priority="Low"),
        _task("2", priority="Urgent"),
        _task("3", priority="High"),
    ]
    cfg = {
        "field_names": FIELD_NAMES,
        "priority_order": ["Urgent", "High", "Medium", "Low"],
    }
    result = filter_and_rank_tasks(tasks, cfg)
    assert [t["gid"] for t in result] == ["2", "3", "1"]


def test_unset_priority_goes_last():
    tasks = [_task("1"), _task("2", priority="High")]
    cfg = {
        "field_names": FIELD_NAMES,
        "priority_order": ["Urgent", "High", "Medium", "Low"],
    }
    result = filter_and_rank_tasks(tasks, cfg)
    assert result[0]["gid"] == "2"
    assert result[-1]["gid"] == "1"


def test_unknown_priority_value_goes_last():
    tasks = [_task("1", priority="Whenever"), _task("2", priority="High")]
    cfg = {
        "field_names": FIELD_NAMES,
        "priority_order": ["Urgent", "High", "Medium", "Low"],
    }
    result = filter_and_rank_tasks(tasks, cfg)
    assert result[0]["gid"] == "2"
    assert result[-1]["gid"] == "1"


def test_caps_at_max_tasks():
    tasks = [_task(str(i)) for i in range(30)]
    cfg = {"field_names": FIELD_NAMES, "max_tasks_for_selector": 10}
    result = filter_and_rank_tasks(tasks, cfg)
    assert len(result) == 10


def test_passthrough_if_no_config():
    tasks = [_task("1"), _task("2"), _task("3")]
    result = filter_and_rank_tasks(tasks, {})
    assert len(result) == 3
