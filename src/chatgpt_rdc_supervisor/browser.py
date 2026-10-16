from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import time

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from .model import BrowserSnapshot, TaskConfig
from .safety import reserve_launch


COMPOSER_SELECTORS = (
    'form[data-chatgpt-composer] [contenteditable="true"][role="textbox"]',
    'form[data-chatgpt-composer] textarea',
    'form[data-composer-placement] [contenteditable="true"][role="textbox"]',
    '#prompt-textarea',
    'textarea[data-testid*="prompt"]',
    '[contenteditable="true"][data-lexical-editor="true"]',
)
COMPOSER_SELECTOR = ", ".join(COMPOSER_SELECTORS)
VISIBLE_COMPOSER_SELECTOR = ", ".join(f"{selector}:visible" for selector in COMPOSER_SELECTORS)


def is_persisted_chat_url(url: str) -> bool:
    return "/c/" in url and "/c/WEB:" not in url


@dataclass
class BrowserHandle:
    playwright: Playwright
    browser: Browser


class ChatGPTBrowser:
    def __init__(self, endpoint: str = "chrome") -> None:
        self.endpoint = endpoint
        self.handle: BrowserHandle | None = None
        self.discovery_page: Page | None = None
        self.launched_pages: list[Page] = []
        self._project_sweep_cursor = 0

    def _owned_open_tabs(self) -> int:
        count = 0
        for page in self.launched_pages:
            try:
                count += not page.is_closed()
            except Exception:
                pass
        return count

    def connect(self) -> None:
        if self.handle is not None:
            if self.handle.browser.is_connected():
                return
            self.close()
        pw = sync_playwright().start()
        try:
            endpoint = self.endpoint
            if endpoint == "channel-bridge":
                state_home = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
                endpoint_file = state_home / "chatgpt-rdc-supervisor/channel-endpoint.json"
                endpoint = json.loads(endpoint_file.read_text())["endpoint"]
            browser = pw.chromium.connect_over_cdp(endpoint, no_defaults=True, timeout=30_000)
        except Exception:
            pw.stop()
            raise
        self.handle = BrowserHandle(pw, browser)

    def close(self) -> None:
        if self.handle:
            self.handle.playwright.stop()
            self.handle = None
        self.discovery_page = None

    @property
    def browser(self) -> Browser:
        if not self.handle:
            self.connect()
        assert self.handle
        return self.handle.browser

    def find_page(self, task: TaskConfig) -> Page | None:
        candidates = self._open_pages()
        for page, url in candidates:
            if task.chat_url and url.rstrip("/") == task.chat_url.rstrip("/"):
                return page
        for page, url in candidates:
            if task.chat_url and "/c/" in task.chat_url and task.chat_url.split("/c/", 1)[-1] in url:
                return page
        return None

    def _open_pages(self) -> list[tuple[Page, str]]:
        pages: list[tuple[Page, str]] = []
        for context in self.browser.contexts:
            for page in context.pages:
                try:
                    if not page.is_closed():
                        pages.append((page, page.url))
                except Exception:
                    # CDP may close a target between listing and reading it.
                    continue
        return pages

    def _new_page_in_auth_context(self) -> Page:
        contexts = self.browser.contexts
        if not contexts:
            return self.browser.new_context().new_page()
        for context in contexts:
            try:
                return context.new_page()
            except Exception:
                # Another existing context may still hold the signed-in session.
                continue
        raise RuntimeError("cdp_context_closed: no existing context can open a page")

    def page_for(self, task: TaskConfig) -> Page:
        existing = self.find_page(task)
        if existing is not None:
            return existing
        page = self._new_page_in_auth_context()
        response = page.goto(task.chat_url or task.project_url or "https://chatgpt.com/", wait_until="domcontentloaded", timeout=45_000)
        if task.chat_url and response is not None and response.status == 404:
            raise RuntimeError("chat_url_not_found: authoritative chat URL returned 404")
        return page

    def discover_chat_urls(self, refresh: bool = True, sweep_projects: bool = False) -> list[str]:
        raise RuntimeError('retired: account-wide discovery is not a C3 executor operation')


    def inspect(self, page: Page) -> BrowserSnapshot:
        script = """() => {
              const text = (document.body?.innerText || '').toLowerCase();
              const turnNodes = [...document.querySelectorAll('[data-testid^="conversation-turn"]')];
              const turns = turnNodes.length ? turnNodes : [...document.querySelectorAll('article')];
              const visible = el => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
              const composer = [...document.querySelectorAll(__COMPOSER_SELECTOR__)].find(visible) || null;
              const buttons = [...document.querySelectorAll('button')].filter(visible);
              const btxt = buttons.map(b => (b.innerText || b.getAttribute('aria-label') || '').toLowerCase());
              const generating = !!document.querySelector('[data-testid="stop-button"]') || btxt.some(x => x.includes('stop generating'));
              const retry = btxt.some(x => x.includes('retry') || x.includes('try again') || x.includes('regenerate'));
              const alerts = [...document.querySelectorAll('[role="alert"], [role="status"], [role="dialog"], [data-testid*="error"], [data-testid*="toast"]')]
                .filter(visible)
                .map(el => (el.innerText || el.textContent || '').toLowerCase())
                .join(' ');
              const lastText = turns.length ? (turns[turns.length - 1].innerText || '').toLowerCase() : '';
              const errorSurface = (alerts + ' ' + (retry ? lastText : '')).trim();
              const slowMarker = 'our systems are thinking a bit more about this request';
              const slowRetryMarker = 'retry with a faster model';
              const userMessages = [...document.querySelectorAll('[data-message-author-role="user"]')];
              const lastUser = userMessages.length ? userMessages[userMessages.length - 1] : null;
              const slowCandidates = [...document.querySelectorAll('main p, main div, main span')]
                .filter(visible)
                .filter(el => {
                  const own = (el.innerText || el.textContent || '').toLowerCase();
                  if (!own.includes(slowMarker) || !own.includes(slowRetryMarker)) return false;
                  if (el.closest('[data-message-author-role="user"]')) return false;
                  if (lastUser && !(lastUser.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING)) return false;
                  return ![...el.children].some(child => {
                    const childText = (child.innerText || child.textContent || '').toLowerCase();
                    return visible(child) && childText.includes(slowMarker) && childText.includes(slowRetryMarker);
                  });
                });
              const slowEl = slowCandidates.length ? slowCandidates[slowCandidates.length - 1] : null;
              const slowThinking = !!slowEl;
              const slowTurn = slowEl?.closest('[data-testid^="conversation-turn"]')?.getAttribute('data-testid') || '';
              const slowBasis = slowThinking ? location.href + '|' + slowTurn + '|' + slowCandidates.length + '|' + (slowEl.innerText || slowEl.textContent || '') : '';
              let error = null;
              if (!composer && (text.includes('verify you are human') || text.includes('captcha'))) error = 'captcha';
              else if (!composer && (btxt.some(x => x === 'log in' || x === 'sign in') || text.includes('log in to chatgpt'))) error = 'login';
              else if (!composer && (text.includes('access denied') || text.includes('forbidden'))) error = 'access-denied';
              else if (errorSurface.includes('rate limit') || errorSurface.includes('reached your') || errorSurface.includes('too many requests')) error = 'rate-limit';
              else if (errorSurface.includes('message delivery timed out')) error = 'delivery-timeout';
              else if (errorSurface.includes('network error') || errorSurface.includes('connection error')) error = 'network';
              else if (errorSurface.includes('something went wrong') || errorSurface.includes('error generating')) error = 'server';
              const chars = turns.reduce((n, el) => n + (el.innerText || '').length, 0);
              const hashText = value => {
                let h = 2166136261;
                for (let i = 0; i < value.length; i++) {
                  h ^= value.charCodeAt(i);
                  h = Math.imul(h, 16777619);
                }
                return (h >>> 0).toString(16);
              };
              const last = turns.length ? (turns[turns.length - 1].innerText || '') : '';
              const basis = location.href + '|' + turns.length + '|' + chars + '|' + last.length + '|' + generating;
              return {
                url: location.href,
                title: document.title,
                authenticated: !!composer && !error?.match(/login|captcha|access-denied/),
                composer: !!composer,
                generating,
                retry_available: retry,
                error_kind: error,
                slow_thinking: slowThinking,
                slow_notice_signature: slowThinking ? hashText(slowBasis) : '',
                turn_count: turns.length,
                text_chars: chars,
                signature: hashText(basis)
              };
            }""".replace("__COMPOSER_SELECTOR__", repr(COMPOSER_SELECTOR))
        data = page.evaluate(script)
        if not data.get("composer") and not data.get("error_kind") and "chatgpt.com" in page.url:
            data["error_kind"] = "dom-unknown"
        return BrowserSnapshot(**data)

    def dismiss_rate_limit_dialog(self, page: Page) -> bool:
        dialogs = page.locator('[role="dialog"]')
        markers = ("too many requests", "making requests too quickly", "temporarily limited access")
        for i in range(dialogs.count()):
            dialog = dialogs.nth(i)
            if not dialog.is_visible():
                continue
            text = (dialog.inner_text() or "").lower()
            if not any(marker in text for marker in markers):
                continue
            buttons = dialog.locator("button")
            for j in range(buttons.count()):
                button = buttons.nth(j)
                if not button.is_visible():
                    continue
                label = ((button.inner_text() or "") or (button.get_attribute("aria-label") or "")).strip().lower()
                if label in {"got it", "ok", "okay", "close", "dismiss"}:
                    button.click()
                    return True
        return False

    def dismiss_rate_limit_dialogs(self) -> int:
        dismissed = 0
        for context in self.browser.contexts:
            for page in context.pages:
                try:
                    dismissed += int(self.dismiss_rate_limit_dialog(page))
                except Exception:
                    pass
        return dismissed

    def _composer(self, page: Page):
        return page.locator(VISIBLE_COMPOSER_SELECTOR).first

    def send_message(self, page: Page, message: str) -> None:
        composer = self._composer(page)
        composer.wait_for(state="visible", timeout=20_000)
        composer.click()
        try:
            composer.fill(message)
        except Exception:
            page.keyboard.press("Control+A")
            page.keyboard.insert_text(message)
        user_turns = page.locator('[data-message-author-role="user"]')
        before = user_turns.count()
        send = page.locator('[data-testid="send-button"]').first
        try:
            send.wait_for(state="visible", timeout=3_000)
            send.click()
        except Exception:
            # A timed-out click may already have delivered the message. Never
            # turn that ambiguity into a second send attempt.
            pass
        try:
            page.wait_for_function(
                """({before, expected}) => {
                  const turns = [...document.querySelectorAll('[data-message-author-role="user"]')];
                  const normalize = value => value.replace(/\\s+/g, ' ').trim();
                  return turns.length > before &&
                    normalize(turns[turns.length - 1].innerText || '') === normalize(expected);
                }""",
                arg={"before": before, "expected": message},
                timeout=10_000,
            )
        except Exception as exc:
            raise RuntimeError("message_delivery_unconfirmed: send once, inspect before retry") from exc

    def stop_generation(self, page: Page) -> bool:
        stop = page.locator('[data-testid="stop-button"], button[aria-label*="Stop generating" i], button[aria-label="Stop" i]').first
        if not stop.count() or not stop.is_visible():
            return False
        stop.click()
        try:
            page.wait_for_function(
                """() => !document.querySelector('[data-testid="stop-button"]')""",
                timeout=10_000,
            )
        except Exception:
            pass
        return True

    def retry(self, page: Page) -> bool:
        buttons = page.locator("button")
        for i in range(buttons.count()):
            b = buttons.nth(i)
            label = ((b.inner_text() if b.is_visible() else "") or b.get_attribute("aria-label") or "").lower()
            if any(x in label for x in ("retry", "try again", "regenerate")):
                b.click()
                return True
        return False

    def reload(self, page: Page) -> None:
        page.reload(wait_until="domcontentloaded", timeout=45_000)

    def probe_lane(self) -> bool:
        """One bounded disposable chat; only a real assistant response is healthy."""
        reserve_launch(open_tabs=self._owned_open_tabs())
        context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
        page = context.new_page()
        self.launched_pages.append(page)
        try:
            page.goto("https://chatgpt.com/", wait_until="domcontentloaded", timeout=15_000)
            initial = self.inspect(page)
            if not initial.authenticated or initial.error_kind:
                return False
            self.send_message(page, "Reply with OK.")
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                snapshot = self.inspect(page)
                if snapshot.error_kind:
                    return False
                if is_persisted_chat_url(page.url) and page.locator(
                    '[data-message-author-role="assistant"]'
                ).count() and not snapshot.generating:
                    return True
                time.sleep(1)
            return False
        except Exception:
            return False
        finally:
            try:
                page.close()
            except Exception:
                pass

    def new_chat(self, task: TaskConfig, message: str) -> tuple[Page, str, str | None]:
        reserve_launch(open_tabs=self._owned_open_tabs())
        context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
        page = context.new_page()
        self.launched_pages.append(page)
        page.goto(task.project_url or "https://chatgpt.com/", wait_until="domcontentloaded", timeout=45_000)
        if task.project_url and not (
            page.url.rstrip('/') == task.project_url.rstrip('/')
            or page.url.startswith(task.project_url.rstrip('/') + '/')
        ):
            page.close()
            raise RuntimeError('project_not_exact')
        self.send_message(page, message)
        deadline = time.time() + 75
        while time.time() < deadline:
            if is_persisted_chat_url(page.url):
                return page, page.url, None
            snapshot = self.inspect(page)
            if snapshot.error_kind == "rate-limit":
                self.dismiss_rate_limit_dialog(page)
                return page, page.url, "rate-limit"
            time.sleep(0.5)
        return page, page.url, None
