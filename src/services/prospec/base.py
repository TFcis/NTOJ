from abc import ABC, abstractmethod
from typing import Any

from services.pro import BaseTestdata


class ProSpec(ABC):
    """Abstract base class for problem type specifications."""

    requires_checker = False

    def get_initial_directories(self) -> tuple[str, ...]:
        """Return problem-relative directories needed for manual setup."""
        return ()

    @abstractmethod
    def get_default_config(self) -> Any:
        """
        Get the default configuration for this problem type.

        Returns:
            Problem type-specific config object (e.g., BatchConfig) inheriting from BaseConfig
        """
        ...

    @abstractmethod
    def from_json(self, data: dict[str, Any]) -> Any:
        """
        Parse JSON data into a problem type-specific configuration.

        Args:
            data: JSON data from database

        Returns:
            Problem type-specific config object (e.g., BatchConfig) inheriting from BaseConfig
        """
        ...

    @abstractmethod
    def to_json(self, config: Any) -> dict[str, Any]:
        """
        Convert problem type-specific configuration to JSON.

        Args:
            config: Problem type-specific config object (e.g., BatchConfig)

        Returns:
            JSON-serializable dictionary
        """
        ...

    @abstractmethod
    async def emit_chal(
        self,
        db,
        rs,
        chal_id: int,
        pro_id: int,
        acct_id: int,
        contest_id: int,
        compiler_type: int,
        config,  # ProblemConfig with spec_config field
        priority: int,
        skip_nonac: bool = False,
    ) -> tuple[None, None] | tuple[tuple[str, str], None]:
        """
        Emit challenge to judge server.

        Args:
            db: Database connection pool
            rs: Redis connection
            chal_id: Challenge ID
            pro_id: Problem ID
            acct_id: Account ID
            contest_id: Contest ID
            compiler_type: Compiler type
            config: ProblemConfig object containing common fields and spec_config
            priority: Judge priority
            skip_nonac: Skip remaining testdata if non-AC

        Returns:
            (None, None) on success, or (error_tuple, None) on failure
        """
        ...

    @abstractmethod
    async def add_chal(
        self,
        db,
        rs,
        pro_id: int,
        acct_id: int,
        contest_id: int,
        compiler_type: int,
        code: str | dict[str, str],
        config,  # ProblemConfig with spec_config field
    ) -> tuple[None, int] | tuple[tuple[str, str], None]:
        """
        Add a new challenge.

        Args:
            db: Database connection pool
            rs: Redis connection
            pro_id: Problem ID
            acct_id: Account ID submitting the challenge
            contest_id: Contest ID (0 if not in contest)
            compiler_type: Compiler type
            code: One source string or a filename-to-source mapping
            config: ProblemConfig object containing common fields and spec_config

        Returns:
            (None, chal_id) on success, or (error_tuple, None) on failure
        """
        ...

    @abstractmethod
    def parse_testdata_files(
        self, testdata_id: int, files_json: dict[str, Any]
    ) -> BaseTestdata:
        """
        Parse testdata files JSON into a dictionary.

        Args:
            testdata_id: Testdata ID
            files_json: JSON data from testdata.files column

        Returns:
            Problem type-specific testdata object (e.g., BatchTestdata) inheriting from BaseTestdata
        """
        ...

    @abstractmethod
    def build_testdata_files(self, testdata: BaseTestdata) -> dict[str, Any]:
        """
        Build testdata files JSON from individual file paths.

        Args:
            testdata: Problem type-specific testdata object (e.g., BatchTestdata)


        Returns:
            JSON-serializable dictionary
        """
        ...

    @abstractmethod
    async def unpack_pro(
        self,
        db,
        rs,
        pro_id: int,
        pack_token: str,
    ) -> tuple[None, None] | tuple[tuple[str, str], None]:
        """
        Unpack and apply a packed problem archive for this problem type.

        Args:
            db: Database connection pool
            rs: Redis connection
            pro_id: The ID of the problem to unpack into
            pack_token: Token for identifying the uploaded archive

        Returns:
            (None, None) on success, or (error_tuple, None) on failure
        """
        ...

    @abstractmethod
    def get_allowed_file_paths(self, config, pro_id: int) -> list[str]:
        """
        Get allowed file paths for this problem type.

        Args:
            config: Problem type-specific config object
            pro_id: Problem ID

        Returns:
            List of allowed file paths relative to problem directory
        """
        ...

    @abstractmethod
    def get_file_structure(self, config, pro_id: int) -> list[dict[str, Any]]:
        """
        Get the file structure for this problem type.

        Args:
            config: Problem type-specific config object
            pro_id: Problem ID

        Returns:
            List of directory information with paths and files
        """
        ...
