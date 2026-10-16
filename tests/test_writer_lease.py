from pathlib import Path
import tempfile
import unittest
from chatgpt_rdc_supervisor.storage import Store, WriterLeaseConflict

class RetiredOwnershipTests(unittest.TestCase):
    def test_all_legacy_state_entrypoints_reject_without_io(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "absent"
            store = Store(root)
            for name in ("claim_writer", "verify_writer", "release_writer", "writer_leases",
                         "tasks", "save_runtime", "load_runtime", "chats", "save_chats",
                         "global_state", "set_lane_state", "pending_ccs_replacements",
                         "enqueue_ccs_replacement", "remove_ccs_replacement", "event"):
                with self.subTest(name=name), self.assertRaisesRegex(WriterLeaseConflict, "retired"):
                    getattr(store, name)()
            self.assertFalse(root.exists())
