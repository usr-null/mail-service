from pydantic import BaseModel
from typing import Optional, Literal
from .message_sending_result import MessageSendingResult


class MessageSendingTask(BaseModel):
    task_id: str
    status: Literal["pending", "complete"]
    result: Optional[MessageSendingResult] = None
