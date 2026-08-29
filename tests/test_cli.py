import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

import cutover_cli


class UnifiedCliTests(unittest.TestCase):
    def test_help_lists_primary_control_room(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = cutover_cli.main(["--help"])
        self.assertEqual(result, 0)
        self.assertIn("control-room", output.getvalue())
        self.assertIn("validate", output.getvalue())

    def test_validate_dispatches_to_existing_engine(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = cutover_cli.main(["validate", "examples/customer-cutover.json"])
        self.assertEqual(result, 0)
        self.assertIn('"valid": true', output.getvalue())

    def test_plan_dispatches_to_existing_engine(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = cutover_cli.main(["plan", "examples/customer-cutover.json"])
        self.assertEqual(result, 0)
        self.assertIn('"executable_now"', output.getvalue())

    def test_unknown_command_fails_loudly(self):
        error = io.StringIO()
        with redirect_stderr(error):
            result = cutover_cli.main(["unknown"])
        self.assertEqual(result, 2)
        self.assertIn("Unknown command", error.getvalue())


if __name__ == "__main__":
    unittest.main()
