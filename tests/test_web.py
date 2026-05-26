from __future__ import annotations

import base64
import unittest

from comms_analyst_agent.web import _is_authorized


class WebAuthTests(unittest.TestCase):
    def test_authorized_basic_header(self) -> None:
        token = base64.b64encode(b"team:secret").decode("ascii")
        self.assertTrue(_is_authorized(f"Basic {token}", "team", "secret"))

    def test_rejects_wrong_password(self) -> None:
        token = base64.b64encode(b"team:nope").decode("ascii")
        self.assertFalse(_is_authorized(f"Basic {token}", "team", "secret"))

    def test_rejects_invalid_header(self) -> None:
        self.assertFalse(_is_authorized("Basic not-base64%%", "team", "secret"))


if __name__ == "__main__":
    unittest.main()
