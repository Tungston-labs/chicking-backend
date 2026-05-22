from typing import Any

from pydantic import BaseModel


class MessageResponseSchema(BaseModel):
    message: str
    data: Any | None = None
