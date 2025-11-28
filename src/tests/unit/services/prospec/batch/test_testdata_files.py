"""Unit tests for BatchProblemSpec testdata file methods."""
import unittest

from services.prospec.batch import BatchProblemSpec
from services.prospec.batch import BatchTestdata


class TestBatchProblemSpecTestdataFiles(unittest.TestCase):
    """Test BatchProblemSpec.parse_testdata_files() and build_testdata_files() methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.spec = BatchProblemSpec()

    def test_parse_testdata_files_complete(self):
        """Test parsing complete testdata files JSON."""
        files_json = {
            'input': '1.in',
            'output': '1.out',
        }

        result = self.spec.parse_testdata_files(1, files_json)

        self.assertEqual(result.inputfile, '1.in')
        self.assertEqual(result.outputfile, '1.out')
        self.assertEqual(result.testdata_id, 1)

    def test_parse_testdata_files_empty(self):
        """Test parsing empty testdata files JSON."""
        files_json = {}

        result = self.spec.parse_testdata_files(1, files_json)

        self.assertEqual(result.inputfile, '')
        self.assertEqual(result.outputfile, '')
        self.assertEqual(result.testdata_id, 1)

    def test_parse_testdata_files_partial(self):
        """Test parsing partial testdata files JSON."""
        files_json = {
            'input': 'test.in',
        }

        result = self.spec.parse_testdata_files(1, files_json)

        self.assertEqual(result.inputfile, 'test.in')
        self.assertEqual(result.outputfile, '')

    def test_parse_testdata_files_extra_fields(self):
        """Test that extra fields in JSON are ignored."""
        files_json = {
            'input': 'data.in',
            'output': 'data.out',
            'extra_field': 'ignored',
            'another': 123,
        }

        result = self.spec.parse_testdata_files(1, files_json)

        # Should only return input and output
        self.assertEqual(result.inputfile, 'data.in')
        self.assertEqual(result.outputfile, 'data.out')

    def test_build_testdata_files_complete(self):
        """Test building complete testdata files JSON."""
        result = self.spec.build_testdata_files(
            BatchTestdata(testdata_id=1, inputfile='1.in', outputfile='1.out')
        )

        self.assertEqual(result['input'], '1.in')
        self.assertEqual(result['output'], '1.out')

    def test_build_testdata_files_empty(self):
        """Test building testdata files JSON with no arguments."""
        result = self.spec.build_testdata_files(
            BatchTestdata(testdata_id=1, inputfile='', outputfile='')
        )

        self.assertEqual(result['input'], '')
        self.assertEqual(result['output'], '')

    def test_build_testdata_files_partial(self):
        """Test building testdata files JSON with partial arguments."""
        result = self.spec.build_testdata_files(
            BatchTestdata(testdata_id=1, inputfile='test.in', outputfile='')
        )

        self.assertEqual(result['input'], 'test.in')
        self.assertEqual(result['output'], '')

    def test_roundtrip_testdata_files(self):
        """Test that parse_testdata_files(build_testdata_files(...)) works correctly."""
        original = BatchTestdata(testdata_id=1, inputfile='1.in', outputfile='1.out')

        # Build JSON
        built = self.spec.build_testdata_files(original)

        # Parse back
        parsed = self.spec.parse_testdata_files(1, built)

        # Should be equivalent
        self.assertEqual(parsed.inputfile, original.inputfile)
        self.assertEqual(parsed.outputfile, original.outputfile)

    def test_parse_testdata_files_with_paths(self):
        """Test parsing testdata files with directory paths."""
        files_json = {
            'input': 'testdata/subtask1/001.in',
            'output': 'testdata/subtask1/001.out',
        }

        result = self.spec.parse_testdata_files(1, files_json)

        self.assertEqual(result.inputfile, 'testdata/subtask1/001.in')
        self.assertEqual(result.outputfile, 'testdata/subtask1/001.out')

    def test_build_testdata_files_with_paths(self):
        """Test building testdata files with directory paths."""
        result = self.spec.build_testdata_files(
            BatchTestdata(testdata_id=1, inputfile='data/input/test01.txt', outputfile='data/output/test01.txt')
        )

        self.assertEqual(result['input'], 'data/input/test01.txt')
        self.assertEqual(result['output'], 'data/output/test01.txt')

    def test_parse_testdata_files_special_characters(self):
        """Test parsing filenames with special characters."""
        files_json = {
            'input': 'test-01_sample (copy).in',
            'output': 'test-01_sample (copy).out',
        }

        result = self.spec.parse_testdata_files(1, files_json)

        self.assertEqual(result.inputfile, 'test-01_sample (copy).in')
        self.assertEqual(result.outputfile, 'test-01_sample (copy).out')

    def test_build_testdata_files_unicode_filenames(self):
        """Test building testdata files with Unicode filenames."""
        result = self.spec.build_testdata_files(
            BatchTestdata(testdata_id=1, inputfile='測試資料.in', outputfile='測試資料.out')
        )

        self.assertEqual(result['input'], '測試資料.in')
        self.assertEqual(result['output'], '測試資料.out')


if __name__ == '__main__':
    unittest.main()
