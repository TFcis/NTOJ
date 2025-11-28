"""Unit tests for FileManager service."""
import os
import tempfile
import shutil
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from services.filemanager import FileManager


class TestFileManager(unittest.TestCase):
    """Test FileManager for secure file operations."""

    def setUp(self):
        """Set up test directory and FileManager instance."""
        self.test_dir = tempfile.mkdtemp()
        self.file_mgr = FileManager(self.test_dir)

        # Create some test files
        with open(os.path.join(self.test_dir, 'test1.txt'), 'w') as f:
            f.write('content1')
        with open(os.path.join(self.test_dir, 'test2.txt'), 'w') as f:
            f.write('content2')

        # Create a subdirectory
        os.mkdir(os.path.join(self.test_dir, 'subdir'))
        with open(os.path.join(self.test_dir, 'subdir', 'test3.txt'), 'w') as f:
            f.write('content3')

    def tearDown(self):
        """Clean up test directory."""
        shutil.rmtree(self.test_dir)

    def test_init_normalizes_path(self):
        """Test that FileManager normalizes the base path."""
        relative_path = 'some/relative/path'
        mgr = FileManager(relative_path)
        self.assertTrue(os.path.isabs(mgr.basepath))

    def test_is_safe_path_within_basepath(self):
        """Test that files within basepath are considered safe."""
        self.assertTrue(self.file_mgr._is_safe_path('test1.txt'))
        self.assertTrue(self.file_mgr._is_safe_path('new_file.txt'))

    def test_is_safe_path_rejects_parent_directory(self):
        """Test that path traversal attempts are rejected."""
        self.assertFalse(self.file_mgr._is_safe_path('../etc/passwd'))
        self.assertFalse(self.file_mgr._is_safe_path('../../etc/passwd'))

    def test_is_safe_path_rejects_absolute_path(self):
        """Test that absolute paths outside basepath are rejected."""
        self.assertFalse(self.file_mgr._is_safe_path('/etc/passwd'))
        self.assertFalse(self.file_mgr._is_safe_path('/tmp/test.txt'))

    def test_is_safe_path_rejects_symlink(self):
        """Test that symlinks are rejected."""
        symlink_path = os.path.join(self.test_dir, 'symlink.txt')
        os.symlink('/etc/passwd', symlink_path)
        self.assertFalse(self.file_mgr._is_safe_path('symlink.txt'))

    def test_exists_for_existing_file(self):
        """Test exists returns True for existing files."""
        self.assertTrue(self.file_mgr.exists('test1.txt'))

    def test_exists_for_nonexistent_file(self):
        """Test exists returns False for nonexistent files."""
        self.assertFalse(self.file_mgr.exists('nonexistent.txt'))

    def test_delete_existing_file(self):
        """Test deleting an existing file."""
        err, _ = self.file_mgr.delete('test1.txt')
        self.assertIsNone(err)
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, 'test1.txt')))

    def test_delete_nonexistent_file(self):
        """Test deleting a nonexistent file returns error."""
        err, _ = self.file_mgr.delete('nonexistent.txt')
        self.assertIsNotNone(err)
        self.assertEqual(err[0], 'Enoext')

    def test_delete_unsafe_path(self):
        """Test deleting with unsafe path returns error."""
        err, _ = self.file_mgr.delete('../etc/passwd')
        self.assertIsNotNone(err)
        self.assertEqual(err[0], 'Eacces')

    def test_rename_success(self):
        """Test renaming a file successfully."""
        err, _ = self.file_mgr.rename('test1.txt', 'renamed.txt')
        self.assertIsNone(err)
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, 'test1.txt')))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'renamed.txt')))

    def test_rename_nonexistent_file(self):
        """Test renaming a nonexistent file returns error."""
        err, _ = self.file_mgr.rename('nonexistent.txt', 'renamed.txt')
        self.assertIsNotNone(err)
        self.assertEqual(err[0], 'Enoext')

    def test_rename_to_existing_file(self):
        """Test renaming to an existing filename returns error."""
        err, _ = self.file_mgr.rename('test1.txt', 'test2.txt')
        self.assertIsNotNone(err)
        self.assertEqual(err[0], 'Eexist')

    def test_rename_unsafe_path(self):
        """Test renaming with unsafe path returns error."""
        err, _ = self.file_mgr.rename('../test.txt', 'renamed.txt')
        self.assertIsNotNone(err)
        self.assertEqual(err[0], 'Eacces')

    def test_multiple_delete_success(self):
        """Test deleting multiple files successfully."""
        err, deleted = self.file_mgr.multiple_delete(['test1.txt', 'test2.txt'])
        self.assertIsNone(err)
        self.assertEqual(deleted, ['test1.txt', 'test2.txt'])
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, 'test1.txt')))
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, 'test2.txt')))

    def test_multiple_delete_with_nonexistent(self):
        """Test multiple delete fails if any file doesn't exist."""
        err, _ = self.file_mgr.multiple_delete(['test1.txt', 'nonexistent.txt'])
        self.assertIsNotNone(err)
        self.assertEqual(err[0], 'Enoext')
        # First file gets deleted before error occurs
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, 'test1.txt')))

    def test_multiple_delete_with_unsafe_path(self):
        """Test multiple delete fails with unsafe path."""
        err, _ = self.file_mgr.multiple_delete(['test1.txt', '../etc/passwd'])
        self.assertIsNotNone(err)
        self.assertEqual(err[0], 'Eacces')

    def test_read_text_file(self):
        """Test reading a text file."""
        err, content = self.file_mgr.read('test1.txt', 'r')
        self.assertIsNone(err)
        self.assertEqual(content, 'content1')

    def test_read_binary_file(self):
        """Test reading a binary file."""
        err, content = self.file_mgr.read('test1.txt', 'rb')
        self.assertIsNone(err)
        self.assertEqual(content, b'content1')

    def test_read_nonexistent_file(self):
        """Test reading a nonexistent file returns error."""
        err, _ = self.file_mgr.read('nonexistent.txt')
        self.assertIsNotNone(err)
        self.assertEqual(err[0], 'Enoext')

    def test_read_unsafe_path(self):
        """Test reading with unsafe path returns error."""
        err, _ = self.file_mgr.read('../etc/passwd')
        self.assertIsNotNone(err)
        self.assertEqual(err[0], 'Eacces')

    def test_get_filepath_safe(self):
        """Test getting filepath for safe file."""
        filepath = self.file_mgr.get_filepath('test1.txt')
        self.assertIsNotNone(filepath)
        self.assertEqual(filepath, os.path.join(self.test_dir, 'test1.txt'))

    def test_get_filepath_unsafe(self):
        """Test getting filepath for unsafe path returns None."""
        filepath = self.file_mgr.get_filepath('../etc/passwd')
        self.assertIsNone(filepath)

    def test_listdir_all_entries(self):
        """Test listing all directory entries."""
        entries = self.file_mgr.listdir(only_files=False)
        self.assertIn('test1.txt', entries)
        self.assertIn('test2.txt', entries)
        self.assertIn('subdir', entries)

    def test_listdir_only_files(self):
        """Test listing only files (not directories)."""
        entries = self.file_mgr.listdir(only_files=True)
        self.assertIn('test1.txt', entries)
        self.assertIn('test2.txt', entries)
        self.assertNotIn('subdir', entries)

    def test_listdir_nonexistent_directory(self):
        """Test listing nonexistent directory returns empty list."""
        mgr = FileManager(os.path.join(self.test_dir, 'nonexistent'))
        entries = mgr.listdir()
        self.assertEqual(entries, [])


class TestFileManagerAsync(unittest.IsolatedAsyncioTestCase):
    """Test FileManager async methods."""

    def setUp(self):
        """Set up test directory and FileManager instance."""
        self.test_dir = tempfile.mkdtemp()
        self.file_mgr = FileManager(self.test_dir)

    def tearDown(self):
        """Clean up test directory."""
        shutil.rmtree(self.test_dir)

    @patch('services.filemanager.PackService')
    async def test_update_from_pack_success(self, mock_pack_service):
        """Test updating file from pack token successfully."""
        # Create existing file
        with open(os.path.join(self.test_dir, 'test.txt'), 'w') as f:
            f.write('old content')

        mock_pack_service.inst = MagicMock()
        mock_pack_service.inst.direct_copy = AsyncMock(return_value=None)

        err, _ = await self.file_mgr.update_from_pack('test.txt', 'token123')
        self.assertIsNone(err)
        mock_pack_service.inst.direct_copy.assert_called_once()

    @patch('services.filemanager.PackService')
    async def test_update_from_pack_nonexistent(self, mock_pack_service):
        """Test updating nonexistent file returns error."""
        mock_pack_service.inst = MagicMock()
        mock_pack_service.inst.clear = AsyncMock()

        err, _ = await self.file_mgr.update_from_pack('nonexistent.txt', 'token123')
        self.assertIsNotNone(err)
        self.assertEqual(err[0], 'Enoext')
        mock_pack_service.inst.clear.assert_called_once_with('token123')

    @patch('services.filemanager.PackService')
    async def test_update_from_pack_unsafe_path(self, mock_pack_service):
        """Test updating with unsafe path returns error."""
        mock_pack_service.inst = MagicMock()
        mock_pack_service.inst.clear = AsyncMock()

        err, _ = await self.file_mgr.update_from_pack('../etc/passwd', 'token123')
        self.assertIsNotNone(err)
        self.assertEqual(err[0], 'Eacces')
        mock_pack_service.inst.clear.assert_called_once_with('token123')

    @patch('services.filemanager.PackService')
    async def test_copy_from_pack_success(self, mock_pack_service):
        """Test creating file from pack token successfully."""
        mock_pack_service.inst = MagicMock()
        mock_pack_service.inst.direct_copy = AsyncMock(return_value=None)

        err, _ = await self.file_mgr.copy_from_pack('new_file.txt', 'token123')
        self.assertIsNone(err)
        mock_pack_service.inst.direct_copy.assert_called_once()

    @patch('services.filemanager.PackService')
    async def test_copy_from_pack_existing_file(self, mock_pack_service):
        """Test creating file that already exists returns error."""
        # Create existing file
        with open(os.path.join(self.test_dir, 'existing.txt'), 'w') as f:
            f.write('content')

        mock_pack_service.inst = MagicMock()
        mock_pack_service.inst.clear = AsyncMock()

        err, _ = await self.file_mgr.copy_from_pack('existing.txt', 'token123')
        self.assertIsNotNone(err)
        self.assertEqual(err[0], 'Eexist')
        mock_pack_service.inst.clear.assert_called_once_with('token123')

    @patch('services.filemanager.PackService')
    async def test_copy_from_pack_unsafe_path(self, mock_pack_service):
        """Test copying with unsafe path returns error."""
        mock_pack_service.inst = MagicMock()
        mock_pack_service.inst.clear = AsyncMock()

        err, _ = await self.file_mgr.copy_from_pack('../etc/passwd', 'token123')
        self.assertIsNotNone(err)
        self.assertEqual(err[0], 'Eacces')
        mock_pack_service.inst.clear.assert_called_once_with('token123')

    @patch('services.filemanager.PackService')
    async def test_copy_from_pack_with_error(self, mock_pack_service):
        """Test copying from pack when direct_copy returns error."""
        mock_pack_service.inst = MagicMock()
        mock_pack_service.inst.direct_copy = AsyncMock(return_value=(('Eunk', 'Unknown error'), None))

        err, _ = await self.file_mgr.copy_from_pack('new_file.txt', 'token123')
        self.assertIsNotNone(err)
        self.assertEqual(err[0], 'Eunk')


if __name__ == '__main__':
    unittest.main()
