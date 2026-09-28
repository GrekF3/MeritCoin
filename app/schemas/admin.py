from pydantic import BaseModel


class GroupCreate(BaseModel):
    name: str
    slug: str
    invite_code: str | None = None
