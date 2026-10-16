import unittest
from unittest.mock import patch
from chatgpt_rdc_supervisor.checkpoint import inspect_checkpoint,active_lane_allows


class HistoricalCheckpointTests(unittest.TestCase):
    def test_history_never_authorizes_recovery_without_any_io(self):
        with patch('subprocess.run') as process, patch('sqlite3.connect') as database:
            for path in ('/historical/m1.md','c2-db:/historical/roadmap.sqlite3#wi:old','/historical/task.md'):
                result=inspect_checkpoint('/historical',path)
                self.assertTrue(result.terminal)
                self.assertIsNone(result.next_action)
                self.assertFalse(result.pushed)
                self.assertFalse(active_lane_allows(path)[0])
            process.assert_not_called()
            database.assert_not_called()
