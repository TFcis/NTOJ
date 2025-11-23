"""Unit tests for BatchConfig dataclass."""
import unittest
from dataclasses import FrozenInstanceError

from services.pro import CheckerType, SummaryType
from services.prospec.batch import BatchConfig
from services.chal import Compiler


class TestBatchConfig(unittest.TestCase):
    """Test BatchConfig dataclass creation and validation."""

    def test_create_basic_config(self):
        """Test creating a basic BatchConfig with required fields."""
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

        self.assertEqual(config.chalmeta, '')
        self.assertEqual(config.checker_type, CheckerType.DIFF)
        self.assertEqual(config.summary_type, SummaryType.GROUPMIN)
        self.assertFalse(config.has_grader)
        self.assertEqual(config.allow_compilers, set())

    def test_create_config_with_grader(self):
        """Test creating BatchConfig with grader enabled."""
        config = BatchConfig(
            chalmeta='',
            userprog_compile_args='-std=c++17',
            checker_type=CheckerType.DIFF,
            checker_compiler=None,
            checker_compile_args='',
            summary_type=SummaryType.GROUPMIN,
            summary_compiler=None,
            summary_compile_args='',
            has_grader=True,
            allow_compilers={Compiler.GPP, Compiler.CLANGPP},
        )

        self.assertTrue(config.has_grader)
        self.assertEqual(config.userprog_compile_args, '-std=c++17')
        self.assertEqual(config.allow_compilers, {Compiler.GPP, Compiler.CLANGPP})

    def test_create_config_with_custom_checker(self):
        """Test creating BatchConfig with custom checker."""
        config = BatchConfig(
            chalmeta='',
            userprog_compile_args='',
            checker_type=CheckerType.TOJ,
            checker_compiler=Compiler.GPP,
            checker_compile_args='-O2',
            summary_type=SummaryType.GROUPMIN,
            summary_compiler=None,
            summary_compile_args='',
            has_grader=False,
            allow_compilers=set(),
        )

        self.assertEqual(config.checker_type, CheckerType.TOJ)
        self.assertEqual(config.checker_compiler, Compiler.GPP)
        self.assertEqual(config.checker_compile_args, '-O2')

    def test_create_config_with_summary(self):
        """Test creating BatchConfig with summary enabled."""
        config = BatchConfig(
            chalmeta='',
            userprog_compile_args='',
            checker_type=CheckerType.DIFF,
            checker_compiler=None,
            checker_compile_args='',
            summary_type=SummaryType.CUSTOM,
            summary_compiler=Compiler.PYTHON3,
            summary_compile_args='',
            has_grader=False,
            allow_compilers=set(),
        )

        self.assertEqual(config.summary_type, SummaryType.CUSTOM)
        self.assertEqual(config.summary_compiler, Compiler.PYTHON3)

    def test_create_config_with_ioredir(self):
        """Test creating BatchConfig with IORedir chalmeta."""
        chalmeta = '{"input": "input.txt", "output": "output.txt"}'
        config = BatchConfig(
            chalmeta=chalmeta,
            userprog_compile_args='',
            checker_type=CheckerType.IOREDIR,
            checker_compiler=None,
            checker_compile_args='',
            summary_type=SummaryType.GROUPMIN,
            summary_compiler=None,
            summary_compile_args='',
            has_grader=False,
            allow_compilers=set(),
        )

        self.assertEqual(config.chalmeta, chalmeta)
        self.assertEqual(config.checker_type, CheckerType.IOREDIR)

    def test_allow_compilers_set_operations(self):
        """Test set operations on allow_compilers field."""
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
            allow_compilers={Compiler.GPP, Compiler.PYTHON3},
        )

        # Test set contains
        self.assertIn(Compiler.GPP, config.allow_compilers)
        self.assertIn(Compiler.PYTHON3, config.allow_compilers)
        self.assertNotIn(Compiler.RUST, config.allow_compilers)

        # Test set length
        self.assertEqual(len(config.allow_compilers), 2)

    def test_config_immutability(self):
        """Test that BatchConfig uses slots for memory efficiency."""
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

        # Verify slots are working - can't add new attributes
        with self.assertRaises(AttributeError):
            config.new_field = 'test'


if __name__ == '__main__':
    unittest.main()
