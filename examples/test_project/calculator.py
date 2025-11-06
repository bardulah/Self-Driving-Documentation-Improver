"""Example module for testing documentation improvement."""


def add(a, b):
    return a + b


def subtract(x, y):
    """Subtract y from x."""
    return x - y


class Calculator:
    def __init__(self, name):
        self.name = name
        self.history = []

    def multiply(self, a, b):
        result = a * b
        self.history.append(f"multiply({a}, {b}) = {result}")
        return result

    def divide(self, numerator, denominator):
        if denominator == 0:
            raise ValueError("Cannot divide by zero")
        return numerator / denominator


async def fetch_calculation(url, params):
    pass
