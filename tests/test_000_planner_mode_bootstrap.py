import os
from pathlib import Path
import unittest


# Keep unittest discovery on the deterministic planner unless a specific test
# explicitly overrides the mode in its own environment patch.
os.environ.setdefault("CLIPFORGE_PLANNER_MODE", "deterministic")


class BootstrapEnvironmentTests(unittest.TestCase):
    def test_runtime_config_isolated_from_local_machine_defaults(self):
        expected_suffix = str(Path(".tmp") / "runtime_config.unittest.json")
        runtime_config_path = os.environ.get("CLIPFORGE_RUNTIME_CONFIG_PATH", "")

        self.assertTrue(
            runtime_config_path,
            "unittest bootstrap should isolate runtime config from local defaults",
        )
        self.assertTrue(runtime_config_path.endswith(expected_suffix))
