"""URL injection utility. Replaces base URL in Dart and Kotlin files safely."""

import re
import shutil
from pathlib import Path
from typing import List, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)


class URLInjectionError(Exception):
    """Raised when URL injection fails."""


class URLInjector:
    # Regex patterns match the URL value inside double quotes after the variable name
    DART_PATTERN = re.compile(r'(baseUrl\s*=\s*)"[^"]*"')
    KOTLIN_PATTERN = re.compile(r'(BASE_URL\s*=\s*)"[^"]*"')

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.backups: List[Tuple[Path, Path]] = []

    def inject(
        self,
        dart_file_relative: str,
        kotlin_file_relative: str,
        new_url: str,
    ) -> None:
        """Replace base URL in both files. Rolls back on any failure."""
        dart_file = self.project_path / dart_file_relative
        kotlin_file = self.project_path / kotlin_file_relative

        self._verify_files_exist(dart_file, kotlin_file)

        try:
            self._replace_in_file(dart_file, self.DART_PATTERN, new_url, "Dart")
            self._replace_in_file(kotlin_file, self.KOTLIN_PATTERN, new_url, "Kotlin")
            logger.info(f"URL injection successful: {new_url}")
        except Exception as e:
            logger.error(f"URL injection failed, rolling back: {e}")
            self._rollback()
            raise

    def _verify_files_exist(self, *files: Path) -> None:
        for f in files:
            if not f.exists():
                raise URLInjectionError(f"Required file not found: {f}")

    def _replace_in_file(
        self,
        file_path: Path,
        pattern: re.Pattern,
        new_url: str,
        label: str,
    ) -> None:
        # Read original content
        original_content = file_path.read_text(encoding="utf-8")

        # Create backup before modification
        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        shutil.copy2(file_path, backup_path)
        self.backups.append((file_path, backup_path))

        # Perform regex replacement
        replacement = rf'\1"{new_url}"'
        new_content, count = pattern.subn(replacement, original_content)

        if count == 0:
            raise URLInjectionError(
                f"{label} file: pattern not found in {file_path}. "
                f"Expected variable assignment matching {pattern.pattern}"
            )

        if count > 1:
            logger.warning(
                f"{label} file: pattern matched {count} times in {file_path}. "
                f"All occurrences replaced."
            )

        # Write modified content
        file_path.write_text(new_content, encoding="utf-8")

        # Verify the new URL is present
        if new_url not in file_path.read_text(encoding="utf-8"):
            raise URLInjectionError(
                f"{label} file: verification failed, new URL not found after write"
            )

        logger.info(f"{label} file updated: {file_path.name} ({count} replacement)")

    def _rollback(self) -> None:
        """Restore all modified files from their backups."""
        for original, backup in self.backups:
            if backup.exists():
                shutil.copy2(backup, original)
                logger.info(f"Rolled back: {original.name}")

    def cleanup_backups(self) -> None:
        """Remove backup files after successful build."""
        for _, backup in self.backups:
            try:
                if backup.exists():
                    backup.unlink()
            except OSError as e:
                logger.warning(f"Could not remove backup {backup}: {e}")
        self.backups.clear()
