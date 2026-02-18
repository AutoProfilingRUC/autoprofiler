import tempfile
import unittest
from pathlib import Path

from proj_analyser.scanner import scan_project


class TestProjAnalyserScanner(unittest.TestCase):
    def test_scan_includes_structure_overview(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "api").mkdir(parents=True, exist_ok=True)
            (root / "api" / "routes.py").write_text("def main():\n    return 1\n", encoding="utf-8")
            (root / "web.py").write_text("if __name__ == '__main__':\n    pass\n", encoding="utf-8")

            result = scan_project(str(root))

            self.assertIn("top_level_overview", result)
            self.assertIn("directories_top", result)
            self.assertIn("entrypoints_primary", result)
            self.assertIn("entrypoints_low_signal", result)
            self.assertTrue(any(i.get("path") == "api" for i in result["top_level_overview"]))
            self.assertTrue(any(i.get("path") == "." for i in result["directories_top"]))

    def test_scan_separates_low_signal_entrypoints(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "app").mkdir(parents=True, exist_ok=True)
            (root / "tests" / "demo_proj").mkdir(parents=True, exist_ok=True)

            (root / "app" / "main.py").write_text(
                "if __name__ == '__main__':\n    pass\n", encoding="utf-8"
            )
            (root / "tests" / "demo_proj" / "main.py").write_text(
                "if __name__ == '__main__':\n    pass\n", encoding="utf-8"
            )

            result = scan_project(str(root))
            primary_paths = {x.get("file_path") for x in result.get("entrypoints_primary", [])}
            low_signal_paths = {
                x.get("file_path") for x in result.get("entrypoints_low_signal", [])
            }

            self.assertIn("app/main.py", primary_paths)
            self.assertIn("tests/demo_proj/main.py", low_signal_paths)


if __name__ == "__main__":
    unittest.main()
