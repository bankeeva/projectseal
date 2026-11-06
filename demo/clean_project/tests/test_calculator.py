from src.calculator import add, multiply


def test_add() -> None:
    assert add(2, 2) == 4


def test_multiply() -> None:
    assert multiply(3, 4) == 12
