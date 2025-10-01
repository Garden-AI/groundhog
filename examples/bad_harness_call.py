# /// script
# requires-python = ">=3.10"
# dependencies = []
#
# ///
"""
This one should not run, because a harness function would be called directly from the script
"""

from dataclasses import dataclass

import groundhog_hpc as hog

DIAMOND_ACCT = "cis250223"


@dataclass
class Person:
    name: str
    age: int
    hobbies: list[str]


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
    # Test custom dataclass
    dataclass_arg = Person(name="Alice", age=30, hobbies=["reading", "hiking"])
    dataclass_result = hello_dataclass.remote(dataclass_arg)
    print(f"Dataclass test: {dataclass_arg} -> {dataclass_result}")

    return dataclass_result


def _illegal_harness_invoker():
    return main()  # not allowed!


print(_illegal_harness_invoker())
