from __future__ import annotations

import unittest

from autoprofiler.cli import build_parser


class CliParsingTest(unittest.TestCase):
    def test_run_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--duration",
                "5",
                "--sample-interval",
                "250",
                "--include-children",
                "--output",
                "outdir",
                "--collect",
                "psutil,perf",
                "--cwd",
                "/tmp",
                "--env",
                "FOO=bar",
                "--",
                "python",
                "-V",
            ]
        )
        self.assertEqual(args.command, "run")
        self.assertEqual(args.duration, 5.0)
        self.assertEqual(args.sample_interval, 250.0)
        self.assertTrue(args.include_children)
        self.assertEqual(args.output, "outdir")
        self.assertEqual(args.collect, "psutil,perf")
        self.assertEqual(args.cwd, "/tmp")
        self.assertEqual(args.env, ["FOO=bar"])
        self.assertEqual(args.cmd, ["--", "python", "-V"])

    def test_attach_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "attach",
                "--pid",
                "123",
                "--name",
                "myproc",
                "--duration",
                "12",
                "--collect",
                "psutil",
            ]
        )
        self.assertEqual(args.command, "attach")
        self.assertEqual(args.pid, [123])
        self.assertEqual(args.name, "myproc")
        self.assertEqual(args.duration, 12.0)
        self.assertEqual(args.collect, "psutil")


if __name__ == "__main__":
    unittest.main()
