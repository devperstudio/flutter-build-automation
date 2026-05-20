"""Entry point. Runs poller and builder concurrently in separate threads.

For production, you can also run workers/poller.py and workers/builder.py as
separate processes (e.g., two systemd services). This combined entry point is
convenient for development and small deployments.
"""

import signal
import sys
import threading

from config.settings import settings
from utils.logger import get_logger
from workers.builder import BuildWorker
from workers.poller import Poller

logger = get_logger(__name__)

_shutdown_event = threading.Event()


def _signal_handler(signum, frame):
    logger.info(f"Received signal {signum}, initiating shutdown")
    _shutdown_event.set()


def run_poller():
    try:
        Poller().run_forever()
    except Exception as e:
        logger.exception(f"Poller crashed: {e}")
        _shutdown_event.set()


def run_builder():
    try:
        BuildWorker().run_forever()
    except Exception as e:
        logger.exception(f"Builder crashed: {e}")
        _shutdown_event.set()


def main():
    settings.validate()
    logger.info("Starting Flutter APK build automation")

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    poller_thread = threading.Thread(target=run_poller, name="poller", daemon=True)
    builder_thread = threading.Thread(target=run_builder, name="builder", daemon=True)

    poller_thread.start()
    builder_thread.start()

    logger.info("Both poller and builder are running. Press Ctrl+C to stop.")

    try:
        while not _shutdown_event.is_set():
            _shutdown_event.wait(1)
    except KeyboardInterrupt:
        pass

    logger.info("Shutdown complete")
    sys.exit(0)


if __name__ == "__main__":
    main()
