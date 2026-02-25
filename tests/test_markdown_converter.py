import unittest

from utils.converters import convert_markdown_to_html


class TestMarkdownConverter(unittest.TestCase):
    def test_fenced_code_block_keeps_code_content(self):
        md = (
            "## Demo\n\n"
            "```bash\n"
            "echo hello\n"
            "python -V\n"
            "```\n"
        )
        html = convert_markdown_to_html(md)
        self.assertIn('class="language-bash"', html)
        self.assertIn("echo hello", html)
        self.assertIn("python -V", html)

    def test_inline_code_is_escaped(self):
        md = "Use `<script>alert(1)</script>` here."
        html = convert_markdown_to_html(md)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_fenced_code_block_with_windows_newlines(self):
        md = (
            "## Demo\r\n\r\n"
            "```python\r\n"
            "def demo():\r\n"
            "    return 1\r\n"
            "```\r\n"
        )
        html = convert_markdown_to_html(md)
        self.assertIn('class="language-python"', html)
        self.assertIn("def demo()", html)

    def test_fenced_code_block_inside_list_item(self):
        md = (
            "1. 重构建议\n"
            "   ```python\n"
            "   def setup_test_environment(name):\n"
            "       pass\n"
            "   ```\n"
        )
        html = convert_markdown_to_html(md)
        self.assertIn('class="language-python"', html)
        self.assertIn("setup_test_environment", html)
        self.assertNotIn("```python", html)


if __name__ == "__main__":
    unittest.main()
