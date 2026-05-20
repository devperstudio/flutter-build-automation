
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    # API endpoints
    API_BASE_URL: str = os.getenv("API_BASE_URL", "").rstrip("/")
    BOT_API_KEY: str = os.getenv("BOT_API_KEY", "")
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))

    # Polling
    POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_QUEUE_NAME: str = os.getenv("REDIS_QUEUE_NAME", "apk_build_queue")
    REDIS_PROCESSING_SET: str = "apk_build_processing"

    # Flutter project
    PROJECT_PATH: str = os.getenv("PROJECT_PATH", "/home/builder/login_app")
    GIT_BRANCH: str = os.getenv("GIT_BRANCH", "main")

    # File paths to modify within the Flutter project
    DART_CONFIG_FILE: str = "lib/utils/constants.dart"
    KOTLIN_API_FILE: str = (
        "android/app/src/main/kotlin/com/example/login_app/api/JobApiService.kt"
    )

    # APK output
    APK_OUTPUT_DIR: str = os.getenv("APK_OUTPUT_DIR", "/home/builder/apk-outputs")
    FLUTTER_APK_RELATIVE_PATH: str = "build/app/outputs/flutter-apk/app-release.apk"

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR: str = os.getenv("LOG_DIR", str(BASE_DIR / "logs"))

    # API endpoint paths
    ENDPOINT_PENDING: str = "/apk-pending"
    ENDPOINT_COMPLETE: str = "/apk-complete"
    ENDPOINT_STATUS: str = "/apk-status"

    @classmethod
    def validate(cls) -> None:
        """Validate required settings are present. Raises ValueError if missing."""
        required = {
            "API_BASE_URL": cls.API_BASE_URL,
            "BOT_API_KEY": cls.BOT_API_KEY,
            "PROJECT_PATH": cls.PROJECT_PATH,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError(f"Missing required settings: {', '.join(missing)}")


settings = Settings()
