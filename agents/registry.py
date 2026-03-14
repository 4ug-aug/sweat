from agents.code_reviewer import CodeReviewerAgent
from agents.implementer import ImplementerAgent
from agents.reviewer import ReviewerAgent

AGENT_TYPES = {
    "implementer": ImplementerAgent,
    "reviewer": ReviewerAgent,
    "code_reviewer": CodeReviewerAgent,
}
