# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# ///
"""
This one shows off argument / serialization handling, including a simple custom class
"""

from dataclasses import dataclass

import groundhog_hpc as hog

GARDEN_ACCT = "cis250461"
DIAMOND_ACCT = "cis250223"


@dataclass
class Person:
    name: str
    age: int
    hobbies: list[str]


@hog.function(account=DIAMOND_ACCT)
def hello_arguments_json(data: dict, multiplier: int):
    """Simple function that accepts and returns JSON-serializable types."""
    result = {k: v * multiplier for k, v in data.items()}
    return result


@hog.function(account=DIAMOND_ACCT)
def hello_arguments_pkl(obj):
    """Function that accepts and returns non-JSON-serializable types (sets, custom classes)."""
    if isinstance(obj, set):
        return {f"processed_{item}" for item in obj}
    return {type(obj).__name__, "processed"}


@hog.function(account=DIAMOND_ACCT)
def hello_dataclass(person: Person):
    """Function that accepts and returns a custom dataclass."""
    # Modify the person and return a new instance
    return Person(
        name=person.name.upper(),
        age=person.age + 1,
        hobbies=person.hobbies + ["groundhog testing"],
    )


@hog.harness()
def main():
    # Test JSON-serializable types
    json_arg = {"a": 1, "b": 2, "c": 3}
    json_result = hello_arguments_json.remote(json_arg, 10)
    print(f"JSON test: {json_arg} -> {json_result}")

    # Test non-JSON-serializable types (set)
    pickle_arg = {"apple", "banana", "cherry"}
    pickle_result = hello_arguments_pkl.remote(pickle_arg)
    print(f"Pickle test: {pickle_arg} -> {pickle_result}")

    # Test custom dataclass
    dataclass_arg = Person(name="Alice", age=30, hobbies=["reading", "hiking"])
    dataclass_result = hello_dataclass.remote(dataclass_arg)
    print(f"Dataclass test: {dataclass_arg} -> {dataclass_result}")

    return json_result, pickle_result, dataclass_result
