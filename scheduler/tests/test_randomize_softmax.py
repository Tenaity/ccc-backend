import random

from scheduler.randomize import _softmax_choice


def test_softmax_choice_no_overflow():
    rng = random.Random(42)
    scored = [("a", -1e6), ("b", -1e12), ("c", -1e9)]
    # không raise OverflowError
    cand = _softmax_choice(scored, rng)
    assert cand in {"a", "b", "c"}
