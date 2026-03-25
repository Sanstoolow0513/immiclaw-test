import pytest

from main import parse_args


def test_parse_args_task_name():
    ns = parse_args(["task", "qmr-login"])
    assert ns.command == "task"
    assert ns.task_name == "qmr-login"
    assert ns.task_file is None


def test_parse_args_task_file():
    ns = parse_args(["task", "--file", "/tmp/task.yaml"])
    assert ns.command == "task"
    assert ns.task_file == "/tmp/task.yaml"


def test_parse_args_list_tasks():
    ns = parse_args(["--list-tasks"])
    assert ns.list_tasks is True


def test_parse_args_task_with_base_url():
    ns = parse_args(["task", "test", "--base-url", "http://example.com"])
    assert ns.task_name == "test"
    assert ns.base_url == "http://example.com"


def test_parse_args_requires_task_name_or_file():
    with pytest.raises(SystemExit):
        parse_args(["task"])
