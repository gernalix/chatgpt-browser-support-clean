import io
import os
import unittest
from unittest.mock import MagicMock, patch

from chatgpt_rdc_supervisor import cli


class CliEndpointTests(unittest.TestCase):
    def test_doctor_uses_service_endpoint_environment(self):
        with patch.dict(os.environ, {'CHATGPT_RDC_ENDPOINT': 'channel-bridge'}), \
             patch.object(cli, 'ChatGPTBrowser') as browser_type, \
             patch('sys.stdout', new_callable=io.StringIO) as output:
            browser_type.return_value.browser.contexts = [MagicMock(pages=[])]
            self.assertEqual(cli.main(['doctor']), 0)
        browser_type.assert_called_once_with('channel-bridge')
        self.assertIn('"endpoint": "channel-bridge"', output.getvalue())


if __name__ == '__main__':
    unittest.main()
