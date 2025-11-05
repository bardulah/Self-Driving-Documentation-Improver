"""Sample Python code for testing documentation improvement."""


def add(a, b):
    return a + b


def multiply(x, y):
    """Multiply two numbers."""
    return x * y


class Calculator:
    def __init__(self, name):
        self.name = name

    def divide(self, numerator, denominator):
        if denominator == 0:
            raise ValueError("Cannot divide by zero")
        return numerator / denominator

    def power(self, base, exponent):
        """Calculate power."""
        return base ** exponent


async def fetch_data(url, timeout=30):
    pass
