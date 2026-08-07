from pydantic import BaseModel, Field


class ContentPlanDay(BaseModel):
    day: int = Field(ge=1, le=7)
    goal: str = Field(min_length=1, max_length=50)
    topic: str = Field(min_length=1, max_length=90)
    format: str = Field(min_length=1, max_length=30)
    key_message: str = Field(min_length=1, max_length=120)
    cta: str = Field(min_length=1, max_length=70)


class SevenDayContentPlan(BaseModel):
    days: list[ContentPlanDay] = Field(
        min_length=7,
        max_length=7,
    )
