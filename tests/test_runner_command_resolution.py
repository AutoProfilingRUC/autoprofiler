from __future__ import annotations

import unittest
from unittest.mock import patch

from autoprofiler.runner import Runner


class RunnerCommandResolutionTest(unittest.TestCase):
    def test_rewrite_python_when_alias_missing(self) -> None:
        with patch("autoprofiler.runner.shutil.which", return_value=None), patch(
            "autoprofiler.runner.sys.executable", "/usr/bin/python3"
        ):
            resolved = Runner._resolve_command(["python", "-V"])
        self.assertEqual(resolved[0], "/usr/bin/python3")
        self.assertEqual(resolved[1:], ["-V"])

    def test_keep_python_when_alias_exists(self) -> None:
        with patch("autoprofiler.runner.shutil.which", return_value="/usr/bin/python"):
            resolved = Runner._resolve_command(["python", "-V"])
        self.assertEqual(resolved, ["python", "-V"])


if __name__ == "__main__":
    unittest.main()

