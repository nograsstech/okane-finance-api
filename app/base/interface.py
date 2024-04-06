from pydantic import BaseModel

class RootResponse(BaseModel):
    status: int
    message: str