"""Unit tests for BatchProblemSpec JSON serialization."""
import unittest

from services.pro import CheckerType, SummaryType
from services.prospec.batch import BatchProblemSpec, BatchConfig
from services.chal import Compiler


class TestBatchProblemSpecFromJson(unittest.TestCase):
    """Test BatchProblemSpec.from_json() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.spec = BatchProblemSpec()

    def test_from_json_minimal(self):
        """Test parsing minimal JSON configuration."""
        data = {
            'checker_type': CheckerType.DIFF,
            'summary_type': SummaryType.GROUPMIN,
        }

        config = self.spec.from_json(data)

        self.assertIsInstance(config, BatchConfig)
        self.assertEqual(config.chalmeta, '')
        self.assertEqual(config.userprog_compile_args, '')
        self.assertEqual(config.checker_type, CheckerType.DIFF)
        self.assertIsNone(config.checker_compiler)
        self.assertEqual(config.checker_compile_args, '')
        self.assertEqual(config.summary_type, SummaryType.GROUPMIN)
        self.assertIsNone(config.summary_compiler)
        self.assertEqual(config.summary_compile_args, '')
        self.assertFalse(config.has_grader)
        self.assertEqual(config.allow_compilers, set())

    def test_from_json_full_config(self):
        """Test parsing complete JSON configuration."""
        data = {
            'chalmeta': '{"input": "input.txt", "output": "output.txt"}',
            'userprog_compile_args': '-std=c++17 -O2',
            'checker_type': CheckerType.CMS_TPS_TESTLIB,
            'checker_compiler': Compiler.GPP,
            'checker_compile_args': '-std=c++17',
            'summary_type': SummaryType.CUSTOM,
            'summary_compiler': Compiler.PYTHON3,
            'summary_compile_args': '-O',
            'has_grader': True,
            'allow_compilers': [Compiler.GPP, Compiler.CLANGPP, Compiler.PYTHON3],
        }

        config = self.spec.from_json(data)

        self.assertEqual(config.chalmeta, '{"input": "input.txt", "output": "output.txt"}')
        self.assertEqual(config.userprog_compile_args, '-std=c++17 -O2')
        self.assertEqual(config.checker_type, CheckerType.CMS_TPS_TESTLIB)
        self.assertEqual(config.checker_compiler, Compiler.GPP)
        self.assertEqual(config.checker_compile_args, '-std=c++17')
        self.assertEqual(config.summary_type, SummaryType.CUSTOM)
        self.assertEqual(config.summary_compiler, Compiler.PYTHON3)
        self.assertEqual(config.summary_compile_args, '-O')
        self.assertTrue(config.has_grader)
        self.assertEqual(config.allow_compilers, {Compiler.GPP, Compiler.CLANGPP, Compiler.PYTHON3})

    def test_from_json_compiler_type_conversion(self):
        """Test that compiler integer values are converted to Compiler enum."""
        data = {
            'checker_type': CheckerType.DIFF,
            'checker_compiler': int(Compiler.GCC),  # Pass as integer
            'summary_type': SummaryType.CUSTOM,
            'summary_compiler': int(Compiler.PYTHON3),  # Pass as integer
        }

        config = self.spec.from_json(data)

        # Should be converted to Compiler enum
        self.assertEqual(config.checker_compiler, Compiler.GCC)
        self.assertEqual(config.summary_compiler, Compiler.PYTHON3)

    def test_from_json_empty_allow_compilers(self):
        """Test parsing with empty allow_compilers list."""
        data = {
            'checker_type': CheckerType.DIFF,
            'summary_type': SummaryType.GROUPMIN,
            'allow_compilers': [],
        }

        config = self.spec.from_json(data)

        self.assertEqual(config.allow_compilers, set())

    def test_from_json_multiple_compilers(self):
        """Test parsing with multiple allowed compilers."""
        data = {
            'checker_type': CheckerType.DIFF,
            'summary_type': SummaryType.GROUPMIN,
            'allow_compilers': [
                Compiler.GCC,
                Compiler.GPP,
                Compiler.CLANG,
                Compiler.CLANGPP,
                Compiler.PYTHON3,
            ],
        }

        config = self.spec.from_json(data)

        expected = {Compiler.GCC, Compiler.GPP, Compiler.CLANG, Compiler.CLANGPP, Compiler.PYTHON3}
        self.assertEqual(config.allow_compilers, expected)

    def test_from_json_null_compilers(self):
        """Test parsing with None/null compiler values."""
        data = {
            'checker_type': CheckerType.DIFF,
            'checker_compiler': None,
            'summary_type': SummaryType.GROUPMIN,
            'summary_compiler': None,
        }

        config = self.spec.from_json(data)

        self.assertIsNone(config.checker_compiler)
        self.assertIsNone(config.summary_compiler)

    def test_from_json_has_grader_false(self):
        """Test parsing with has_grader explicitly set to False."""
        data = {
            'checker_type': CheckerType.DIFF,
            'summary_type': SummaryType.GROUPMIN,
            'has_grader': False,
        }

        config = self.spec.from_json(data)

        self.assertFalse(config.has_grader)

    def test_from_json_has_grader_true(self):
        """Test parsing with has_grader set to True."""
        data = {
            'checker_type': CheckerType.DIFF,
            'summary_type': SummaryType.GROUPMIN,
            'has_grader': True,
        }

        config = self.spec.from_json(data)

        self.assertTrue(config.has_grader)


class TestBatchProblemSpecToJson(unittest.TestCase):
    """Test BatchProblemSpec.to_json() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.spec = BatchProblemSpec()

    def test_to_json_minimal(self):
        """Test serializing minimal BatchConfig to JSON."""
        config = BatchConfig(
            chalmeta='',
            userprog_compile_args='',
            checker_type=CheckerType.DIFF,
            checker_compiler=None,
            checker_compile_args='',
            summary_type=SummaryType.GROUPMIN,
            summary_compiler=None,
            summary_compile_args='',
            has_grader=False,
            allow_compilers=set(),
        )

        result = self.spec.to_json(config)

        self.assertEqual(result['chalmeta'], '')
        self.assertEqual(result['userprog_compile_args'], '')
        self.assertEqual(result['checker_type'], int(CheckerType.DIFF))
        self.assertIsNone(result['checker_compiler'])
        self.assertEqual(result['checker_compile_args'], '')
        self.assertEqual(result['summary_type'], int(SummaryType.GROUPMIN))
        self.assertIsNone(result['summary_compiler'])
        self.assertEqual(result['summary_compile_args'], '')
        self.assertFalse(result['has_grader'])
        self.assertEqual(result['allow_compilers'], [])

    def test_to_json_compilers_are_integers(self):
        """Test that compiler enums are serialized to integers."""
        config = BatchConfig(
            chalmeta='',
            userprog_compile_args='',
            checker_type=CheckerType.DIFF,
            checker_compiler=Compiler.GCC,
            checker_compile_args='',
            summary_type=SummaryType.CUSTOM,
            summary_compiler=Compiler.PYTHON3,
            summary_compile_args='',
            has_grader=False,
            allow_compilers={Compiler.GPP, Compiler.RUST},
        )

        result = self.spec.to_json(config)

        # Verify types are integers, not Compiler enums
        self.assertIsInstance(result['checker_compiler'], int)
        self.assertIsInstance(result['summary_compiler'], int)
        for compiler in result['allow_compilers']:
            self.assertIsInstance(compiler, int)

    def test_to_json_allow_compilers_is_list(self):
        """Test that allow_compilers is serialized as a list, not a set."""
        config = BatchConfig(
            chalmeta='',
            userprog_compile_args='',
            checker_type=CheckerType.DIFF,
            checker_compiler=None,
            checker_compile_args='',
            summary_type=SummaryType.GROUPMIN,
            summary_compiler=None,
            summary_compile_args='',
            has_grader=False,
            allow_compilers={Compiler.GCC, Compiler.GPP},
        )

        result = self.spec.to_json(config)

        # Should be a list for JSON serialization
        self.assertIsInstance(result['allow_compilers'], list)
        self.assertEqual(len(result['allow_compilers']), 2)

    def test_roundtrip_serialization(self):
        """Test that from_json(to_json(config)) returns equivalent config."""
        original = BatchConfig(
            chalmeta='{"test": "data"}',
            userprog_compile_args='-std=c++20',
            checker_type=CheckerType.STD_TESTLIB,
            checker_compiler=Compiler.CLANGPP,
            checker_compile_args='-O3',
            summary_type=SummaryType.OVERWRITE,
            summary_compiler=Compiler.PYTHON3,
            summary_compile_args='-O',
            has_grader=True,
            allow_compilers={Compiler.GPP, Compiler.CLANGPP, Compiler.PYTHON3},
        )

        # Serialize to JSON and parse back
        json_data = self.spec.to_json(original)
        reconstructed = self.spec.from_json(json_data)

        # Compare all fields
        self.assertEqual(reconstructed.chalmeta, original.chalmeta)
        self.assertEqual(reconstructed.userprog_compile_args, original.userprog_compile_args)
        self.assertEqual(reconstructed.checker_type, original.checker_type)
        self.assertEqual(reconstructed.checker_compiler, original.checker_compiler)
        self.assertEqual(reconstructed.checker_compile_args, original.checker_compile_args)
        self.assertEqual(reconstructed.summary_type, original.summary_type)
        self.assertEqual(reconstructed.summary_compiler, original.summary_compiler)
        self.assertEqual(reconstructed.summary_compile_args, original.summary_compile_args)
        self.assertEqual(reconstructed.has_grader, original.has_grader)
        self.assertEqual(reconstructed.allow_compilers, original.allow_compilers)


if __name__ == '__main__':
    unittest.main()
