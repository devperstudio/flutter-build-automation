"""Git operations wrapper using subprocess."""

import subprocess
from pathlib import Path
from typing import List

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class GitServiceError(Exception):
    """Raised when a git operation fails."""


class GitService:
    def __init__(self, project_path: str, branch: str = "main"):
        self.project_path = Path(project_path)
        self.branch = branch

    def pull_latest(self) -> List[str]:
        """Pull the latest code from the configured branch.

        Returns a list of changed file paths since the previous HEAD.
        """
        if not self.project_path.exists():
            raise GitServiceError(f"Project path does not exist: {self.project_path}")

        if not (self.project_path / ".git").exists():
            raise GitServiceError(f"Not a git repository: {self.project_path}")

        # Capture current HEAD before pulling
        old_head = self._run(["git", "rev-parse", "HEAD"]).strip()
        logger.info(f"Current HEAD: {old_head[:8]}")

        # Reset any local modifications to avoid merge conflicts on the build server
        self._run(["git", "reset", "--hard", "HEAD"])
        self._run(["git", "clean", "-fd"])

        # Checkout target branch and pull
        self._run(["git", "checkout", self.branch])
        self._run(["git", "pull", "origin", self.branch])

        new_head = self._run(["git", "rev-parse", "HEAD"]).strip()
        logger.info(f"New HEAD: {new_head[:8]}")

        if old_head == new_head:
            logger.info("No new commits since last build")
            return []

        # Get list of files changed between old and new HEAD
        diff_output = self._run(
            ["git", "diff", "--name-only", old_head, new_head]
        )
        changed_files = [f.strip() for f in diff_output.splitlines() if f.strip()]
        logger.info(f"Changed files: {len(changed_files)}")
        return changed_files

    def _run(self, command: List[str]) -> str:
        """Run a git command in the project directory. Returns stdout."""
        try:
            result = subprocess.run(
                command,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise GitServiceError(
                f"Git command failed: {' '.join(command)}\n"
                f"stdout: {e.stdout}\nstderr: {e.stderr}"
            ) from e
        except subprocess.TimeoutExpired as e:
            raise GitServiceError(
                f"Git command timed out: {' '.join(command)}"
            ) from e
