import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from retryq import cli

POLICY = {
    "max_attempts": 3,
    "base_delay": 1.0,
    "multiplier": 2.0,
}


def run(argv):
    out = io.StringIO()
    with mock.patch.object(cli.sys, "stdin", io.StringIO(json.dumps(POLICY))):
        with redirect_stdout(out):
            code = cli.main(argv)
    return code, out.getvalue()


class JsonFormat(unittest.TestCase):
    def test_full_schedule_is_a_json_array(self):
        code, output = run(["-", "--format", "json"])
        self.assertEqual(code, 0)
        rows = json.loads(output)
        self.assertEqual(len(rows), 3)
        self.assertEqual(
            rows[0],
            {"attempt": 1, "delay_min": 1.0, "delay_max": 1.0, "elapsed_min": 1.0, "elapsed_max": 1.0},
        )
        self.assertEqual(rows[2]["elapsed_max"], 7.0)

    def test_single_attempt_that_will_retry(self):
        code, output = run(["-", "--attempt", "2", "--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(
            json.loads(output),
            {"attempt": 2, "will_retry": True, "delay_min": 2.0, "delay_max": 2.0},
        )

    def test_single_attempt_beyond_max_attempts(self):
        code, output = run(["-", "--attempt", "9", "--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(
            json.loads(output),
            {"attempt": 9, "will_retry": False, "max_attempts": 3},
        )


class Simulate(unittest.TestCase):
    def test_full_simulation_is_a_json_array(self):
        code, output = run(["-", "--simulate", "--seed", "1", "--format", "json"])
        self.assertEqual(code, 0)
        rows = json.loads(output)
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertEqual(set(row), {"attempt", "delay", "elapsed"})

    def test_same_seed_is_reproducible(self):
        _, first = run(["-", "--simulate", "--seed", "7", "--format", "json"])
        _, second = run(["-", "--simulate", "--seed", "7", "--format", "json"])
        self.assertEqual(first, second)

    def test_single_attempt_simulated(self):
        code, output = run(["-", "--simulate", "--seed", "1", "--attempt", "2", "--format", "json"])
        self.assertEqual(code, 0)
        row = json.loads(output)
        self.assertEqual(row["attempt"], 2)
        self.assertTrue(row["will_retry"])
        self.assertIn("delay", row)

    def test_single_attempt_beyond_max_attempts(self):
        code, output = run(["-", "--simulate", "--attempt", "9", "--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(
            json.loads(output),
            {"attempt": 9, "will_retry": False, "max_attempts": 3},
        )

    def test_seed_without_simulate_is_rejected(self):
        code, output = run(["-", "--seed", "1"])
        self.assertEqual(code, 1)

    def test_table_format_has_a_delay_and_elapsed_column(self):
        code, output = run(["-", "--simulate", "--seed", "1"])
        self.assertEqual(code, 0)
        self.assertIn("delay", output)
        self.assertIn("elapsed", output)


if __name__ == "__main__":
    unittest.main()
