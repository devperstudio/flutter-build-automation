"""Flutter build operations with smart cache management."""

import shutil
import subprocess
import time
from pathlib import Path
from typing import List

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class FlutterServiceError(Exception):
    """Raised when a Flutter command fails."""


class FlutterService:
    # Build timeout in seconds (30 minutes is a generous upper bound)
    BUILD_TIMEOUT = 1800
    PUB_GET_TIMEOUT = 600

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)

    def prepare_build(self, changed_files: List[str]) -> None:

        needs_pub_get = any("pubspec.yaml" in f for f in changed_files)
        needs_clean = any(f.startswith("android/") for f in changed_files)

        # On first run after a fresh clone, always pub get
        if not (self.project_path / ".dart_tool").exists():
            needs_pub_get = True
            logger.info("No .dart_tool detected, will run pub get")

        if needs_clean:
            logger.info("Android files changed, running flutter clean")
            self._run_flutter(["clean"], timeout=300)

        if needs_pub_get or needs_clean:
            logger.info("Running flutter pub get")
            self._run_flutter(["pub", "get"], timeout=self.PUB_GET_TIMEOUT)

    def build_release_apk(self) -> Path:
        """Build a signed release APK. Returns the path to the produced APK."""
        logger.info("Starting flutter build apk --release")
        start = time.time()

        self._run_flutter(["build", "apk", "--release"], timeout=self.BUILD_TIMEOUT)

        elapsed = time.time() - start
        logger.info(f"Build completed in {elapsed:.1f} seconds")

        apk_path = self.project_path / settings.FLUTTER_APK_RELATIVE_PATH
        if not apk_path.exists():
            raise FlutterServiceError(f"Built APK not found at {apk_path}")

        size_mb = apk_path.stat().st_size / (1024 * 1024)
        logger.info(f"APK size: {size_mb:.2f} MB")
        return apk_path

    def _run_flutter(self, args: List[str], timeout: int) -> None:
        """Run a flutter command, streaming output to logs."""
        command = ["flutter"] + args
        logger.info(f"Executing: {' '.join(command)}")

        try:
            result = subprocess.run(
                command,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout,
            )
            # Log last 50 lines of stdout for visibility without flooding logs
            if result.stdout:
                tail = "\n".join(result.stdout.splitlines()[-50:])
                logger.debug(f"Flutter stdout (tail):\n{tail}")
        except subprocess.CalledProcessError as e:
            stderr_tail = "\n".join((e.stderr or "").splitlines()[-30:])
            stdout_tail = "\n".join((e.stdout or "").splitlines()[-30:])
            raise FlutterServiceError(
                f"Flutter command failed: {' '.join(command)}\n"
                f"Exit code: {e.returncode}\n"
                f"STDERR (tail):\n{stderr_tail}\n"
                f"STDOUT (tail):\n{stdout_tail}"
            ) from e
        except subprocess.TimeoutExpired as e:
            raise FlutterServiceError(
                f"Flutter command timed out after {timeout}s: {' '.join(command)}"
            ) from e


def copy_apk_to_output(
    source_apk: Path,
    output_dir: str,
    job_id: int,
    domain: str,
) -> Path:
    """Copy the built APK to the output directory with a descriptive filename."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Sanitize domain for use in filename
    safe_domain = domain.replace(".", "_").replace("/", "_")
    filename = f"build_{job_id}_{safe_domain}.apk"
    destination = output_path / filename

    shutil.copy2(source_apk, destination)
    logger.info(f"APK copied to: {destination}")
    return destination
