"""Build worker. Consumes jobs from the Redis queue and builds APKs sequentially."""

import time
from typing import Optional

from config.settings import settings
from services.api_client import APIClient
from services.flutter_service import (
    FlutterService,
    FlutterServiceError,
    copy_apk_to_output,
)
from services.git_service import GitService, GitServiceError
from services.redis_queue import RedisQueue
from utils.logger import get_logger
from utils.url_injector import URLInjectionError, URLInjector

logger = get_logger(__name__)


class BuildWorker:
    def __init__(self):
        self.queue = RedisQueue()
        self.api = APIClient()
        self.git = GitService(settings.PROJECT_PATH, settings.GIT_BRANCH)
        self.flutter = FlutterService(settings.PROJECT_PATH)
        self.injector = URLInjector(settings.PROJECT_PATH)

    def run_forever(self) -> None:
        """Main loop. Blocks on the queue, processes one job at a time."""
        logger.info("Build worker started")
        while True:
            try:
                job = self.queue.dequeue(timeout=10)
                if job is None:
                    continue
                self._process_job(job)
            except KeyboardInterrupt:
                logger.info("Build worker stopping (keyboard interrupt)")
                break
            except Exception as e:
                # Catch-all to keep the worker alive across unexpected errors
                logger.exception(f"Unexpected error in worker loop: {e}")
                time.sleep(5)

    def _process_job(self, job: dict) -> None:
        """Execute a single build job end-to-end."""
        job_id = job.get("id")
        domain = job.get("full_domain", "")

        if not job_id or not domain:
            logger.error(f"Invalid job payload, missing id or full_domain: {job}")
            return

        logger.info(f"===== Starting build for job {job_id} ({domain}) =====")
        start = time.time()
        new_url = self._build_url_from_domain(domain)

        try:
            # Step 1: Pull latest code
            changed_files = self.git.pull_latest()

            # Step 2: Inject the new base URL into Dart and Kotlin files
            self.injector.inject(
                settings.DART_CONFIG_FILE,
                settings.KOTLIN_API_FILE,
                new_url,
            )

            # Treat injected files as changed for the prepare step
            injected_files = [settings.DART_CONFIG_FILE, settings.KOTLIN_API_FILE]
            all_changed = list(set(changed_files + injected_files))

            # Step 3: Run pub get / clean as needed
            self.flutter.prepare_build(all_changed)

            # Step 4: Build the release APK
            apk_source = self.flutter.build_release_apk()

            # Step 5: Copy APK to output directory
            apk_destination = copy_apk_to_output(
                apk_source,
                settings.APK_OUTPUT_DIR,
                job_id,
                domain,
            )

            # Step 6: Notify the API
            elapsed = time.time() - start
            build_time_str = self._format_duration(elapsed)
            success = self.api.mark_complete(
                job_id=job_id,
                apk_file=apk_destination.name,
                apk_build_time=build_time_str,
            )

            if success:
                logger.info(
                    f"===== Job {job_id} completed in {build_time_str} ====="
                )
                # Remove backup files only after a successful API confirmation
                self.injector.cleanup_backups()
            else:
                logger.error(f"Job {job_id} built but API rejected completion")

        except (GitServiceError, FlutterServiceError, URLInjectionError) as e:
            logger.error(f"Build failed for job {job_id}: {e}")
            # Backups already rolled back by injector on URLInjectionError;
            # for other errors, restore source files explicitly
            self.injector._rollback()
        except Exception as e:
            logger.exception(f"Unexpected error building job {job_id}: {e}")
            self.injector._rollback()
        finally:
            self.queue.mark_done(job_id)

    @staticmethod
    def _build_url_from_domain(domain: str) -> str:
        """Convert a bare domain into the full base URL used by the app.

        The API returns full_domain values like 'mars.bkserver.tech'. The Flutter
        app expects URLs like 'https://mars.bkserver.tech/api/v1'. Adjust here if
        the API ever starts returning full URLs.
        """
        if domain.startswith(("http://", "https://")):
            return domain.rstrip("/")
        return f"https://{domain}/api/v1"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format seconds into a string like '3m 42s' (matches API expectation)."""
        minutes, secs = divmod(int(seconds), 60)
        return f"{minutes}m {secs}s"


def main():
    settings.validate()
    worker = BuildWorker()
    worker.run_forever()


if __name__ == "__main__":
    main()
