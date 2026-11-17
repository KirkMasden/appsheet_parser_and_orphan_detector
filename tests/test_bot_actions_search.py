"""Where the action orphan detector looks for bot_actions.txt: the input
folder first (the documented place, beside Application Documentation.html),
then the older locations as fallbacks.

Run from the repository root:
    python -m unittest discover -s tests -t .
"""

import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

import master_parser_and_orphan_detector as master
from actions_orphan_detector import ActionOrphanDetector


def _write(path, names):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n" + "\n".join(names) + "\n")  # a leading blank line, as the real file has


def _detector(parse_dir, input_dir=None):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        detector = ActionOrphanDetector(parse_dir, input_dir) if input_dir is not None else ActionOrphanDetector(parse_dir)
    return detector, out.getvalue()


class TestBotActionsSearch(unittest.TestCase):
    def test_found_in_the_input_folder_in_the_documented_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = os.path.join(tmp, "apps", "MyApp_1")
            parse_dir = os.path.join(tmp, "output", "MyApp_1", "app")
            os.makedirs(parse_dir)
            _write(os.path.join(input_dir, "bot_actions.txt"), ["Number Scheduled", "Switch It"])
            detector, printed = _detector(parse_dir, input_dir)
        self.assertEqual(detector.bot_actions, {"number scheduled", "switch it"})
        self.assertIn("Loaded 2 bot-used actions", printed)
        self.assertIn(os.path.join(input_dir, "bot_actions.txt"), printed)  # the full path, not just the name

    def test_the_input_folder_wins_over_a_file_in_the_output_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = os.path.join(tmp, "apps", "MyApp_1")
            parse_dir = os.path.join(tmp, "output", "MyApp_1", "app")
            os.makedirs(parse_dir)
            _write(os.path.join(input_dir, "bot_actions.txt"), ["From Input"])
            _write(os.path.join(parse_dir, "bot_actions.txt"), ["From Output", "Another"])
            _write(os.path.join(os.path.dirname(parse_dir), "bot_actions.txt"), ["From Parent"])
            detector, printed = _detector(parse_dir, input_dir)
        self.assertEqual(detector.bot_actions, {"from input"})
        self.assertIn(os.path.join(input_dir, "bot_actions.txt"), printed)

    def test_the_older_locations_still_work_when_the_input_folder_has_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = os.path.join(tmp, "apps", "MyApp_1")
            os.makedirs(input_dir)
            parse_dir = os.path.join(tmp, "output", "MyApp_1", "app")
            os.makedirs(parse_dir)
            # 1. the parse output folder
            _write(os.path.join(parse_dir, "bot_actions.txt"), ["In Output"])
            detector, printed = _detector(parse_dir, input_dir)
            self.assertEqual(detector.bot_actions, {"in output"})
            self.assertIn(os.path.join(parse_dir, "bot_actions.txt"), printed)
            os.remove(os.path.join(parse_dir, "bot_actions.txt"))
            # 2. its parent folder
            _write(os.path.join(os.path.dirname(parse_dir), "bot_actions.txt"), ["In Parent"])
            detector, _ = _detector(parse_dir, input_dir)
            self.assertEqual(detector.bot_actions, {"in parent"})

    def test_the_timestamped_parse_folder_fallback_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            parse_dir = os.path.join(tmp, "20260907_111603_My_App_parse")
            os.makedirs(parse_dir)
            _write(os.path.join(tmp, "My App", "bot_actions.txt"), ["From Source Folder"])
            detector, _ = _detector(parse_dir)
        self.assertEqual(detector.bot_actions, {"from source folder"})

    def test_run_on_its_own_without_an_input_folder_uses_the_fallbacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            parse_dir = os.path.join(tmp, "app")
            os.makedirs(parse_dir)
            _write(os.path.join(parse_dir, "bot_actions.txt"), ["Alone"])
            detector, _ = _detector(parse_dir)
        self.assertEqual(detector.bot_actions, {"alone"})

    def test_no_file_anywhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = os.path.join(tmp, "apps", "MyApp_1")
            parse_dir = os.path.join(tmp, "output", "MyApp_1", "app")
            os.makedirs(input_dir)
            os.makedirs(parse_dir)
            detector, printed = _detector(parse_dir, input_dir)
        self.assertEqual(detector.bot_actions, set())
        self.assertIn("No bot_actions.txt file found", printed)

    def test_the_master_script_passes_the_folder_of_the_html_export(self):
        with mock.patch.object(master, "ActionOrphanDetector") as detector_class:
            with contextlib.redirect_stdout(io.StringIO()):
                master.run_action_orphan_detector("/some/output", "/some/input")
        detector_class.assert_called_once_with("/some/output", "/some/input")
        detector_class.return_value.run_analysis.assert_called_once()

    def test_the_master_script_still_works_without_an_input_folder(self):
        with mock.patch.object(master, "ActionOrphanDetector") as detector_class:
            with contextlib.redirect_stdout(io.StringIO()):
                master.run_action_orphan_detector("/some/output")
        detector_class.assert_called_once_with("/some/output", None)


if __name__ == "__main__":
    unittest.main()
