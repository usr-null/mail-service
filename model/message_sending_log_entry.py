from pydantic import BaseModel
from typing import Optional
from typing import Literal
from .message_sending_step_error import MessageSendingStepError

StepType = Literal[
    "DNS_LOOKUP",
    "CONNECT",
    "START_TLS",
    "START_PLAIN_TEXT",
    "SEND_FROM",
    "SEND_TO",
    "SEND_DATA",
    "QUIT"
]

class MessageSendingLogEntry(BaseModel):
    step_type: StepType
    domain: str
    error: Optional[MessageSendingStepError] = None