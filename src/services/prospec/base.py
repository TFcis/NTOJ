from abc import ABC, abstractmethod
from typing import Any


class ProSpec(ABC):
    """Abstract base class for problem type specifications."""

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
        code: str,
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
            code: Source code
            config: ProblemConfig object containing common fields and spec_config

        Returns:
            (None, chal_id) on success, or (error_tuple, None) on failure
        """
        ...

    @abstractmethod
    def parse_testdata_files(self, files_json: dict[str, Any]) -> dict[str, str]:
        """
        Parse testdata files JSON into a dictionary.

        Args:
            files_json: JSON data from testdata.files column

        Returns:
            Dictionary mapping file type to file path
        """
        ...

    @abstractmethod
    def build_testdata_files(self, **files) -> dict[str, Any]:
        """
        Build testdata files JSON from individual file paths.

        Args:
            **files: Keyword arguments for file paths

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
