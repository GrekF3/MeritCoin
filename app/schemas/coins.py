from pydantic import BaseModel, Field


class CoinOperation(BaseModel):
    amount: int = Field(gt=0)
    reason: str = Field(min_length=1)
