from pydantic import BaseModel, ConfigDict, Field


class ProblemDetail(BaseModel):
    """RFC 7807 Problem Details body (media type ``application/problem+json``).

    Used as the documented response model for every error in the OpenAPI spec.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "about:blank",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Invalid or expired credentials.",
                "instance": "/auth/login",
            }
        }
    )

    type: str = Field(
        default="about:blank",
        description="A URI reference identifying the problem type.",
    )
    title: str = Field(description="A short, human-readable summary of the problem type.")
    status: int = Field(description="The HTTP status code.")
    detail: str | None = Field(
        default=None, description="A human-readable explanation specific to this occurrence."
    )
    instance: str | None = Field(
        default=None, description="A URI reference identifying the specific occurrence."
    )
