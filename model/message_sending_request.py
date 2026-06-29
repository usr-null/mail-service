from pydantic import BaseModel
from typing import Optional

class MessageSendingRequest(BaseModel):
    title: str
    content: str
    html_content: str
    sender_alias: Optional[str] = None
