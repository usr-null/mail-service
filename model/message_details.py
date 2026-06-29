from .message_summary import MessageSummary
from typing import Optional


class MessageDetails(MessageSummary):
    content: Optional[str]
