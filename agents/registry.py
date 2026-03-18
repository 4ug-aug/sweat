from agents.code_reviewer import CodeReviewerAgent
from agents.implementer import ImplementerAgent
from agents.reviewer import ReviewerAgent
from agents.security_reviewer import SecurityReviewerAgent

AGENT_TYPES = {
    "implementer": ImplementerAgent,
    "reviewer": ReviewerAgent,
    "code_reviewer": CodeReviewerAgent,
    "security_reviewer": SecurityReviewerAgent,
}
