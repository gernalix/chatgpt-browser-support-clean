import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from chatgpt_rdc_supervisor import cli, checkpoint
from chatgpt_rdc_supervisor.supervisor import Supervisor


class RetirementTests(unittest.TestCase):
    def test_global_commands_fail_before_storage_or_browser(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            canonical = home / '.local/state/c3-control/roadmap.sqlite'
            canonical.parent.mkdir(parents=True)
            canonical.touch()
            with patch('pathlib.Path.home', return_value=home), patch.object(cli, 'ChatGPTBrowser', side_effect=AssertionError('browser must remain untouched')):
                for args in (['daemon'], ['discover'], ['run-once'], ['resume', 'm1']):
                    self.assertEqual(cli.main(args), 2)
            canonical.unlink()
            with patch('pathlib.Path.home',return_value=home), patch.object(cli,'ChatGPTBrowser',side_effect=AssertionError('no browser')):
                self.assertEqual(2,cli.main(['daemon']))
                self.assertEqual(2,cli.main(['register','--task-id','old']))
                with self.assertRaisesRegex(RuntimeError,'retired'):
                    Supervisor()

    def test_m1_and_old_snapshot_are_historical_not_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            canonical = home / '.local/state/c3-control/roadmap.sqlite'
            canonical.parent.mkdir(parents=True)
            canonical.touch()
            with patch('pathlib.Path.home', return_value=home), patch.object(checkpoint, '_run', side_effect=AssertionError('no Git or recovery discovery')):
                for state_file in ('/historical/m1.md', 'c2-db:/historical/roadmap.sqlite3#wi:old'):
                    result = checkpoint.inspect_checkpoint('/historical', state_file)
                    self.assertTrue(result.terminal)
                    self.assertIsNone(result.next_action)
