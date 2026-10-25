"""The retired uncontained route must remain unavailable."""
import unittest
from template_ai.review_tool.illustrator_bridge import available,IllustratorBridge,BridgeError
class RetiredBridgeTests(unittest.TestCase):
    def test_uncontained_route_is_disabled(self):
        self.assertFalse(available())
        with self.assertRaises(BridgeError):IllustratorBridge(None)
