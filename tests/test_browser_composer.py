import unittest

from chatgpt_rdc_supervisor.browser import ChatGPTBrowser, VISIBLE_COMPOSER_SELECTOR


CURRENT_COMPOSER = (
    '<form data-composer-placement="thread" data-chatgpt-composer="">'
    '<div class="ProseMirror" contenteditable="true" role="textbox" aria-label="Ask ChatGPT"></div>'
    '</form>'
)


class FakeLocator:
    def __init__(self, *, found: bool = True, on_click=None):
        self.found = found
        self.first = self
        self.filled = None
        self.clicked = False
        self.clicks = 0
        self.on_click = on_click

    def wait_for(self, **_kwargs):
        if not self.found:
            raise TimeoutError("composer-not-found")

    def click(self):
        if not self.found:
            raise TimeoutError("composer-not-found")
        self.clicked = True
        self.clicks += 1
        if self.on_click:
            self.on_click()

    def fill(self, message):
        if not self.found:
            raise TimeoutError("composer-not-found")
        self.filled = message


class CurrentComposerPage:
    def __init__(self, *, delivery=True, click_error=False):
        self.composer = FakeLocator(found=False)
        self.delivered = False
        self.delivery = delivery
        self.click_error = click_error
        self.send = FakeLocator(on_click=self._send)
        self.user_turns = self
        self.keyboard = None
        self.requested_selectors = []

    def _send(self):
        self.delivered = self.delivery
        if self.click_error:
            raise TimeoutError("click-ack-lost")

    def count(self):
        return 0

    def wait_for_function(self, script, *, arg, timeout):
        assert "data-message-author-role" in script
        assert arg["before"] == 0
        assert arg["expected"] == self.composer.filled
        assert timeout == 10_000
        if not self.delivered:
            raise TimeoutError("no-user-turn")

    def locator(self, selector):
        self.requested_selectors.append(selector)
        if selector == '[data-testid="send-button"]':
            return self.send
        if selector == '[data-message-author-role="user"]':
            return self.user_turns
        current_markup_matches = (
            'data-chatgpt-composer' in selector
            and '[contenteditable="true"][role="textbox"]' in selector
        )
        self.composer.found = current_markup_matches
        return self.composer


class BrowserComposerTests(unittest.TestCase):
    def test_current_composer_markup_no_longer_fails_delivery(self):
        self.assertNotIn('id="prompt-textarea"', CURRENT_COMPOSER)
        self.assertNotIn('data-lexical-editor', CURRENT_COMPOSER)
        page = CurrentComposerPage()

        ChatGPTBrowser().send_message(page, "TASK_ID=wi:fixture\nDo the work")

        self.assertEqual(VISIBLE_COMPOSER_SELECTOR, page.requested_selectors[0])
        self.assertTrue(page.composer.clicked)
        self.assertEqual("TASK_ID=wi:fixture\nDo the work", page.composer.filled)
        self.assertTrue(page.send.clicked)

    def test_click_ack_error_does_not_send_enter_again(self):
        page = CurrentComposerPage(click_error=True)
        ChatGPTBrowser().send_message(page, "one attempt")
        self.assertEqual(1, page.send.clicks)
        self.assertIsNone(page.keyboard)

    def test_unconfirmed_click_fails_closed(self):
        page = CurrentComposerPage(delivery=False, click_error=True)
        with self.assertRaisesRegex(RuntimeError, "message_delivery_unconfirmed"):
            ChatGPTBrowser().send_message(page, "one attempt")
        self.assertEqual(1, page.send.clicks)
        self.assertIsNone(page.keyboard)

    def test_unrecognized_markup_still_fails_closed_before_send(self):
        page = CurrentComposerPage()
        page.locator = lambda selector: (
            page.send if selector == '[data-testid="send-button"]' else FakeLocator(found=False)
        )

        with self.assertRaisesRegex(TimeoutError, "composer-not-found"):
            ChatGPTBrowser().send_message(page, "must not be sent")

        self.assertFalse(page.send.clicked)


if __name__ == "__main__":
    unittest.main()
