import tempfile
from pathlib import Path

import yaml

from immiclaw_test.skill_loader import (
    assemble_skills_prompt,
    filter_skills_for_scenario,
    load_skills,
)


def _write_skill(dir_path: Path, subdir: str, data: dict) -> Path:
    skill_dir = dir_path / subdir
    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / f"{data['name']}.yaml"
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_load_skills_from_dir():
    with tempfile.TemporaryDirectory() as tmp:
        skills_dir = Path(tmp)
        _write_skill(
            skills_dir,
            "operation",
            {
                "name": "login",
                "type": "operation",
                "description": "Login",
                "prompt": "Do login",
                "allowed_tools": ["click", "fill"],
            },
        )
        _write_skill(
            skills_dir,
            "strategy",
            {
                "name": "error-handling",
                "type": "strategy",
                "description": "Errors",
                "prompt": "Handle errors",
            },
        )
        skills = load_skills(["login", "error-handling"], skills_dir)
        assert len(skills) == 2
        names = {s.name for s in skills}
        assert names == {"login", "error-handling"}
        assert skills[0].allowed_tools == ["click", "fill"]


def test_load_skills_missing_raises():
    with tempfile.TemporaryDirectory() as tmp:
        import pytest

        with pytest.raises(FileNotFoundError):
            load_skills(["nonexistent"], Path(tmp))


def test_filter_skills_universal():
    from immiclaw_test.models import Skill

    skills = [
        Skill(name="a", type="strategy", description="", prompt="universal"),
    ]
    result = filter_skills_for_scenario(skills, "any-scenario")
    assert len(result) == 1


def test_filter_skills_with_applies_to():
    from immiclaw_test.models import Skill

    skills = [
        Skill(
            name="login",
            type="operation",
            description="",
            prompt="login stuff",
            applies_to=["qmr-login"],
        ),
        Skill(name="general", type="strategy", description="", prompt="general stuff"),
    ]
    result = filter_skills_for_scenario(skills, scenario_name=None)
    assert len(result) == 2


def test_assemble_skills_prompt():
    from immiclaw_test.models import Skill

    skills = [
        Skill(
            name="login",
            type="operation",
            description="Login",
            prompt="Do login",
            applies_to=["qmr-login"],
        ),
        Skill(name="errors", type="strategy", description="Errors", prompt="Handle errors"),
    ]
    prompt = assemble_skills_prompt(skills)
    assert "### 操作级" in prompt
    assert "### 策略级" in prompt
    assert "Do login" in prompt
    assert "Handle errors" in prompt
    assert "适用场景: qmr-login" in prompt
