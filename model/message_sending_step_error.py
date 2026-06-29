from pydantic import BaseModel

class MessageSendingStepError(BaseModel):
    type: str
    message: str
    trace_back: str