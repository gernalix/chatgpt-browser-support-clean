import unittest
from types import SimpleNamespace

from chatgpt_rdc_supervisor.browser import ChatGPTBrowser
from chatgpt_rdc_supervisor.model import TaskConfig


CHAT_URL = "https://chatgpt.com/c/123"


class FakePage:
    def __init__(self, url="about:blank", closed=False, status=200):
        self.url = url
        self.closed = closed
        self.status = status

    def is_closed(self):
        return self.closed

    def goto(self, url, **_kwargs):
        self.url = url
        return SimpleNamespace(status=self.status)


class FakeContext:
    def __init__(self, pages=(), closed=False):
        self.pages = list(pages)
        self.closed = closed
        self.created = []

    def new_page(self):
        if self.closed:
            raise RuntimeError("Target page, context or browser has been closed")
        page = FakePage()
        self.created.append(page)
        return page


def browser_with(contexts):
    browser = ChatGPTBrowser()
    browser.handle = SimpleNamespace(browser=SimpleNamespace(contexts=contexts))
    return browser


def task():
    return TaskConfig(task_id="fixture", state_file="/tmp/fixture", repo_root="/tmp", chat_url=CHAT_URL)


class BrowserPageRecoveryTests(unittest.TestCase):
    def test_closed_match_is_not_reused_and_second_context_recovers(self):
        closed = FakePage(CHAT_URL, closed=True)
        first = FakeContext([closed], closed=True)
        second = FakeContext()
        page = browser_with([first, second]).page_for(task())
        self.assertIs(page, second.created[0])
        self.assertEqual(CHAT_URL, page.url)

    def test_all_closed_contexts_fail_without_unauthenticated_new_context(self):
        browser = browser_with([FakeContext(closed=True)])
        with self.assertRaisesRegex(RuntimeError, "cdp_context_closed"):
            browser.page_for(task())

    def test_authoritative_chat_404_is_observable(self):
        context = FakeContext()
        browser = browser_with([context])
        original_new_page = context.new_page

        def new_page_404():
            page = original_new_page()
            page.status = 404
            return page

        context.new_page = new_page_404
        with self.assertRaisesRegex(RuntimeError, "chat_url_not_found"):
            browser.page_for(task())


if __name__ == "__main__":
    unittest.main()
