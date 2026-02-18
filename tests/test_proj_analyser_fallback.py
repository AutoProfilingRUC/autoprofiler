import unittest

from proj_analyser.service import analyze_project_with_api


class TestProjAnalyserFallback(unittest.TestCase):
    def test_fallback_without_model_config(self):
        result = analyze_project_with_api(
            project_path=".",
            deepseek_config={},
            query_terms=["performance"],
            top_files=6,
            token_budget=5000,
            max_rounds=2,
        )
        self.assertEqual(result.get("analysis_mode"), "fallback_local")
        self.assertTrue(result.get("report_markdown", "").strip())
        self.assertIn("Local Fallback Mode", result.get("report_markdown", ""))
        self.assertIn("code_structure", result)
        self.assertEqual(result["code_structure"].get("type"), "project")
        self.assertIn("deepseek_results", result)
        self.assertIn("local_fallback", result["deepseek_results"])
        self.assertIn("docs_report_path", result.get("outputs", {}))
        self.assertTrue(result["outputs"]["docs_report_path"].endswith("report_project_api.md"))
        normalized = result["outputs"]["docs_report_path"].replace("\\", "/")
        self.assertIn("/docs/generated/project/", normalized)


if __name__ == "__main__":
    unittest.main()
