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


if __name__ == "__main__":
    unittest.main()
