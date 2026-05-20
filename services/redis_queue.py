"""Redis-backed FIFO queue for build jobs."""

import json
from typing import Optional

import redis

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class RedisQueue:
    def __init__(self):
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        self.queue_name = settings.REDIS_QUEUE_NAME
        self.processing_set = settings.REDIS_PROCESSING_SET

    def ping(self) -> bool:
        """Verify Redis connectivity."""
        try:
            return self.client.ping()
        except redis.RedisError as e:
            logger.error(f"Redis ping failed: {e}")
            return False

    def enqueue(self, job: dict) -> bool:
        """Push a job onto the queue if it's not already queued or processing."""
        job_id = job.get("id")
        if job_id is None:
            logger.error(f"Cannot enqueue job without id: {job}")
            return False

        # Skip if this job is already being tracked anywhere
        if self.is_tracked(job_id):
            logger.debug(f"Job {job_id} already tracked, skipping enqueue")
            return False

        try:
            self.client.rpush(self.queue_name, json.dumps(job))
            self.client.sadd(self.processing_set, str(job_id))
            logger.info(f"Enqueued job {job_id} (queue size: {self.size()})")
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to enqueue job {job_id}: {e}")
            return False

    def dequeue(self, timeout: int = 5) -> Optional[dict]:
        """Block-pop the next job from the queue. Returns None on timeout."""
        try:
            result = self.client.blpop(self.queue_name, timeout=timeout)
        except redis.RedisError as e:
            logger.error(f"Failed to dequeue: {e}")
            return None

        if result is None:
            return None

        _, raw = result
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted job data in queue: {e}")
            return None

    def mark_done(self, job_id: int) -> None:
        """Remove a job from the processing tracker after completion or failure."""
        try:
            self.client.srem(self.processing_set, str(job_id))
        except redis.RedisError as e:
            logger.error(f"Failed to mark job {job_id} done: {e}")

    def is_tracked(self, job_id: int) -> bool:
        """Check if a job id is already in queue or being processed."""
        try:
            return bool(self.client.sismember(self.processing_set, str(job_id)))
        except redis.RedisError as e:
            logger.error(f"Failed to check tracking for job {job_id}: {e}")
            return False

    def size(self) -> int:
        """Return current queue length."""
        try:
            return self.client.llen(self.queue_name)
        except redis.RedisError:
            return 0
