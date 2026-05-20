

from typing import Optional

import requests

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class APIClientError(Exception):
    """Raised when API communication fails."""


class APIClient:
    def __init__(self):
        self.base_url = settings.API_BASE_URL
        self.timeout = settings.REQUEST_TIMEOUT
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-BOT-KEY": settings.BOT_API_KEY,
                "Accept": "application/json",
            }
        )

    def get_pending_job(self) -> Optional[dict]:
        """Poll for the next pending build job. Returns job dict or None if empty."""
        url = f"{self.base_url}{settings.ENDPOINT_PENDING}"
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch pending job: {e}")
            return None
        except ValueError as e:
            logger.error(f"Invalid JSON in pending response: {e}")
            return None

        servers = data.get("servers", [])
        if not servers:
            return None

        # API returns the oldest pending job; take the first item
        job = servers[0]
        logger.info(
            f"Picked up pending job id={job.get('id')} "
            f"domain={job.get('full_domain')}"
        )
        return job

    def mark_complete(
        self,
        job_id: int,
        apk_file: str,
        apk_build_time: str,
    ) -> bool:
        """Notify the API that a build has finished successfully."""
        url = f"{self.base_url}{settings.ENDPOINT_COMPLETE}"
        payload = {
            "id": job_id,
            "apk_file": apk_file,
            "apk_build_time": apk_build_time,
        }
        try:
            response = self.session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to mark job {job_id} as complete: {e}")
            return False
        except ValueError as e:
            logger.error(f"Invalid JSON in complete response: {e}")
            return False

        if data.get("success"):
            logger.info(f"Job {job_id} marked complete successfully")
            return True

        logger.error(
            f"Job {job_id} completion rejected: {data.get('message', 'unknown error')}"
        )
        return False

    def check_status(self, job_id: int) -> Optional[dict]:
        """Fetch the current status of a specific job."""
        url = f"{self.base_url}{settings.ENDPOINT_STATUS}/{job_id}"
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to check status for job {job_id}: {e}")
            return None
