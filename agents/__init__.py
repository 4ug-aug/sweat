from agents.base import BaseAgent

__all__ = [
    "BaseAgent",
    "ImplementerAgent",
    "ReviewerAgent",
    "CodeReviewerAgent",
    "AGENT_TYPES",
]


def __getattr__(name: str):
    if name == "ImplementerAgent":
        from agents.implementer import ImplementerAgent
        return ImplementerAgent
    if name == "ReviewerAgent":
        from agents.reviewer import ReviewerAgent
        return ReviewerAgent
    if name == "CodeReviewerAgent":
        from agents.code_reviewer import CodeReviewerAgent
        return CodeReviewerAgent
    if name == "AGENT_TYPES":
        from agents.registry import AGENT_TYPES
        return AGENT_TYPES
    raise AttributeError(f"module 'agents' has no attribute {name!r}")
