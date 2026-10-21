"""Simple workflow ordering and failure checks, without network or device access."""

import unittest
from unittest.mock import patch
import simple_workflow as simple


class SimpleWorkflowTests(unittest.TestCase):
    def test_selected_bit_and_mcs_format_survive_prepared_file_programming(self):
        for kind in ("bit", "mcs"):
            command = simple.firmware_file_command(
                "loader",
                "amaneq-v4",
                "lrtdc",
                kind,
                "prepared." + kind,
                ["--cable", "hs3", "--serial", "SYNTHETIC"],
            )
            self.assertEqual(command[command.index("--format") + 1], kind)
            self.assertEqual(command[command.index("--file") + 1], "prepared." + kind)
            self.assertNotIn("--latest", command)
            self.assertEqual(command[command.index("--serial") + 1], "SYNTHETIC")
        with self.assertRaises(ValueError):
            simple.firmware_file_command(
                "loader", "amaneq-v4", "lrtdc", "hex", "image", []
            )

    def test_initialization_and_persistent_ip_are_explicit(self):
        with (
            patch.object(simple.operations, "license_kind", return_value="MPCX"),
            patch.object(simple.operations, "utility_command") as command,
        ):
            command.side_effect = lambda root, host, action, *args, **kwargs: [
                action,
                str(kwargs),
            ]
            plan = simple.prepare_network(
                ".", "192.168.10.10", "synthetic.mpcx", "192.168.10.25"
            )
            license_call = next(
                c for c in command.call_args_list if c.args[2] == "Write MPC/MPCX"
            )
            self.assertIs(license_call.kwargs["initialize"], True)
            ip_call = next(
                c for c in command.call_args_list if c.args[2] == "Write IP only"
            )
            self.assertIs(ip_call.kwargs["current"], False)
            self.assertEqual(ip_call.kwargs["new_ip"], "192.168.10.25")
            self.assertEqual(plan.saved_ip, "192.168.10.25")

    def test_readback_order_and_stop_on_any_failure(self):
        plan = simple.NetworkPlan(
            "192.168.10.10",
            "192.168.10.25",
            ("check",),
            ("license",),
            ("license-read",),
            ("ip",),
            ("ip-read",),
        )
        expected = ["check", "clock", "license", "license-read", "ip", "ip-read"]
        for failure in [None] + expected:
            seen = []

            def step(name):
                seen.append(name)
                if name == failure:
                    raise RuntimeError("synthetic failure")

            def clock(host, preset, persist):
                self.assertEqual(preset, simple.operations.DEFAULT_CLOCK_PRESET)
                self.assertTrue(persist)
                step("clock")
                return "clock verified"

            if failure is None:
                simple.configure_network(
                    plan, lambda cmd: step(cmd[0]), lambda message: None, clock
                )
                self.assertEqual(seen, expected)
            else:
                with self.assertRaises(RuntimeError):
                    simple.configure_network(
                        plan, lambda cmd: step(cmd[0]), lambda message: None, clock
                    )
                self.assertEqual(seen, expected[: expected.index(failure) + 1])


if __name__ == "__main__":
    unittest.main()
