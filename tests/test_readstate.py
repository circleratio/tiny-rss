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


if __name__ == "__main__":
    unittest.main()
