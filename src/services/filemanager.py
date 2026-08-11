"""
FileManager Service - Secure file operations within a specified directory.

This service provides a safe abstraction for file operations,
ensuring all operations stay within a designated base path and only operate on regular files.
"""

import os
import logging
from typing import Literal

from services.pack import PackService

logger = logging.getLogger("tornado.application")

ErrorType = tuple[tuple[str, str], None]


class FileManager:
    """
    File manager for secure file operations within a base directory.

    All file operations are restricted to the base path and only work with regular files.
    Attempts to access files outside the base path or non-regular files are rejected.
    """

    def __init__(self, basepath: str):
        """
        Initialize FileManager with a base directory path.

        Args:
            basepath: Absolute path to the directory where file operations are allowed
        """
        self.basepath = os.path.realpath(os.path.abspath(basepath))

    def _is_safe_path(self, filename: str) -> bool:
        """
        Check if a filename is safe to access within basepath.

        Args:
            filename: The filename to check

        Returns:
            True if the file is within basepath and is (or would be) a regular file
        """
        try:
            filepath = os.path.abspath(os.path.join(self.basepath, filename))
            resolved_filepath = os.path.realpath(filepath)
            if os.path.commonpath([self.basepath, resolved_filepath]) != self.basepath:
                return False
        except (OSError, TypeError, ValueError):
            return False

        try:
            # If the final path exists, verify it is a regular file and not a symlink.
            if os.path.exists(filepath):
                return os.path.isfile(filepath) and not os.path.islink(filepath)
        except (OSError, ValueError):
            return False

        # Non-existent paths are safe only after all existing symlink components
        # have been resolved and checked above.
        return True

    def exists(self, filename: str) -> bool:
        """Check if a file exists in the managed directory."""
        if not self._is_safe_path(filename):
            return False
        filepath = os.path.join(self.basepath, filename)
        return os.path.exists(filepath)

    def delete(self, filename: str) -> tuple[None, None] | ErrorType:
        """
        Delete a file from the managed directory.

        Args:
            filename: Name of the file to delete

        Returns:
            (None, None) on success, or error tuple on failure
        """
        if not self._is_safe_path(filename):
            return ('Eacces', 'Access denied: invalid file path'), None

        filepath = os.path.join(self.basepath, filename)
        if not os.path.exists(filepath):
            return ('Enoext', 'File not found'), None

        try:
            os.remove(filepath)
            return None, None
        except OSError as e:
            logger.error(f"Failed to delete file {filepath}: {e}", exc_info=True)
            return ('Eunk', f'Failed to delete file: {str(e)}'), None

    def rename(self, old_filename: str, new_filename: str) -> tuple[None, None] | ErrorType:
        """
        Rename a file within the managed directory.

        Args:
            old_filename: Current filename
            new_filename: New filename

        Returns:
            (None, None) on success, or error tuple on failure
        """
        if not self._is_safe_path(old_filename) or not self._is_safe_path(new_filename):
            return ('Eacces', 'Access denied: invalid file path'), None

        old_filepath = os.path.join(self.basepath, old_filename)
        new_filepath = os.path.join(self.basepath, new_filename)

        if not os.path.exists(old_filepath):
            return ('Enoext', 'Old filename not found'), None

        if os.path.exists(new_filepath):
            return ('Eexist', 'New filename already exists'), None

        try:
            os.rename(old_filepath, new_filepath)
            return None, None
        except OSError as e:
            logger.error(f"Failed to rename file from {old_filepath} to {new_filepath}: {e}", exc_info=True)
            return ('Eunk', f'Failed to rename file: {str(e)}'), None

    async def update_from_pack(self, filename: str, pack_token: str) -> tuple[None, None] | ErrorType:
        """
        Update an existing file from a pack token.

        Args:
            filename: Name of the file to update
            pack_token: Pack token identifying the uploaded file

        Returns:
            (None, None) on success, or error tuple on failure
        """
        if not self._is_safe_path(filename):
            await PackService.inst.clear(pack_token)
            return ('Eacces', 'Access denied: invalid file path'), None

        filepath = os.path.join(self.basepath, filename)

        if not os.path.exists(filepath):
            await PackService.inst.clear(pack_token)
            return ('Enoext', 'File not found'), None

        result = await PackService.inst.direct_copy(pack_token, filepath)
        if result is not None:
            await PackService.inst.clear(pack_token)
            # direct_copy returned an error
            return result

        return None, None

    async def copy_from_pack(self, filename: str, pack_token: str) -> tuple[None, None] | ErrorType:
        """
        Create a new file from a pack token.

        Args:
            filename: Name of the new file to create
            pack_token: Pack token identifying the uploaded file

        Returns:
            (None, None) on success, or error tuple on failure
        """
        if not self._is_safe_path(filename):
            await PackService.inst.clear(pack_token)
            return ('Eacces', 'Access denied: invalid file path'), None

        filepath = os.path.join(self.basepath, filename)

        if os.path.exists(filepath):
            await PackService.inst.clear(pack_token)
            return ('Eexist', 'File already exists'), None

        result = await PackService.inst.direct_copy(pack_token, filepath)
        if result is not None:
            await PackService.inst.clear(pack_token)
            # direct_copy returned an error
            return result

        return None, None

    def multiple_delete(self, filenames: list[str]) -> tuple[None, list[str]] | ErrorType:
        """
        Delete multiple files from the managed directory.

        Args:
            filenames: List of filenames to delete

        Returns:
            (None, list of successfully deleted files) on success,
            or error tuple if any file operation fails
        """
        deleted = []

        for filename in filenames:
            if not self._is_safe_path(filename):
                return ('Eacces', f'Access denied for file: {filename}'), None

            filepath = os.path.join(self.basepath, filename)

            if not os.path.exists(filepath):
                return ('Enoext', f'File not found: {filename}'), None

            try:
                os.remove(filepath)
                deleted.append(filename)
            except OSError as e:
                logger.error(f"Failed to delete file {filepath}: {e}", exc_info=True)
                return ('Eunk', f'Failed to delete {filename}: {str(e)}'), None

        return None, deleted

    def read(self, filename: str, mode: Literal['r', 'rb'] = 'r') -> tuple[None, str | bytes] | ErrorType:
        """
        Read file contents.

        Args:
            filename: Name of the file to read
            mode: Read mode ('r' for text, 'rb' for binary)

        Returns:
            (None, file_content) on success, or error tuple on failure
        """
        if not self._is_safe_path(filename):
            return ('Eacces', 'Access denied: invalid file path'), None

        filepath = os.path.join(self.basepath, filename)

        if not os.path.exists(filepath):
            return ('Enoext', 'File not found'), None

        try:
            with open(filepath, mode) as f:
                content = f.read()
            return None, content
        except UnicodeDecodeError:
            return ('Eunicode', 'File contains invalid unicode characters'), None
        except OSError as e:
            logger.error(f"Failed to read file {filepath}: {e}", exc_info=True)
            return ('Eunk', f'Failed to read file: {str(e)}'), None

    def get_filepath(self, filename: str) -> str | None:
        """
        Get the absolute filepath if the file is safe to access.

        Args:
            filename: Name of the file

        Returns:
            Absolute filepath if safe, None otherwise
        """
        if not self._is_safe_path(filename):
            return None
        return os.path.join(self.basepath, filename)

    def listdir(self, only_files: bool = False) -> list[str]:
        """
        List all entries in the managed directory.

        Args:
            only_files: If True, only return regular files (not directories)

        Returns:
            List of filenames/directory names in the managed directory
        """
        if not os.path.exists(self.basepath):
            return []

        entries = os.listdir(self.basepath)

        if only_files:
            # Filter to only include regular files
            entries = [
                name for name in entries
                if os.path.isfile(os.path.join(self.basepath, name))
            ]

        return entries
