from __future__ import annotations

import unittest

from chatgpt_rdc_supervisor.browser import is_persisted_chat_url


class BrowserUrlTests(unittest.TestCase):
    def test_rejects_provisional_web_id(self):
        self.assertFalse(is_persisted_chat_url("https://chatgpt.com/c/WEB:11111111-1111-4111-8111-111111111111"))
        self.assertFalse(is_persisted_chat_url("https://chatgpt.com/g/project/c/WEB:11111111-1111-4111-8111-111111111111"))

    def test_accepts_persisted_conversation_id(self):
        self.assertTrue(is_persisted_chat_url("https://chatgpt.com/c/22222222-2222-4222-8222-222222222222"))
        self.assertTrue(is_persisted_chat_url("https://chatgpt.com/g/project/c/22222222-2222-4222-8222-222222222222"))


if __name__ == "__main__":
    unittest.main()
