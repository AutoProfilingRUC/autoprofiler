import unittest

from proj_analyser.focus import build_focus_plan


class TestProjAnalyserFocus(unittest.TestCase):
    def test_focus_selects_entrypoint(self):
        scan_result = {
            "entrypoints_top": [
                {"file_path": "app/main.py", "score": 88, "reason": ["python_main_guard"]}
            ],
            "files": [
                {
                    "path": "app/main.py",
                    "size_bytes": 500,
                    "preview_text": "if __name__ == '__main__':\n    main()",
                },
                {
                    "path": "services/auth.py",
                    "size_bytes": 1200,
                    "preview_text": "def login(user):\n    pass",
                },
                {
                    "path": "requirements.txt",
                    "size_bytes": 80,
                    "preview_text": "flask\npsutil\n",
                },
            ],
        }
        plan = build_focus_plan(
            scan_result=scan_result,
            query_terms=["login"],
            top_files=2,
            token_budget=1000,
            bytes_per_token=4,
        )
        selected = plan["selected_files"]
        self.assertGreaterEqual(len(selected), 1)
        paths = [x["path"] for x in selected]
        self.assertIn("app/main.py", paths)
        self.assertLessEqual(plan["summary"]["selected_count"], 2)
        self.assertIn("selected_plus_agent_tokens_estimate", plan["summary"])
        self.assertGreaterEqual(
            plan["summary"]["selected_plus_agent_tokens_estimate"],
            plan["summary"]["selected_tokens_estimate"],
        )

    def test_focus_penalizes_low_signal_paths(self):
        scan_result = {
            "entrypoints_top": [
                {"file_path": "tests/test_main.py", "score": 90, "reason": ["python_main_guard"]}
            ],
            "files": [
                {
                    "path": "tests/test_main.py",
                    "size_bytes": 400,
                    "preview_text": "if __name__ == '__main__': pass",
                },
                {
                    "path": "autoprofiler/runner.py",
                    "size_bytes": 5000,
                    "preview_text": "class Runner: pass",
                },
            ],
        }
        plan = build_focus_plan(
            scan_result=scan_result,
            query_terms=[],
            top_files=1,
            token_budget=10000,
            bytes_per_token=4,
        )
        selected = plan["selected_files"]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["path"], "autoprofiler/runner.py")


if __name__ == "__main__":
    unittest.main()
