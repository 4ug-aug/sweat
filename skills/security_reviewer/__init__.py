from pathlib import Path

from skills.base import BaseSkill, SkillContext

_PROMPT = (Path(__file__).parent / "prompt.md").read_text()


class SecurityReviewerSkill(BaseSkill):
    name = "security-reviewer"
    description = (
        "Applies security audit patterns covering SQL injection, XSS, "
        "authorization, input validation, secrets exposure, and header security."
    )

    def build_prompt_fragment(self, context: SkillContext) -> str:
        return _PROMPT


SKILL_CLASS = SecurityReviewerSkill
