"""Regression for the malformed indentation in a generated Actions document."""
from pathlib import Path
import unittest
import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml"

class GeneratedWorkflowYamlTests(unittest.TestCase):
    def test_actual_generated_document_parses_with_expected_execution_structure(self):
        document = yaml.safe_load(WORKFLOW.read_text())
        self.assertIsInstance(document, dict)
        self.assertEqual(document["name"], "Offline checks")
        events = document.get("on", document.get(True))
        self.assertIsInstance(events, dict)
        self.assertIn("workflow_dispatch", events)
        self.assertIn("push", events)
        self.assertIn("expected_sha", events["workflow_dispatch"]["inputs"])
        steps = document["jobs"]["offline-tests"]["steps"]
        self.assertTrue(any(step.get("uses", "").startswith("actions/checkout@") for step in steps))
        self.assertTrue(any(step.get("name") == "Verify exact checkout" for step in steps))
        self.assertTrue(any(step.get("name") == "Run offline tests" for step in steps))

    def test_rejects_accidentally_indented_top_level_keys_after_first_line(self):
        malformed = "name: Offline checks\n run-name: regression\n on:\n   workflow_dispatch:\n"
        with self.assertRaises(yaml.YAMLError):
            yaml.safe_load(malformed)

if __name__ == "__main__":
    unittest.main()
