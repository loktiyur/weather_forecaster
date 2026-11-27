from enum import StrEnum


# In core (like Language), because user preferences use it too. A comment, not a docstring:
# Pydantic would copy a docstring into the OpenAPI schema.
class Units(StrEnum):
    METRIC = "metric"
    IMPERIAL = "imperial"
