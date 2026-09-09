import unittest
from unittest.mock import patch
from tests_m2.timeout_headroom import timeout_factor, controller_headroom
from screen2xyz_m2.controller import LiveSessionController


class TimeoutHeadroomTests(unittest.TestCase):
    def test_real_runner_enters_headroom_context(self):
        from tests_m2 import run_m2_integration, timeout_headroom
        from types import SimpleNamespace
        seen=[]
        def run(_suite):
            seen.append(LiveSessionController._request_timeout_ms(None))
            return SimpleNamespace(testsRun=0, failures=[], errors=[], skipped=[], wasSuccessful=lambda:True)
        with patch.dict('os.environ', {'S2XYZ_M2_TEST_TIMEOUT_FACTOR':'3'}), \
             patch.dict('sys.modules', {'timeout_headroom':timeout_headroom}), \
             patch.object(run_m2_integration, '_skip_reason', return_value=None), \
             patch.object(LiveSessionController, '_request_timeout_ms', lambda self:2000), \
             patch.object(run_m2_integration.unittest.TextTestRunner, 'run', side_effect=run):
            self.assertEqual(run_m2_integration.main(),0)
            self.assertEqual(seen,[6000])
            self.assertEqual(LiveSessionController._request_timeout_ms(None),2000)

    def test_invalid_factors(self):
        for value in ('0', '-1', 'nan', 'inf', '11', 'garbage'):
            with self.subTest(value=value), patch.dict('os.environ', {'S2XYZ_M2_TEST_TIMEOUT_FACTOR': value}):
                with self.assertRaises(ValueError): timeout_factor()

    def test_scaling_and_restoration_even_after_exception(self):
        original = LiveSessionController._request_timeout_ms
        with patch.object(LiveSessionController, '_request_timeout_ms', lambda self: 2001):
            for factor in ('1', '2.5'):
                with patch.dict('os.environ', {'S2XYZ_M2_TEST_TIMEOUT_FACTOR': factor}):
                    with self.assertRaisesRegex(RuntimeError, 'deliberate'):
                        with controller_headroom():
                            self.assertEqual(LiveSessionController._request_timeout_ms(None), 2001 if factor == '1' else 5003)
                            raise RuntimeError('deliberate')
                    self.assertEqual(LiveSessionController._request_timeout_ms(None), 2001)
        self.assertIs(LiveSessionController._request_timeout_ms, original)
