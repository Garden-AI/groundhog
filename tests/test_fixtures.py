"""Test fixtures for groundhog_hpc tests.

This module provides test functions in a separate module from test_function.py,
allowing for realistic testing of cross-module behavior in Function.local().
"""

import groundhog_hpc as hog


# Undecorated functions - for simple test cases and mocking
def simple_function():
    """A simple test function that returns a string."""
    return "results!"


def add(a, b):
    """A simple test function that adds two numbers."""
    return a + b


def multiply(x, y):
    """A simple test function that multiplies two numbers."""
    return x * y


# Decorated @hog.function() - for testing cross-module .local() behavior
@hog.function()
def cross_module_function(x):
    """A decorated function for testing cross-module .local() calls."""
    return x * 2


@hog.function()
def nested_local_caller(y):
    """A function that calls another .local() - tests nested behavior."""
    return cross_module_function.local(y)
