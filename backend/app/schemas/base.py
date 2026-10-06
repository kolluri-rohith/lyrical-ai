from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base schema: snake_case in Python, camelCase in JSON."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        # `modelName` and friends would otherwise clash with pydantic's `model_` namespace.
        protected_namespaces=(),
    )


class ErrorResponse(BaseModel):
    detail: str
    code: str
