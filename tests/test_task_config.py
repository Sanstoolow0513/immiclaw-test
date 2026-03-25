import tempfile
from pathlib import Path

import yaml

from immiclaw_test.config import load_task


def test_load_task_new_shape():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "task.yaml"
        path.write_text(
            yaml.dump(
                {
                    "name": "test-task",
                    "description": "Test",
                    "start_url": "{base_url}/login",
                    "goal": "Log in",
                    "done_when": ["Reach dashboard"],
                    "subtasks": [
                        {
                            "name": "login",
                            "goal": "Log in",
                            "done_when": ["Reach dashboard"],
                        }
                    ],
                    "test_data": {"email": "user-{timestamp}@example.com"},
                },
                allow_unicode=True,
            ),
            encoding="utf-8",
        )

        task = load_task(path)
        assert task.name == "test-task"
        assert task.start_url == "{base_url}/login"
        assert task.subtasks[0].name == "login"
        assert "{timestamp}" not in task.test_data["email"]


def test_load_task_legacy_scenario_shape():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "task.yaml"
        path.write_text(
            yaml.dump(
                {
                    "name": "legacy-task",
                    "description": "Legacy",
                    "target_url": "{base_url}/login",
                    "goal": "Log in",
                    "assertions": ["Reach dashboard"],
                    "test_data": {"email": "user-{timestamp}@example.com"},
                },
                allow_unicode=True,
            ),
            encoding="utf-8",
        )

        task = load_task(path)
        assert task.name == "legacy-task"
        assert task.start_url == "{base_url}/login"
        assert task.done_when == ["Reach dashboard"]
        assert len(task.subtasks) == 1
        assert task.subtasks[0].name == "complete-task"
