import unittest

from retryq.policy import PolicyError, RetryPolicy


def make(**overrides):
    data = {"max_attempts": 5, "base_delay": 1.0}
    data.update(overrides)
    return data


class FromDictRequiredFields(unittest.TestCase):
    def test_missing_max_attempts(self):
        with self.assertRaisesRegex(PolicyError, "max_attempts"):
            RetryPolicy.from_dict({"base_delay": 1.0})

    def test_missing_base_delay(self):
        with self.assertRaisesRegex(PolicyError, "base_delay"):
            RetryPolicy.from_dict({"max_attempts": 3})

    def test_not_a_dict(self):
        with self.assertRaisesRegex(PolicyError, "JSON object"):
            RetryPolicy.from_dict([1, 2, 3])


class FromDictValidation(unittest.TestCase):
    def test_max_attempts_must_be_int(self):
        with self.assertRaisesRegex(PolicyError, "integer"):
            RetryPolicy.from_dict(make(max_attempts="soon"))

    def test_max_attempts_must_be_at_least_one(self):
        with self.assertRaisesRegex(PolicyError, "at least 1"):
            RetryPolicy.from_dict(make(max_attempts=0))

    def test_base_delay_must_be_a_number(self):
        with self.assertRaisesRegex(PolicyError, "number"):
            RetryPolicy.from_dict(make(base_delay="fast"))

    def test_base_delay_cannot_be_negative(self):
        with self.assertRaisesRegex(PolicyError, "negative"):
            RetryPolicy.from_dict(make(base_delay=-1.0))

    def test_multiplier_must_be_at_least_one(self):
        with self.assertRaisesRegex(PolicyError, "at least 1"):
            RetryPolicy.from_dict(make(multiplier=0.5))

    def test_multiplier_must_be_a_number(self):
        with self.assertRaisesRegex(PolicyError, "number"):
            RetryPolicy.from_dict(make(multiplier="double"))

    def test_max_delay_cannot_be_smaller_than_base_delay(self):
        with self.assertRaisesRegex(PolicyError, "max_delay"):
            RetryPolicy.from_dict(make(base_delay=5.0, max_delay=1.0))

    def test_max_delay_must_be_a_number(self):
        with self.assertRaisesRegex(PolicyError, "number"):
            RetryPolicy.from_dict(make(max_delay="a lot"))

    def test_invalid_jitter(self):
        with self.assertRaisesRegex(PolicyError, "jitter"):
            RetryPolicy.from_dict(make(jitter="gaussian"))

    def test_invalid_strategy(self):
        with self.assertRaisesRegex(PolicyError, "strategy"):
            RetryPolicy.from_dict(make(strategy="fibonacci"))

    def test_multiplier_rejected_for_linear_strategy(self):
        with self.assertRaisesRegex(PolicyError, "multiplier"):
            RetryPolicy.from_dict(make(strategy="linear", multiplier=3.0))

    def test_multiplier_rejected_for_constant_strategy(self):
        with self.assertRaisesRegex(PolicyError, "multiplier"):
            RetryPolicy.from_dict(make(strategy="constant", multiplier=3.0))

    def test_defaults(self):
        policy = RetryPolicy.from_dict(make())
        self.assertEqual(policy.multiplier, 2.0)
        self.assertIsNone(policy.max_delay)
        self.assertEqual(policy.jitter, "none")
        self.assertEqual(policy.strategy, "exponential")

    def test_accepts_all_fields(self):
        policy = RetryPolicy.from_dict(
            make(multiplier=3.0, max_delay=20.0, jitter="equal")
        )
        self.assertEqual(policy.max_attempts, 5)
        self.assertEqual(policy.base_delay, 1.0)
        self.assertEqual(policy.multiplier, 3.0)
        self.assertEqual(policy.max_delay, 20.0)
        self.assertEqual(policy.jitter, "equal")


class WillRetry(unittest.TestCase):
    def test_boundaries(self):
        policy = RetryPolicy.from_dict(make(max_attempts=3))
        self.assertFalse(policy.will_retry(0))
        self.assertTrue(policy.will_retry(1))
        self.assertTrue(policy.will_retry(3))
        self.assertFalse(policy.will_retry(4))


class DelayBounds(unittest.TestCase):
    def test_rejects_attempt_below_one(self):
        policy = RetryPolicy.from_dict(make())
        with self.assertRaisesRegex(PolicyError, "attempt"):
            policy.delay_bounds(0)

    def test_no_jitter_is_a_single_value(self):
        policy = RetryPolicy.from_dict(make(base_delay=1.0, multiplier=2.0))
        self.assertEqual(policy.delay_bounds(1), (1.0, 1.0))
        self.assertEqual(policy.delay_bounds(2), (2.0, 2.0))
        self.assertEqual(policy.delay_bounds(3), (4.0, 4.0))

    def test_full_jitter_ranges_from_zero(self):
        policy = RetryPolicy.from_dict(make(base_delay=1.0, jitter="full"))
        lo, hi = policy.delay_bounds(3)
        self.assertEqual(lo, 0.0)
        self.assertEqual(hi, 4.0)

    def test_equal_jitter_keeps_half_fixed(self):
        policy = RetryPolicy.from_dict(make(base_delay=1.0, jitter="equal"))
        lo, hi = policy.delay_bounds(3)
        self.assertEqual(lo, 2.0)
        self.assertEqual(hi, 4.0)

    def test_max_delay_caps_before_jitter(self):
        policy = RetryPolicy.from_dict(
            make(base_delay=1.0, multiplier=2.0, max_delay=3.0, jitter="equal")
        )
        # uncapped delay at attempt 3 would be 4.0, capped to 3.0
        lo, hi = policy.delay_bounds(3)
        self.assertEqual(hi, 3.0)
        self.assertEqual(lo, 1.5)

    def test_linear_strategy_grows_by_attempt_number(self):
        policy = RetryPolicy.from_dict(make(base_delay=1.5, strategy="linear"))
        self.assertEqual(policy.delay_bounds(1), (1.5, 1.5))
        self.assertEqual(policy.delay_bounds(2), (3.0, 3.0))
        self.assertEqual(policy.delay_bounds(3), (4.5, 4.5))

    def test_constant_strategy_never_grows(self):
        policy = RetryPolicy.from_dict(make(base_delay=2.0, strategy="constant"))
        self.assertEqual(policy.delay_bounds(1), (2.0, 2.0))
        self.assertEqual(policy.delay_bounds(5), (2.0, 2.0))

    def test_max_delay_still_caps_linear_strategy(self):
        policy = RetryPolicy.from_dict(
            make(base_delay=1.0, strategy="linear", max_delay=2.5)
        )
        self.assertEqual(policy.delay_bounds(3), (2.5, 2.5))


class Schedule(unittest.TestCase):
    def test_length_matches_max_attempts(self):
        policy = RetryPolicy.from_dict(make(max_attempts=4))
        self.assertEqual(len(policy.schedule()), 4)

    def test_attempts_are_sequential(self):
        policy = RetryPolicy.from_dict(make(max_attempts=3))
        attempts = [row[0] for row in policy.schedule()]
        self.assertEqual(attempts, [1, 2, 3])

    def test_cumulative_totals_are_running_sums(self):
        policy = RetryPolicy.from_dict(
            make(max_attempts=3, base_delay=1.0, multiplier=2.0)
        )
        rows = policy.schedule()
        # no jitter, so min == max at each step: 1, 2, 4
        self.assertEqual([row[3] for row in rows], [1.0, 3.0, 7.0])
        self.assertEqual([row[4] for row in rows], [1.0, 3.0, 7.0])

    def test_cumulative_totals_with_jitter_track_min_and_max_separately(self):
        policy = RetryPolicy.from_dict(
            make(max_attempts=3, base_delay=1.0, multiplier=2.0, jitter="full")
        )
        rows = policy.schedule()
        self.assertEqual([row[3] for row in rows], [0.0, 0.0, 0.0])
        self.assertEqual([row[4] for row in rows], [1.0, 3.0, 7.0])


if __name__ == "__main__":
    unittest.main()
