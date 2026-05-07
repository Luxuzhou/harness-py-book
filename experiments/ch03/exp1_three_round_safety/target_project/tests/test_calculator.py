"""Incomplete test suite — only covers addition."""
from target_project.calculator import Calculator


class TestCalculator:
    def setup_method(self):
        self.calc = Calculator()

    def test_add(self):
        result = self.calc.calculate(2, "+", 3)
        assert result["result"] == 5

    def test_add_negative(self):
        result = self.calc.calculate(-1, "+", 1)
        assert result["result"] == 0

    # TODO: test_subtract, test_multiply, test_divide are missing
