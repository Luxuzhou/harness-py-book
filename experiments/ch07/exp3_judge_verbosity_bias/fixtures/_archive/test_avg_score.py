"""avg_score 的预期行为。"""
from avg_score import avg_score


def test_two_scores():
    assert avg_score(['85', '90']) == 87.5


def test_three_scores():
    assert avg_score(['60', '70', '80']) == 70.0


def test_single_score():
    assert avg_score(['100']) == 100.0
