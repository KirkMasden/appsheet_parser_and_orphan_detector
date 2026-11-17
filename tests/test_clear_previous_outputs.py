"""A run first deletes the files its mode writes from the output folder (and
nothing else), so a file from an earlier run on the same input folder cannot
survive as stale when the detectors find nothing and write nothing.

Run from the repository root:
    python -m unittest discover -s tests -t .
"""

import contextlib
import io
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import master_parser_and_orphan_detector as master

_REPO = Path(master.__file__).resolve().parent

ORPHAN_FILES = (
    'potential_action_orphans.csv', 'potential_slice_orphans.csv', 'potential_view_orphans.csv',
    'unused_system_views.csv', 'potential_virtual_column_orphans.csv',
)


def _touch(path, text="stale"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _run_main(argv, **patches):
    """Runs master.main() with the given argv, the parsers and detectors it
    would call replaced by mocks; returns (exit code, printed text, mocks)."""
    out = io.StringIO()
    names = ('run_all_parsers', 'run_action_orphan_detector', 'run_view_orphan_detector',
             'run_slice_parser', 'run_column_orphan_detector')
    with contextlib.ExitStack() as stack:
        mocks = {n: stack.enter_context(mock.patch.object(master, n, return_value=None)) for n in names}
        stack.enter_context(mock.patch.object(sys, 'argv', ['master'] + argv))
        stack.enter_context(mock.patch('builtins.input', return_value='n'))  # the closing "explore dependencies?" prompt
        stack.enter_context(contextlib.redirect_stdout(out))
        code = 0
        try:
            master.main()
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), mocks


class TestClearPreviousOutputs(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name
        self.html = os.path.join(self.tmp, "in", "Application Documentation.html")
        _touch(self.html, "<html></html>")
        self.out = os.path.join(self.tmp, "out", "app")
        os.makedirs(self.out)

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_full_run_removes_stale_files_and_does_not_rewrite_them_when_nothing_is_found(self):
        for name in master.MODE_OUTPUT_FILES['full']:
            _touch(os.path.join(self.out, name))
        code, printed, mocks = _run_main([self.html, '-o', self.out, '--output-as-is'])
        self.assertEqual(code, 0)
        self.assertEqual(os.listdir(self.out), [])  # nothing was written by the (mocked) run
        for name in master.MODE_OUTPUT_FILES['full']:
            self.assertIn(f"Deleted the previous run's {name}", printed)
        self.assertEqual(printed.count("Deleted the previous run's"), len(master.MODE_OUTPUT_FILES['full']))
        mocks['run_all_parsers'].assert_called_once()

    def test_the_files_are_cleared_before_any_parser_runs(self):
        _touch(os.path.join(self.out, 'potential_action_orphans.csv'))
        seen = []
        def fake_parse(*a, **k):
            seen.append(sorted(os.listdir(self.out)))
        with mock.patch.object(master, 'run_all_parsers', side_effect=fake_parse), \
                mock.patch.object(sys, 'argv', ['master', self.html, '-o', self.out, '--output-as-is']), \
                mock.patch('builtins.input', return_value='n'), \
                contextlib.redirect_stdout(io.StringIO()):
            master.main()
        self.assertEqual(seen, [[]])

    def test_a_file_that_is_not_on_the_list_survives(self):
        keep = [
            os.path.join(self.out, 'bot_actions.txt'),
            os.path.join(self.out, 'notes.md'),
            os.path.join(self.out, 'appsheet_columns.csv.bak'),
            os.path.join(self.out, 'investigations', 'report.md'),
            os.path.join(self.out, 'investigations', 'potential_action_orphans.csv'),
            os.path.join(self.out, 'gates', 'appsheet_actions.csv'),
            os.path.join(self.out, 'subfolder', 'potential_slice_orphans.csv'),
        ]
        for path in keep:
            _touch(path)
        _touch(os.path.join(self.out, 'potential_slice_orphans.csv'))
        code, printed, _ = _run_main([self.html, '-o', self.out, '--output-as-is'])
        self.assertEqual(code, 0)
        for path in keep:
            self.assertTrue(os.path.isfile(path), msg=path)
        self.assertFalse(os.path.exists(os.path.join(self.out, 'potential_slice_orphans.csv')))
        self.assertEqual(printed.count("Deleted the previous run's"), 1)

    def test_a_directory_with_a_listed_name_is_not_touched(self):
        os.makedirs(os.path.join(self.out, 'potential_action_orphans.csv'))
        _touch(os.path.join(self.out, 'potential_action_orphans.csv', 'inner.txt'))
        deleted = master.clear_previous_outputs(self.out, 'full')
        self.assertEqual(deleted, [])
        self.assertTrue(os.path.isfile(os.path.join(self.out, 'potential_action_orphans.csv', 'inner.txt')))

    def test_a_partial_mode_clears_only_its_own_files(self):
        for name in ORPHAN_FILES + ('appsheet_actions.csv', 'navigation_edges.csv'):
            _touch(os.path.join(self.out, name))
        code, printed, mocks = _run_main([self.html, '-o', self.out, '-ao'])
        self.assertEqual(code, 0)
        self.assertEqual(
            sorted(os.listdir(self.out)),
            sorted(set(ORPHAN_FILES + ('appsheet_actions.csv', 'navigation_edges.csv')) - {'potential_action_orphans.csv'}),
        )
        self.assertEqual(printed.count("Deleted the previous run's"), 1)
        mocks['run_action_orphan_detector'].assert_called_once()
        mocks['run_all_parsers'].assert_not_called()

    def test_each_partial_mode_clears_exactly_its_list(self):
        flags = {
            '-s': 'slices', '-c': 'columns', '-f': 'format_rules', '-a': 'actions', '-v': 'views', '-t': 'targets',
            '-co': 'column_orphans', '-vo': 'view_orphans', '-fo': 'format_rule_orphans', '-so': 'slice_orphans',
            '-ao': 'action_orphans',
        }
        parser_functions = ('run_slice_parser', 'run_column_parser', 'run_format_rules_parser', 'run_actions_parser',
                            'run_views_parser', 'run_action_target_parser', 'run_column_orphan_detector',
                            'run_view_orphan_detector', 'run_format_rule_orphan_detector',
                            'run_slice_orphan_detector', 'run_action_orphan_detector')
        for flag, mode in flags.items():
            with self.subTest(flag=flag):
                every = set(master.MODE_OUTPUT_FILES['full'])
                for name in every:
                    _touch(os.path.join(self.out, name))
                with contextlib.ExitStack() as stack:
                    for fn in parser_functions:
                        stack.enter_context(mock.patch.object(master, fn, return_value=None))
                    stack.enter_context(mock.patch.object(sys, 'argv', ['master', self.html, '-o', self.out, '--output-as-is', flag]))
                    stack.enter_context(mock.patch('builtins.input', return_value='n'))
                    stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                    try:
                        master.main()
                    except SystemExit:
                        pass
                left = set(os.listdir(self.out))
                self.assertEqual(left, every - set(master.MODE_OUTPUT_FILES[mode]))
                for name in left:
                    os.remove(os.path.join(self.out, name))

    def test_an_empty_or_missing_output_folder_is_handled(self):
        self.assertEqual(master.clear_previous_outputs(self.out, 'full'), [])
        self.assertEqual(master.clear_previous_outputs(os.path.join(self.tmp, 'does-not-exist'), 'full'), [])
        code, printed, mocks = _run_main([self.html, '-o', self.out, '--output-as-is'])
        self.assertEqual(code, 0)
        self.assertNotIn("Deleted the previous run's", printed)
        mocks['run_all_parsers'].assert_called_once()

    def test_if_a_deletion_fails_the_run_stops_before_parsing(self):
        _touch(os.path.join(self.out, 'potential_action_orphans.csv'))
        with mock.patch.object(master.os, 'remove', side_effect=PermissionError("denied")):
            code, printed, mocks = _run_main([self.html, '-o', self.out, '--output-as-is'])
        self.assertEqual(code, 1)
        self.assertIn("could not delete", printed)
        self.assertIn("potential_action_orphans.csv", printed)
        self.assertIn("Stopping rather than parsing", printed)
        mocks['run_all_parsers'].assert_not_called()
        self.assertTrue(os.path.isfile(os.path.join(self.out, 'potential_action_orphans.csv')))


class TestTheListIsComplete(unittest.TestCase):
    def test_the_modes_precedence_matches_mains(self):
        ns = type('Args', (), {})()
        for flag in ('column_orphans', 'action_orphans', 'view_orphans', 'format_rule_orphans', 'slice_orphans',
                     'phantom_views', 'slice_only', 'column_only', 'format_rules_only', 'actions_only',
                     'views_only', 'targets_only'):
            setattr(ns, flag, False)
        self.assertEqual(master.run_mode(ns), 'full')
        ns.targets_only = True
        self.assertEqual(master.run_mode(ns), 'targets')
        ns.slice_only = True
        self.assertEqual(master.run_mode(ns), 'slices')
        ns.action_orphans = True
        self.assertEqual(master.run_mode(ns), 'action_orphans')
        ns.column_orphans = True
        self.assertEqual(master.run_mode(ns), 'column_orphans')

    def test_every_mode_is_part_of_the_full_run_and_nothing_is_listed_twice(self):
        full = master.MODE_OUTPUT_FILES['full']
        self.assertEqual(len(full), len(set(full)))
        for mode, names in master.MODE_OUTPUT_FILES.items():
            self.assertTrue(set(names) <= set(full), msg=mode)

    def test_every_output_file_name_the_code_mentions_is_on_the_list(self):
        """Any csv name the parsers and detectors mention that looks like one of their outputs must be listed,
        so a new output file cannot be added to the code and forgotten here."""
        pattern = re.compile(r"""['"]((?:potential_|unused_|broken_|action_targets|navigation_edges|appsheet_)[a-z_]*\.csv)['"]""")
        mentioned = set()
        for path in _REPO.glob('*.py'):
            if path.name in ('master_parser_and_orphan_detector.py',) or path.name.endswith('_analyzer.py') \
                    or path.name == 'dependency_analyzer_hub.py':
                continue
            mentioned.update(pattern.findall(path.read_text(encoding='utf-8')))
        listed = set(master.MODE_OUTPUT_FILES['full'])
        self.assertEqual(sorted(mentioned - listed), [])


if __name__ == "__main__":
    unittest.main()
