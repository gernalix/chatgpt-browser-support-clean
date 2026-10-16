import unittest
from chatgpt_rdc_supervisor.discovery import conversation_id_from_url, normalize_chat_url, merge_chat_inventory

class DiscoveryTests(unittest.TestCase):
    def test_targeted_url_normalization(self):
        url = "https://chatgpt.com/c/abc-123?messageId=x#frag"
        self.assertEqual("abc-123", conversation_id_from_url(url))
        self.assertEqual("https://chatgpt.com/c/abc-123", normalize_chat_url(url))
        self.assertIsNone(normalize_chat_url("https://chatgpt.com/c/WEB:abc"))
        self.assertIsNone(normalize_chat_url("https://example.com/c/abc"))

    def test_global_discovery_rejects(self):
        with self.assertRaisesRegex(RuntimeError, "retired_global"):
            merge_chat_inventory([], [], {}, 0)
