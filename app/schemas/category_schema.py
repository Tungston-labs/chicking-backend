from pydantic import BaseModel


class CategoryResponseSchema(BaseModel):
    name: str
    count: int
