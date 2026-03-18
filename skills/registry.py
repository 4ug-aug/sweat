from __future__ import annotations

import importlib
import logging
from pathlib import Path

from skills.base import BaseSkill

SKILLS: dict[str, type[BaseSkill]] = {}


def _auto_discover() -> None:
    skills_dir = Path(__file__).parent
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir() or not (entry / "__init__.py").exists():
            continue
        module_name = f"skills.{entry.name}"
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            logging.warning(f"Failed to import skill module {module_name!r}: {exc}")
            continue
        skill_cls = getattr(module, "SKILL_CLASS", None)
        if skill_cls is None:
            continue
        if not (isinstance(skill_cls, type) and issubclass(skill_cls, BaseSkill)):
            logging.warning(f"SKILL_CLASS in {module_name!r} is not a BaseSkill subclass, skipping")
            continue
        SKILLS[skill_cls.name] = skill_cls
        logging.debug(f"Registered skill: {skill_cls.name!r}")


_auto_discover()
