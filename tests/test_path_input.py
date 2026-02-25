import unittest

from utils.path_input import normalize_user_path


class TestPathInput(unittest.TestCase):
    def test_normalize_quoted_windows_path(self):
        src = '"E:\\MY_WORK\\CS\\etrip-profiling\\autoprofiler\\tests\\test_extended.py"'
        self.assertEqual(
            normalize_user_path(src),
            r"E:\MY_WORK\CS\etrip-profiling\autoprofiler\tests\test_extended.py",
        )

    def test_normalize_single_quoted_windows_path(self):
        src = "'E:\\repo\\analysis\\task.py'"
        self.assertEqual(normalize_user_path(src), r"E:\repo\analysis\task.py")

    def test_keep_plain_path(self):
        src = r"E:\repo\analysis\task.py"
        self.assertEqual(normalize_user_path(src), src)


if __name__ == "__main__":
    unittest.main()

