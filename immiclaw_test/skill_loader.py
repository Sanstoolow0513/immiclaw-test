"""Load and assemble skill YAML files into LLM prompt fragments."""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import Skill


def load_skills(skill_names: list[str], skills_dir: Path) -> list[Skill]:
    """Load skill YAMLs by name from skills_dir (searching operation/ and strategy/ subdirs)."""
    skills: list[Skill] = []
    for name in skill_names:
        path = _find_skill_file(name, skills_dir)
        if path is None:
            raise FileNotFoundError(
                f"Skill '{name}' not found in {skills_dir}. "
                f"Searched operation/ and strategy/ subdirectories."
            )
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        skills.append(Skill(**data))
    return skills


def _find_skill_file(name: str, skills_dir: Path) -> Path | None:
    for subdir in ("operation", "strategy"):
        for ext in (".yaml", ".yml"):
            candidate = skills_dir / subdir / f"{name}{ext}"
            if candidate.is_file():
                return candidate
    return None


def filter_skills_for_scenario(
    skills: list[Skill],
    scenario_name: str | None,
) -> list[Skill]:
    """Filter skills for a specific task, or return all if scenario_name is None."""
    if scenario_name is None:
        return list(skills)
    return [s for s in skills if not s.applies_to or scenario_name in s.applies_to]


def assemble_skills_prompt(skills: list[Skill]) -> str:
    """Assemble filtered skills into a structured prompt fragment."""
    operation_skills = [s for s in skills if s.type == "operation"]
    strategy_skills = [s for s in skills if s.type == "strategy"]

    parts: list[str] = []

    if operation_skills:
        parts.append("### 操作级")
        for s in operation_skills:
            header = f"**{s.description}** ({s.name})"
            if s.applies_to:
                header += f"\n适用场景: {', '.join(s.applies_to)}"
            parts.append(f"{header}\n{s.prompt.strip()}")

    if strategy_skills:
        parts.append("### 策略级")
        for s in strategy_skills:
            header = f"**{s.description}** ({s.name})"
            if s.applies_to:
                header += f"\n适用场景: {', '.join(s.applies_to)}"
            parts.append(f"{header}\n{s.prompt.strip()}")

    return "\n\n".join(parts)
