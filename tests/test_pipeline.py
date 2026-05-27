import unittest

from comms_analyst_agent.pipeline import build_target_slug


class BuildTargetSlugTests(unittest.TestCase):
    def test_removes_invalid_filesystem_characters(self) -> None:
        self.assertEqual(
            build_target_slug("<I would like for deep sentiment>"),
            "i-would-like-for-deep-sentiment",
        )

    def test_falls_back_when_only_invalid_characters(self) -> None:
        self.assertEqual(build_target_slug("<<>>"), "target")


if __name__ == "__main__":
    unittest.main()
