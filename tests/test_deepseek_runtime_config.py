import unittest

from models.deepseek_config import DeepSeekConfig


class TestDeepSeekRuntimeConfig(unittest.TestCase):
    def test_remote_runtime(self):
        cfg = {
            "api_key": "k",
            "api_url": "https://api.deepseek.com/v1/chat/completions",
            "model": "deepseek-chat",
            "output_language": "en",
        }
        runtime = DeepSeekConfig.resolve_runtime(cfg)
        self.assertTrue(runtime["enabled"])
        self.assertEqual(runtime["mode"], "remote")
        self.assertEqual(runtime["output_language"], "en")

    def test_local_runtime_priority(self):
        cfg = {
            "api_key": "k",
            "api_url": "https://api.deepseek.com/v1/chat/completions",
            "model": "deepseek-chat",
            "use_local_model": True,
            "local_api_url": "http://127.0.0.1:11434/v1/chat/completions",
            "local_model": "qwen2.5-coder:7b",
        }
        runtime = DeepSeekConfig.resolve_runtime(cfg)
        self.assertTrue(runtime["enabled"])
        self.assertEqual(runtime["mode"], "local")
        self.assertEqual(runtime["model"], "qwen2.5-coder:7b")
        self.assertEqual(runtime["output_language"], "zh")

    def test_none_runtime(self):
        runtime = DeepSeekConfig.resolve_runtime({})
        self.assertFalse(runtime["enabled"])
        self.assertEqual(runtime["mode"], "none")
        self.assertEqual(runtime["output_language"], "zh")

    def test_normalize_output_language(self):
        self.assertEqual(DeepSeekConfig.normalize_output_language("english"), "en")
        self.assertEqual(DeepSeekConfig.normalize_output_language("zh-cn"), "zh")
        self.assertEqual(DeepSeekConfig.normalize_output_language("invalid"), "zh")


if __name__ == "__main__":
    unittest.main()
