import json
import tempfile
import unittest
from pathlib import Path

from rss_reader.readstate import ReadStore


class ReadStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "read.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_starts_empty_without_file(self):
        store = ReadStore(self.path)
        self.assertFalse(store.is_read("https://a.example/1"))
        self.assertIsNone(store.load_warning)
        self.assertFalse(self.path.exists())

    def test_save_and_reload(self):
        ReadStore(self.path).mark_read(["https://a.example/1", "https://a.example/2"])
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], 1)
        self.assertEqual(set(data["read"]), {"https://a.example/1", "https://a.example/2"})

        store = ReadStore(self.path)
        self.assertTrue(store.is_read("https://a.example/1"))
        self.assertFalse(store.is_read("https://a.example/3"))

    def test_mark_unread(self):
        ReadStore(self.path).mark_read(["https://a.example/1"])
        ReadStore(self.path).mark_unread("https://a.example/1")
        self.assertFalse(ReadStore(self.path).is_read("https://a.example/1"))

    def test_no_temp_files_left(self):
        ReadStore(self.path).mark_read(["https://a.example/1"])
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["read.json"])

    def test_broken_json_is_backed_up(self):
        self.path.write_text("{not json", encoding="utf-8")
        store = ReadStore(self.path)
        self.assertEqual(store.load_warning, "既読情報が壊れていたため初期化しました")
        self.assertFalse(store.is_read("x"))
        backup = self.path.with_name("read.json.bak")
        self.assertEqual(backup.read_text(encoding="utf-8"), "{not json")
        self.assertFalse(self.path.exists())

    def test_wrong_structure_is_backed_up(self):
        self.path.write_text('{"version": 1, "read": ["a"]}', encoding="utf-8")
        store = ReadStore(self.path)
        self.assertIsNotNone(store.load_warning)
        self.assertTrue(self.path.with_name("read.json.bak").exists())

    def _saved(self):
        return json.loads(self.path.read_text(encoding="utf-8"))["read"]

    def test_return_values(self):
        store = ReadStore(self.path)
        self.assertEqual(store.mark_read(["a", "b"]), ["a", "b"])
        self.assertEqual(store.mark_read(["a", "c"]), ["c"])
        self.assertTrue(store.mark_unread("a"))
        self.assertFalse(store.mark_unread("a"))

    def test_undo_mark_read(self):
        store = ReadStore(self.path)
        store.mark_read(["a"])
        self.assertEqual(store.undo(), ["a"])
        self.assertFalse(store.is_read("a"))
        self.assertNotIn("a", self._saved())

    def test_undo_mark_unread_restores_timestamp(self):
        # An old read time, distinguishable from the time of undo
        self.path.write_text(
            json.dumps({"version": 1, "read": {"a": "2000-01-01T00:00:00+00:00"}}), encoding="utf-8"
        )
        store = ReadStore(self.path)
        store.mark_unread("a")
        self.assertEqual(store.undo(), ["a"])
        self.assertTrue(store.is_read("a"))
        self.assertEqual(self._saved()["a"], "2000-01-01T00:00:00+00:00")

    def test_undo_multiple_links_at_once(self):
        store = ReadStore(self.path)
        store.mark_read(["a", "b", "c"])
        self.assertEqual(store.undo(), ["a", "b", "c"])
        self.assertFalse(any(store.is_read(x) for x in "abc"))

    def test_undo_goes_back_one_by_one(self):
        store = ReadStore(self.path)
        store.mark_read(["a"])
        store.mark_read(["b"])
        store.mark_unread("a")
        self.assertEqual(store.undo(), ["a"])
        self.assertTrue(store.is_read("a"))
        self.assertEqual(store.undo(), ["b"])
        self.assertFalse(store.is_read("b"))
        self.assertTrue(store.is_read("a"))
        self.assertEqual(store.undo(), ["a"])
        self.assertFalse(store.is_read("a"))
        self.assertIsNone(store.undo())

    def test_unchanged_operations_are_not_recorded(self):
        store = ReadStore(self.path)
        store.mark_read(["a"])
        store.mark_read(["a"])  # already read
        store.mark_read([])
        store.mark_unread("b")  # already unread
        self.assertEqual(store.undo(), ["a"])
        self.assertIsNone(store.undo())

    def test_undo_empty_history(self):
        self.assertIsNone(ReadStore(self.path).undo())

    def test_history_is_not_persisted(self):
        ReadStore(self.path).mark_read(["a"])
        store = ReadStore(self.path)
        self.assertIsNone(store.undo())
        self.assertTrue(store.is_read("a"))


if __name__ == "__main__":
    unittest.main()
