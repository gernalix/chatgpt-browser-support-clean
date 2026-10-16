from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]


class SystemdSafetyTests(unittest.TestCase):
    def test_global_daemon_unit_is_removed_and_installer_fails_closed(self):
        self.assertFalse((ROOT/'systemd/chatgpt-rdc-supervisor.service').exists())
        result=subprocess.run(['bash',str(ROOT/'scripts/install-user.sh')],capture_output=True,text=True)
        self.assertEqual(2,result.returncode)
        self.assertIn('Retired',result.stderr)

    def test_on_demand_bridge_does_not_launch_a_separate_chrome(self):
        self.assertFalse((ROOT/'systemd/chatgpt-rdc-browser.service').exists())
        script=(ROOT/'scripts/browser-health.sh').read_text()
        self.assertNotIn('systemctl --user restart',script)
