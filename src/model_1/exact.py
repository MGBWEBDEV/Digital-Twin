"""Exact volume arithmetic.

Volumes are held as fractions.Fraction so that the per-step rule of
design/mathematical_models.md section 4.4 is computed without rounding.
Repeatedly adding 0.01 mL in binary floating point drifts, which can move a
sensor crossing by one simulation step (e.g. 23.999999 mL instead of 24 mL at
19.00 s, check M1-3). Exact arithmetic is mathematically identical to section
4.4 (WP05 section 10 allows any identical formulation). Floats are produced
only for logs.

A float parameter is converted through its shortest decimal representation,
so 0.83 becomes exactly 83/100, the value that was written down.
"""

from decimal import Decimal
from fractions import Fraction


def exact(value) -> Fraction:
    """Convert a number to an exact Fraction."""
    if isinstance(value, bool):
        raise TypeError("a Boolean is not a quantity")
    if isinstance(value, (Fraction, int, Decimal)):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(repr(value))
    raise TypeError(f"not a number: {value!r}")
