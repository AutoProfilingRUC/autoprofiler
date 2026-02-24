import tempfile
import unittest
from pathlib import Path
import importlib.util

from models.deepseek_config import DeepSeekConfig


@unittest.skipUnless(importlib.util.find_spec("flask"), "flask not installed")
class TestApiRoutesHardening(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        from web import create_app

        class TestConfig:
            SECRET_KEY = "test"
            TESTING = True
            MAX_CONTENT_LENGTH = 50 * 1024 * 1024
            JSON_AS_ASCII = False
            PERMANENT_SESSION_LIFETIME = 3600
            BASE_DIR = root
            UPLOAD_FOLDER = root / "uploads"
            STATIC_FOLDER = root / "static"
            TEMPLATE_FOLDER = root / "templates"
            DEEPSEEK_CONFIG_FILE = UPLOAD_FOLDER / "deepseek_config.json"
            HOST = "127.0.0.1"
            PORT = 5000
            DEBUG = False

        self.config = TestConfig
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    def tearDown(self):
        self._tmp.cleanup()

    def test_reject_relative_file_path(self):
        resp = self.client.post(
            "/api/analyze-file-path",
            json={"file_path": "./relative.py"},
        )
        self.assertEqual(resp.status_code, 400)
        payload = resp.get_json() or {}
        self.assertIn("绝对路径", payload.get("error", ""))

    def test_reject_relative_project_path(self):
        resp = self.client.post(
            "/api/proj-analyser/analyze",
            json={"project_path": "./relative_project"},
        )
        self.assertEqual(resp.status_code, 400)
        payload = resp.get_json() or {}
        self.assertIn("绝对路径", payload.get("error", ""))

    def test_deepseek_config_get_masks_secrets_and_save_preserves_existing(self):
        original = {
            "api_key": "sk-test-secret-1234",
            "api_url": "https://api.deepseek.com/v1/chat/completions",
            "model": "deepseek-chat",
            "output_language": "zh",
        }
        save_resp = self.client.post("/api/deepseek/config", json=original)
        self.assertEqual(save_resp.status_code, 200)

        get_resp = self.client.get("/api/deepseek/config")
        self.assertEqual(get_resp.status_code, 200)
        config = (get_resp.get_json() or {}).get("config", {})
        self.assertEqual(config.get("api_key"), "")
        self.assertTrue(config.get("api_key_configured"))
        self.assertTrue(str(config.get("api_key_masked", "")).endswith("1234"))

        update_resp = self.client.post(
            "/api/deepseek/config",
            json={
                "api_key": "",
                "model": "deepseek-chat-v2",
            },
        )
        self.assertEqual(update_resp.status_code, 200)

        stored = DeepSeekConfig.load(self.config.DEEPSEEK_CONFIG_FILE)
        self.assertEqual(stored.get("api_key"), "sk-test-secret-1234")
        self.assertEqual(stored.get("model"), "deepseek-chat-v2")

    def test_get_system_capabilities(self):
        resp = self.client.get("/api/system/capabilities")
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json() or {}
        self.assertTrue(payload.get("success"))
        caps = payload.get("capabilities", {})
        self.assertIn("features", caps)
        self.assertIn("pdf_export", caps.get("features", {}))


if __name__ == "__main__":
    unittest.main()
