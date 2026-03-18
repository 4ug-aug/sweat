from pathlib import Path

from skills.base import BaseSkill, SkillContext

_PROMPT = (Path(__file__).parent / "prompt.md").read_text()


class FrontendDesignerSkill(BaseSkill):
    name = "frontend-designer"
    description = (
        "Applies design system conventions, component reuse patterns, "
        "accessibility standards, and responsive layout practices to frontend tasks."
    )

    def build_prompt_fragment(self, context: SkillContext) -> str:
        return _PROMPT


SKILL_CLASS = FrontendDesignerSkill
