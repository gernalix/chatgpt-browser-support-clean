import asyncio
import json
from pathlib import Path
import runpy
import unittest


ChannelBridge = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / 'scripts/channel-bridge.py')
)['ChannelBridge']


class FakeClient:
    def __init__(self):
        self.messages = []

    async def send(self, message):
        self.messages.append(message)


class ChannelBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_responsive_existing_page_is_forwarded(self):
        bridge = ChannelBridge(None)
        bridge.client = FakeClient()
        commands = []

        async def send(payload, *, client=None):
            commands.append(payload['method'])
            return {'result': {'frameTree': {}}}

        bridge.send = send
        await bridge.screen_target({'method': 'Target.attachedToTarget', 'params': {
            'sessionId': 'tab-1', 'targetInfo': {'type': 'page'}}})
        self.assertEqual(commands, ['Page.getFrameTree'])
        self.assertEqual(len(bridge.client.messages), 1)
        self.assertIn('tab-1', bridge.forwarded_sessions)

    async def test_discarded_page_is_detached_without_forwarding(self):
        bridge = ChannelBridge(None)
        bridge.client = FakeClient()
        commands = []

        async def send(payload, *, client=None):
            commands.append(payload['method'])
            if payload['method'] == 'Page.getFrameTree':
                raise asyncio.TimeoutError()
            return {'result': {}}

        bridge.send = send
        await bridge.screen_target({'method': 'Target.attachedToTarget', 'params': {
            'sessionId': 'tab-2', 'targetInfo': {'type': 'page'}}})
        self.assertEqual(commands, ['Page.getFrameTree', 'Target.detachFromTarget'])
        self.assertEqual(bridge.client.messages, [])

    async def test_new_page_attachment_is_forwarded_before_create_result(self):
        bridge = ChannelBridge(None)
        bridge.client = FakeClient()

        async def send(payload, *, client=None):
            if payload['method'] == 'Target.createTarget':
                asyncio.create_task(bridge.screen_target({
                    'method': 'Target.attachedToTarget',
                    'params': {'sessionId': 'new-tab', 'targetInfo': {
                        'type': 'page', 'targetId': 'target-1'}},
                }))
                return {'result': {'targetId': 'target-1'}}
            return {'result': {'frameTree': {}}}

        bridge.send = send
        class Request:
            path = '/token'

        class Client(FakeClient):
            request = Request()

            def __aiter__(self):
                self.request_sent = False
                return self

            async def __anext__(self):
                if self.request_sent:
                    raise StopAsyncIteration
                self.request_sent = True
                return json.dumps({'id': 7, 'method': 'Target.createTarget', 'params': {'url': 'about:blank'}})

        client = Client()
        bridge.client = None
        await bridge.handle_client(client, 'token')
        messages = [json.loads(item) for item in client.messages]
        self.assertEqual(messages[0]['method'], 'Target.attachedToTarget')
        self.assertEqual(messages[1], {'id': 7, 'result': {'targetId': 'target-1'}})


if __name__ == '__main__':
    unittest.main()
