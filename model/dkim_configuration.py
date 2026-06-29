from pydantic import BaseModel


class DKIMConfiguration(BaseModel):
    private_key_path: str
    selector: str
