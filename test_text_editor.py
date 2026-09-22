import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from text_editor import replace_all


class ReplaceTests(unittest.TestCase):
    def test_literal_case_words_and_delete(self):
        self.assertEqual(replace_all("Ta ta tan", "ta", "X", whole_word=True), ("X X tan", 2))
        self.assertEqual(replace_all("Ta ta", "ta", "X", match_case=True), ("Ta X", 1))
        self.assertEqual(replace_all("a.b aab", "a.b", r"\1"), (r"\1 aab", 1))
        self.assertEqual(replace_all("xin xin", "xin", ""), (" ", 2))
        self.assertEqual(replace_all("abc", "", "x"), ("abc", 0))

    def test_size_limit(self):
        with patch("text_editor.MAX_TEXT_CHARS", 10), self.assertRaises(ValueError):
            replace_all("aaa", "a", "long")

    def test_editor_replace_undo_and_new_crawl(self):
        app = AppTest.from_file("app.py", default_timeout=20).run()
        result = dict(title="Test", text="Ta ta tan", raw_text="original raw", markdown="original md", clean_stats={}, source_mode="Fixture")
        app.text_input[0].set_value("https://example.com")
        with patch("job_runner.run_crawl", return_value=result):
            next(b for b in app.button if b.label == "Convert").click().run()
        app.text_input(key="find_query").set_value("ta")
        app.text_input(key="replace_value").set_value("X")
        app.checkbox(key="find_word").check().run()
        app.button(key="replace_all").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.text_area(key="edit_clean").value, "X X tan")
        self.assertEqual(app.text_area(key="edit_raw").value, "original raw")
        app.button(key="undo_replace").click().run()
        self.assertEqual(app.text_area(key="edit_clean").value, "Ta ta tan")
        app.selectbox(key="replace_target").select("Raw Text").run()
        app.text_input(key="find_query").set_value("original")
        app.text_input(key="replace_value").set_value("").run()
        app.button(key="replace_all").click().run()
        self.assertEqual(app.text_area(key="edit_raw").value, " raw")
        self.assertEqual(app.session_state["raw_text_result"], "original raw")
        app.session_state["last_crawl"] = 0
        with patch("job_runner.run_crawl", return_value=result):
            next(b for b in app.button if b.label == "Convert").click().run()
        self.assertEqual(app.text_area(key="edit_raw").value, "original raw")
        self.assertTrue(app.button(key="undo_replace").disabled)


if __name__ == "__main__":
    unittest.main()
