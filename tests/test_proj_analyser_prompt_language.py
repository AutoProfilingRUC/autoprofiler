import unittest
from unittest.mock import patch

from proj_analyser.api_dialogue import run_api_dialogue


class TestProjAnalyserPromptLanguage(unittest.TestCase):
    def _scan_result(self):
        return {
            "summary": {"files_scanned": 1, "entrypoints_found": 1, "total_size_bytes": 10},
            "top_level_overview": [{"path": ".", "files": 1, "size_bytes": 10}],
            "directories_top": [{"path": ".", "files": 1, "size_bytes": 10}],
            "language_distribution": [{"language": "python", "files": 1, "size_bytes": 10}],
            "entrypoints_primary": [{"file_path": "main.py", "score": 100, "reason": ["main"]}],
            "entrypoints_top": [{"file_path": "main.py", "score": 100, "reason": ["main"]}],
            "entrypoints_low_signal": [],
            "files": [{"path": "main.py", "size_bytes": 10, "preview_text": "print('x')"}],
        }

    def _focus_plan(self):
        return {
            "selected_files": [{"path": "main.py", "score": 100, "token_estimate": 10}],
            "summary": {
                "selected_tokens_estimate": 10,
                "selected_plus_agent_tokens_estimate": 100,
            },
        }

    def test_prompt_language_en(self):
        captured = {}

        def fake_call(runtime_config, messages, temperature, max_output_tokens):
            captured["messages"] = messages
            return '{"action":"final_report","title":"t","report_markdown":"ok"}'

        with patch("proj_analyser.api_dialogue.call_chat_api_openai_compatible", side_effect=fake_call):
            run_api_dialogue(
                repo_root=".",
                scan_result=self._scan_result(),
                focus_plan=self._focus_plan(),
                runtime_config={"output_language": "en"},
                query_terms=["performance"],
                max_rounds=1,
            )

        system_prompt = captured["messages"][0]["content"]
        bootstrap = captured["messages"][1]["content"]
        self.assertIn("in English", system_prompt)
        self.assertIn('"output_language": "en"', bootstrap)

    def test_prompt_language_zh(self):
        captured = {}

        def fake_call(runtime_config, messages, temperature, max_output_tokens):
            captured["messages"] = messages
            return '{"action":"final_report","title":"t","report_markdown":"ok"}'

        with patch("proj_analyser.api_dialogue.call_chat_api_openai_compatible", side_effect=fake_call):
            run_api_dialogue(
                repo_root=".",
                scan_result=self._scan_result(),
                focus_plan=self._focus_plan(),
                runtime_config={"output_language": "zh"},
                query_terms=["性能"],
                max_rounds=1,
            )

        system_prompt = captured["messages"][0]["content"]
        bootstrap = captured["messages"][1]["content"]
        self.assertIn("必须使用中文", system_prompt)
        self.assertIn('"output_language": "zh"', bootstrap)


if __name__ == "__main__":
    unittest.main()
