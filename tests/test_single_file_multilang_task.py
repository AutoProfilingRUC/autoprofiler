import tempfile
import unittest
from pathlib import Path

from analysis.manager import analysis_manager
from analysis.task import analyze_python_file


class TestSingleFileMultilangTask(unittest.TestCase):
    def test_single_file_js_analysis_completes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fp = root / "worker.js"
            fp.write_text(
                "import axios from 'axios';\n"
                "async function run(items) { for (const i of items) { await axios.get(i); } }\n",
                encoding="utf-8",
            )
            analysis_id = analysis_manager.create_analysis(str(fp), fp.name, deepseek_config={})
            analyze_python_file(str(fp), analysis_id, {}, root)
            analysis = analysis_manager.get_analysis(analysis_id)
            self.assertEqual(analysis.get("status"), "completed")
            result = analysis.get("result", {})
            self.assertEqual(result.get("analysis_mode"), "single_file_static_multilang")
            code_structure = result.get("code_structure", {})
            self.assertEqual(code_structure.get("basic_info", {}).get("language"), "javascript")


if __name__ == "__main__":
    unittest.main()
