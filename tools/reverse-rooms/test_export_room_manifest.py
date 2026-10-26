"""Independent regression for Unity-authored Transform sibling order."""
import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("export_room_manifest.py")
SPEC = importlib.util.spec_from_file_location("export_room_manifest", MODULE_PATH)
EXPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORTER)


class TransformChildOrderTest(unittest.TestCase):
    def test_uses_serialized_children_not_transform_table_order(self):
        # Deliberately put children in path-ID/object-table order, opposite to
        # the authored sibling order retained by Unity in m_Children.
        transforms = {
            10: {"m_Father": {"m_PathID": 0}, "m_Children": [{"m_PathID": 30}, {"m_PathID": 20}]},
            20: {"m_Father": {"m_PathID": 10}, "m_Children": []},
            30: {"m_Father": {"m_PathID": 10}, "m_Children": []},
        }
        children = EXPORTER.build_transform_children(transforms)
        self.assertEqual(children[10], [30, 20])

    def test_rejects_inconsistent_father_and_child_links(self):
        transforms = {
            10: {"m_Father": {"m_PathID": 0}, "m_Children": [{"m_PathID": 20}]},
            20: {"m_Father": {"m_PathID": 99}, "m_Children": []},
        }
        with self.assertRaisesRegex(ValueError, "whose father"):
            EXPORTER.build_transform_children(transforms)


if __name__ == "__main__":
    unittest.main()
