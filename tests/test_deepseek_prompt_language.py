import unittest

from analysis.deepseek_analyzer import DeepSeekAnalyzer


class TestDeepSeekPromptLanguage(unittest.TestCase):
    def test_blackbox_prompt_language(self):
        en_prompt = DeepSeekAnalyzer._create_blackbox_prompt({"duration": 1}, "en")
        zh_prompt = DeepSeekAnalyzer._create_blackbox_prompt({"duration": 1}, "zh")
        self.assertIn("Reply in English", en_prompt)
        self.assertIn("请用中文回复", zh_prompt)

    def test_whitebox_prompt_language(self):
        en_prompt = DeepSeekAnalyzer._create_whitebox_prompt({"functions": []}, "en")
        zh_prompt = DeepSeekAnalyzer._create_whitebox_prompt({"functions": []}, "zh")
        self.assertIn("Reply in English", en_prompt)
        self.assertIn("请用中文回复", zh_prompt)


if __name__ == "__main__":
    unittest.main()
