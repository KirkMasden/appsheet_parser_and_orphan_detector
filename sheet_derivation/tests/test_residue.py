import unittest

from ..artifact import ArtifactBase
from ..residue import ArtifactStamp, ResidueEntry, build_stamp, get_tool_commit


class TestResidueEntry(unittest.TestCase):
    def test_valid_entry_constructs_and_sorts_locations(self):
        entry = ResidueEntry(
            what="INDIRECT argument not resolved",
            locations=("C10", "A1", "B5"),
            defeating_construct="INDIRECT(...) with a computed string argument",
            consequence="the dependency graph may be missing an edge from this cell",
        )
        self.assertEqual(entry.locations, ("A1", "B5", "C10"))  # sorted, explicit key

    def test_rejects_bare_could_not_parse(self):
        with self.assertRaises(ValueError):
            ResidueEntry(what="", locations=("A1",), defeating_construct="x", consequence="y")
        with self.assertRaises(ValueError):
            ResidueEntry(what="could not parse", locations=(), defeating_construct="x", consequence="y")
        with self.assertRaises(ValueError):
            ResidueEntry(what="x", locations=("A1",), defeating_construct="", consequence="y")
        with self.assertRaises(ValueError):
            ResidueEntry(what="x", locations=("A1",), defeating_construct="y", consequence="")


class TestArtifactStamp(unittest.TestCase):
    def test_requires_both_fields(self):
        with self.assertRaises(ValueError):
            ArtifactStamp(capture_date="", tool_commit="abc123")
        with self.assertRaises(ValueError):
            ArtifactStamp(capture_date="2099-01-01T00:00:00.000Z", tool_commit="")

    def test_get_tool_commit_never_raises_and_never_empty(self):
        commit = get_tool_commit()
        self.assertTrue(commit)

    def test_build_stamp(self):
        stamp = build_stamp("2099-01-01T00:00:00.000Z")
        self.assertEqual(stamp.capture_date, "2099-01-01T00:00:00.000Z")
        self.assertTrue(stamp.tool_commit)


class TestArtifactBase(unittest.TestCase):
    def test_cannot_construct_without_reliability_condition(self):
        stamp = build_stamp("2099-01-01T00:00:00.000Z")
        with self.assertRaises(ValueError):
            ArtifactBase(stamp=stamp, reliability_condition="", residue=())

    def test_constructs_with_all_required_fields(self):
        stamp = build_stamp("2099-01-01T00:00:00.000Z")
        entry = ResidueEntry(
            what="x", locations=("A1",), defeating_construct="y", consequence="z"
        )
        artifact = ArtifactBase(
            stamp=stamp,
            reliability_condition="valid as long as no residue entry below applies",
            residue=[entry],
        )
        self.assertEqual(artifact.residue, (entry,))  # coerced to tuple


if __name__ == "__main__":
    unittest.main()
