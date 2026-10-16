import unittest
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from chatgpt_rdc_supervisor.browser import ChatGPTBrowser


class BrowserChannelTests(unittest.TestCase):
    @patch('chatgpt_rdc_supervisor.browser.sync_playwright')
    def test_attaches_to_normal_chrome_and_reconnects_after_disconnect(self, start):
        first = MagicMock()
        first.chromium.connect_over_cdp.return_value.is_connected.side_effect = [True, False]
        second = MagicMock()
        second.chromium.connect_over_cdp.return_value.is_connected.return_value = True
        start.return_value.start.side_effect = [first, second]

        browser = ChatGPTBrowser()
        browser.connect()
        browser.connect()
        self.assertEqual(start.return_value.start.call_count, 1)
        browser.connect()
        self.assertEqual(start.return_value.start.call_count, 2)
        first.chromium.connect_over_cdp.assert_called_once_with('chrome', no_defaults=True, timeout=30_000)
        first.stop.assert_called_once()
        second.chromium.connect_over_cdp.assert_called_once_with('chrome', no_defaults=True, timeout=30_000)
        browser.close()
        second.stop.assert_called_once()

    @patch('chatgpt_rdc_supervisor.browser.sync_playwright')
    def test_failed_attach_stops_playwright(self, start):
        playwright = start.return_value.start.return_value
        playwright.chromium.connect_over_cdp.side_effect = RuntimeError('attach refused')
        browser = ChatGPTBrowser()
        with self.assertRaisesRegex(RuntimeError, 'attach refused'):
            browser.connect()
        playwright.stop.assert_called_once()
        self.assertIsNone(browser.handle)

    @patch('chatgpt_rdc_supervisor.browser.sync_playwright')
    def test_channel_bridge_reads_local_endpoint(self, start):
        with TemporaryDirectory() as temp, patch.dict(os.environ, {'XDG_STATE_HOME': temp}):
            path = Path(temp) / 'chatgpt-rdc-supervisor/channel-endpoint.json'
            path.parent.mkdir()
            path.write_text(json.dumps({'endpoint': 'ws://127.0.0.1:1234/secret'}))
            browser = ChatGPTBrowser('channel-bridge')
            browser.connect()
            start.return_value.start.return_value.chromium.connect_over_cdp.assert_called_once_with(
                'ws://127.0.0.1:1234/secret', no_defaults=True, timeout=30_000
            )
            browser.close()

    def test_launch_cap_counts_only_supervisor_created_open_tabs(self):
        browser = ChatGPTBrowser('channel-bridge')
        open_page = MagicMock()
        open_page.is_closed.return_value = False
        closed_page = MagicMock()
        closed_page.is_closed.return_value = True
        browser.launched_pages = [open_page, closed_page]
        self.assertEqual(browser._owned_open_tabs(), 1)

    def test_discovery_does_not_wait_on_every_existing_tab(self):
        browser = ChatGPTBrowser('channel-bridge')
        discovery = MagicMock()
        discovery.url = 'https://chatgpt.com/'
        discovery.is_closed.return_value = False
        discovery.eval_on_selector_all.return_value = []
        existing = MagicMock()
        existing.eval_on_selector_all.return_value = ['https://chatgpt.com/c/existing']
        browser.discovery_page = discovery
        browser._open_pages = lambda: [
            (discovery, 'https://chatgpt.com/'),
            (existing, 'https://chatgpt.com/c/existing'),
        ]
        with self.assertRaisesRegex(RuntimeError,'retired'):
            browser.discover_chat_urls(refresh=False)
        discovery.locator.assert_not_called()
        existing.locator.assert_not_called()


if __name__ == '__main__':
    unittest.main()
