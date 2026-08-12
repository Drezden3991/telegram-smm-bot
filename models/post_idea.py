from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
)


PostIdeaText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
    ),
]


class GeneratedPostIdeas(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ideas: list[PostIdeaText] = Field(
        min_length=3,
        max_length=3,
    )