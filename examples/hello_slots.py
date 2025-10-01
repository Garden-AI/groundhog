# /// script
# requires-python = ">=3.11"
# dependencies = []
#
# ///
"""
Test script to demonstrate tricky serialization/custom types, run locally with
3.10 and remotely with 3.11+. (Python 3.11 changed how __slots__ are handled in
dataclasses etc)
"""

from dataclasses import dataclass

import groundhog_hpc as hog

DIAMOND_ACCT = "cis250223"


class Person:
    __slots__ = ("name", "age")

    def __init__(self, name, age):
        self.name = name
        self.age = age

    def __getstate__(self):
        # Custom getstate that returns a dict
        return {"name": self.name, "age": self.age, "version": 1}

    def __setstate__(self, state):
        self.name = state["name"]
        self.age = state["age"]


@dataclass(slots=True)
class BaseEntity:
    """Base class with __slots__."""

    id: str


@dataclass(slots=True)
class SlottedPerson(BaseEntity):
    """Derived dataclass with __slots__ that inherits from slotted base.

    In Python 3.11+, if 'id' were redeclared here, it would NOT be included
    in the generated __slots__ to prevent overriding the base class slot.
    """

    name: str
    age: int
    city: str


@hog.function(account=DIAMOND_ACCT)
def process_stateful_person(person: Person) -> Person:
    """Function that accepts and returns a slotted class with custom get/set state."""
    return Person(
        name=person.name.upper(),
        age=person.age + 1,
    )


@hog.function(account=DIAMOND_ACCT)
def process_slotted_person(person: SlottedPerson) -> SlottedPerson:
    """Function that accepts and returns a slotted dataclass with inheritance."""
    return SlottedPerson(
        id=person.id,
        name=person.name.upper(),
        age=person.age + 1,
        city=f"{person.city} (processed)",
    )


@hog.harness()
def main():
    # Create a slotted dataclass instance with inheritance
    person = SlottedPerson(id="person-123", name="Bob", age=25, city="Vegas, baby 🎰")
    print(f"Sending: {person}")

    # This should fail due to pickle/slots incompatibility across Python versions
    result = process_slotted_person.remote(person)
    print(f"Received: {result}")

    person2 = Person(name="boB", age=52)
    print(f"Sending: {person2}")
    result2 = process_stateful_person.remote(person2)
    print(f"Received: {result2}")

    return result, result2
