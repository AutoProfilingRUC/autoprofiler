import tempfile
import unittest
from pathlib import Path

from analysis.code_analyzer import CodeAnalyzer


class TestCodeAnalyzerMultilang(unittest.TestCase):
    def test_detect_language(self):
        self.assertEqual(CodeAnalyzer.detect_language("a.py"), "python")
        self.assertEqual(CodeAnalyzer.detect_language("a.ts"), "typescript")
        self.assertEqual(CodeAnalyzer.detect_language("a.cpp"), "cpp")

    def test_analyze_javascript_structure(self):
        with tempfile.TemporaryDirectory() as td:
            fp = Path(td) / "service.js"
            fp.write_text(
                "import fs from 'fs';\n"
                "class Cache {\n"
                "  constructor() {}\n"
                "}\n"
                "function processData(items) { for (const i of items) { console.log(i); } }\n",
                encoding="utf-8",
            )
            result = CodeAnalyzer.analyze_code_structure(fp)
            self.assertNotIn("error", result)
            self.assertEqual(result["basic_info"]["language"], "javascript")
            self.assertGreaterEqual(len(result.get("functions", [])), 1)
            self.assertGreaterEqual(len(result.get("classes", [])), 1)
            self.assertIn("performance_signals", result)


if __name__ == "__main__":
    unittest.main()
