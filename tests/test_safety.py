from pathlib import Path
import tempfile
import unittest

from chatgpt_rdc_supervisor.safety import LaunchDisabled, daemon_lock, reserve_launch


class SafetyTests(unittest.TestCase):
    def test_only_one_daemon_owns_process_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'state'
            kill = Path(tmp) / 'disable-chat-supervisor'
            with self.assertRaisesRegex(LaunchDisabled, 'retired_global'):
                with daemon_lock(state, kill):
                    pass
            self.assertFalse(state.exists())

    def test_chat_burst_trips_persistent_kill_switch_until_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'state'
            kill = Path(tmp) / 'config' / 'disable-chat-supervisor'
            for _ in range(3):
                reserve_launch(open_tabs=1, state_dir=state, kill_switch=kill, now=100)
            with self.assertRaisesRegex(LaunchDisabled, 'circuit_breaker'):
                reserve_launch(open_tabs=1, state_dir=state, kill_switch=kill, now=101)
            self.assertTrue(kill.exists())
            with self.assertRaisesRegex(LaunchDisabled, 'kill_switch'):
                reserve_launch(open_tabs=1, state_dir=state, kill_switch=kill, now=500)
            kill.unlink()
            reserve_launch(open_tabs=1, state_dir=state, kill_switch=kill, now=500)

    def test_open_tab_cap_disables_launcher_without_creating_chat(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'state'
            kill = Path(tmp) / 'config' / 'disable-chat-supervisor'
            with self.assertRaisesRegex(LaunchDisabled, 'circuit_breaker'):
                reserve_launch(open_tabs=20, state_dir=state, kill_switch=kill, now=1)
            self.assertTrue(kill.exists())


if __name__ == '__main__':
    unittest.main()
