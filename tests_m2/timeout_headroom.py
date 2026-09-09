"""Opt-in integration headroom; no production defaults or timing assertions change."""
from contextlib import contextmanager
import math
import os
from unittest.mock import patch


def timeout_factor():
    factor = float(os.environ.get('S2XYZ_M2_TEST_TIMEOUT_FACTOR', '1'))
    if not math.isfinite(factor) or not 1 <= factor <= 10:
        raise ValueError('S2XYZ_M2_TEST_TIMEOUT_FACTOR must be finite in [1, 10]')
    return factor


@contextmanager
def controller_headroom():
    from screen2xyz_m2.controller import LiveSessionController
    factor = timeout_factor()
    original = LiveSessionController._request_timeout_ms
    def scaled(self):
        return math.ceil(original(self) * factor)
    with patch.object(LiveSessionController, '_request_timeout_ms', scaled):
        yield factor
