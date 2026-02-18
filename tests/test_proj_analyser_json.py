import unittest

from proj_analyser.api_dialogue import extract_loose_json_object


class TestProjAnalyserJson(unittest.TestCase):
    def test_extract_plain_json(self):
        text = '{"action":"final_report","report_markdown":"ok"}'
        out = extract_loose_json_object(text)
        self.assertIsNotNone(out)
        self.assertEqual(out["action"], "final_report")

    def test_extract_fenced_json(self):
        text = "```json\n{\"action\":\"need_files\",\"files\":[{\"path\":\"main.py\"}]}\n```"
        out = extract_loose_json_object(text)
        self.assertIsNotNone(out)
        self.assertEqual(out["action"], "need_files")

    def test_extract_embedded_json(self):
        text = (
            "Some words before "
            '{"action":"final_report","title":"x","report_markdown":"hello"}'
            " and after"
        )
        out = extract_loose_json_object(text)
        self.assertIsNotNone(out)
        self.assertEqual(out["title"], "x")


if __name__ == "__main__":
    unittest.main()

