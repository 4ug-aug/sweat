from responsibilities.review_responder import ReviewResponder
from responsibilities.ci_responder import CIResponder
from responsibilities.comment_responder import CommentResponder

RESPONSIBILITY_TYPES: dict[str, type] = {
    "review_responder": ReviewResponder,
    "ci_responder": CIResponder,
    "comment_responder": CommentResponder,
}
