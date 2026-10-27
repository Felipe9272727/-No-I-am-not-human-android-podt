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


class ObjectViewStateDecodeTest(unittest.TestCase):
    def test_decodes_object_state_and_exact_start_state(self):
        # One serialized RoomObjectState<EObjectsRoomObject> record. This
        # independently exercises the raw layout used by the scene exporter.
        raw = bytearray(100)
        raw[56:60] = (1).to_bytes(4, "little", signed=True)
        raw[60:64] = (2).to_bytes(4, "little", signed=True)
        raw[64:68] = (2).to_bytes(4, "little", signed=True)  # sharedassets1
        raw[68:76] = (612).to_bytes(8, "little", signed=True)
        import struct
        struct.pack_into("<ff", raw, 76, 690.0, -65.0)
        struct.pack_into("<ff", raw, 84, 2.0, 2.0)
        raw[92] = 0  # CannotInteract
        raw[96:100] = (2).to_bytes(4, "little", signed=True)

        decoded = EXPORTER.decode_object_view_states(bytes(raw), "_Code.Rooms.ObjectRoomObjectView")
        self.assertEqual(decoded["start_state_name"], "Fridge")
        self.assertEqual(decoded["states"][0]["enum_name"], "Fridge")
        self.assertEqual(decoded["states"][0]["sprite_reference"], {"file_id": 2, "path_id": 612})
        self.assertEqual(decoded["states"][0]["position_shift"], [690.0, -65.0])
        self.assertEqual(decoded["states"][0]["scale_shift"], [2.0, 2.0])
        self.assertEqual(decoded["bytes_consumed"], len(raw))

    def test_rejects_object_view_trailing_bytes(self):
        raw = bytearray(101)
        raw[56:60] = (1).to_bytes(4, "little", signed=True)
        with self.assertRaisesRegex(ValueError, "schema consumed 100, raw size 101"):
            EXPORTER.decode_object_view_states(bytes(raw), "_Code.Rooms.ObjectRoomObjectView")


if __name__ == "__main__":
    unittest.main()
