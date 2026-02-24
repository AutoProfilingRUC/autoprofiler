import unittest
from unittest.mock import patch

from proj_analyser.api_dialogue import run_api_dialogue
from proj_analyser.service import _merge_report_sections


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

    def test_token_usage_aggregation(self):
        def fake_call(runtime_config, messages, temperature, max_output_tokens):
            return {
                "content": '{"action":"final_report","title":"t","report_markdown":"ok"}',
                "usage": {"prompt_tokens": 10, "completion_tokens": 25, "total_tokens": 35},
            }

        with patch("proj_analyser.api_dialogue.call_chat_api_openai_compatible", side_effect=fake_call):
            result = run_api_dialogue(
                repo_root=".",
                scan_result=self._scan_result(),
                focus_plan=self._focus_plan(),
                runtime_config={"output_language": "zh"},
                query_terms=["性能"],
                max_rounds=1,
            )

        usage = result.get("token_usage_summary", {})
        self.assertEqual(usage.get("prompt_tokens"), 10)
        self.assertEqual(usage.get("completion_tokens"), 25)
        self.assertEqual(usage.get("total_tokens"), 35)
        self.assertEqual(usage.get("rounds_with_usage"), 1)

    def test_report_includes_token_usage_section(self):
        report = _merge_report_sections(
            base_report="# Project Performance Report\n\nok",
            scan_result=self._scan_result(),
            focus_plan=self._focus_plan(),
            analysis_mode="project_api",
            runtime_mode="api",
            rounds=2,
            token_usage_summary={
                "prompt_tokens": 11,
                "completion_tokens": 22,
                "total_tokens": 33,
                "rounds_with_usage": 2,
            },
            output_language="en",
        )
        self.assertIn("## API Token Usage", report)
        self.assertIn("- Total tokens: 33", report)


if __name__ == "__main__":
    unittest.main()
