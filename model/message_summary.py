from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from datetime import datetime


class MessageSummary(BaseModel):
    id: str
    subject: str
    received_time: datetime
    to: str
    from_: str = Field(..., alias="from")


    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)
