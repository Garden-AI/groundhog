import json
from typing import Any


def serialize(obj: Any) -> str:
    return json.dumps(obj)


def deserialize(payload: str) -> Any:
    return json.loads(payload)
