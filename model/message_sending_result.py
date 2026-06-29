from pydantic import BaseModel
from typing import List
from .message_sending_log_entry import MessageSendingLogEntry

class MessageSendingResult(BaseModel):
    success: bool
    logs: List[MessageSendingLogEntry]
