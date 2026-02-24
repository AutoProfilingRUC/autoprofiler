import unittest
from unittest.mock import patch

from utils import runtime_capabilities as rc


class TestRuntimeCapabilities(unittest.TestCase):
    def tearDown(self):
        rc.clear_runtime_capabilities_cache()

    def test_detect_has_expected_shape(self):
        caps = rc.detect_runtime_capabilities()
        self.assertIn("environment", caps)
        self.assertIn("modules", caps)
        self.assertIn("commands", caps)
        self.assertIn("features", caps)
        self.assertIn("pdf_export", caps["features"])

    def test_pdf_unavailable_when_markdown_missing(self):
        def fake_module_available(name):
            if name == "markdown":
                return False
            return True

        with patch("utils.runtime_capabilities._module_available", side_effect=fake_module_available):
            caps = rc.detect_runtime_capabilities()

        pdf = caps.get("features", {}).get("pdf_export", {})
        self.assertFalse(pdf.get("available"))
        self.assertIn("markdown", str(pdf.get("reason", "")))

    def test_capability_cache_refresh(self):
        rc.clear_runtime_capabilities_cache()
        with patch(
            "utils.runtime_capabilities.detect_runtime_capabilities",
            side_effect=[
                {"v": 1, "features": {}},
                {"v": 2, "features": {}},
            ],
        ):
            first = rc.get_runtime_capabilities()
            second = rc.get_runtime_capabilities()
            third = rc.get_runtime_capabilities(refresh=True)

        self.assertEqual(first.get("v"), 1)
        self.assertEqual(second.get("v"), 1)
        self.assertEqual(third.get("v"), 2)


if __name__ == "__main__":
    unittest.main()
