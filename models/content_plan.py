from pydantic import BaseModel, ConfigDict, Field


class ContentPlanDay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: int = Field(ge=1, le=7)
    goal: str = Field(
        min_length=1,
        max_length=50,
        description="Цель дня: не более 50 символов.",
    )
    topic: str = Field(
        min_length=1,
        max_length=90,
        description="Тема публикации: не более 90 символов.",
    )
    format: str = Field(
        min_length=1,
        max_length=30,
        description="Формат публикации: не более 30 символов.",
    )
    key_message: str = Field(
        min_length=1,
        max_length=120,
        description="Ключевой тезис: не более 120 символов.",
    )
    cta: str = Field(
        min_length=1,
        max_length=70,
        description="Призыв к действию: не более 70 символов.",
    )


class SevenDayContentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    days: list[ContentPlanDay] = Field(
        min_length=7,
        max_length=7,
    )