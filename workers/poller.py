"""Poller. Every N seconds, fetches pending jobs and pushes them to the Redis queue."""

import time

from config.settings import settings
from services.api_client import APIClient
from services.redis_queue import RedisQueue
from utils.logger import get_logger

logger = get_logger(__name__)


class Poller:
    def __init__(self):
        self.api = APIClient()
        self.queue = RedisQueue()
        self.interval = settings.POLL_INTERVAL

    def run_forever(self) -> None:
        """Poll loop. Runs indefinitely until interrupted."""
        logger.info(
            f"Poller started (interval={self.interval}s, "
            f"endpoint={settings.API_BASE_URL}{settings.ENDPOINT_PENDING})"
        )

        if not self.queue.ping():
            raise RuntimeError("Cannot connect to Redis, aborting poller startup")

        while True:
            try:
                self._poll_once()
            except KeyboardInterrupt:
                logger.info("Poller stopping (keyboard interrupt)")
                break
            except Exception as e:
                # Keep polling even if a single iteration fails
                logger.exception(f"Unexpected error in poll loop: {e}")

            time.sleep(self.interval)

    def _poll_once(self) -> None:
        """Single poll iteration.

        The /apk-pending endpoint returns one job per call (oldest pending) and
        flips its status to processing on the server side. We loop here to drain
        all pending jobs within a single tick so they all end up in the local
        Redis queue immediately.
        """
        jobs_picked = 0
        # Safety cap to avoid infinite loops if the API misbehaves
        max_per_tick = 50

        while jobs_picked < max_per_tick:
            job = self.api.get_pending_job()
            if job is None:
                break

            enqueued = self.queue.enqueue(job)
            if enqueued:
                jobs_picked += 1
            else:
                # Already tracked; skip but keep draining
                logger.debug(f"Job {job.get('id')} already tracked")

        if jobs_picked > 0:
            logger.info(
                f"Polling tick: enqueued {jobs_picked} new job(s), "
                f"queue size now {self.queue.size()}"
            )


def main():
    settings.validate()
    poller = Poller()
    poller.run_forever()


if __name__ == "__main__":
    main()
