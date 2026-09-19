import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@lru_cache(maxsize=1)
def get_settings() -> dict[str, str]:
    return {
        "usda_api_key": os.getenv("USDA_API_KEY", "").strip(),
        "supabase_url": os.getenv("SUPABASE_URL", "").strip().rstrip("/"),
        "supabase_service_role_key": os.getenv(
            "SUPABASE_SERVICE_ROLE_KEY", ""
        ).strip(),
    }


def require_settings() -> dict[str, str]:
    settings = get_settings()

    missing = []
    if not settings["usda_api_key"]:
        missing.append("USDA_API_KEY")
    if not settings["supabase_url"]:
        missing.append("SUPABASE_URL")
    if not settings["supabase_service_role_key"]:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")

    if missing:
        raise RuntimeError(
            "Missing backend environment variables: " + ", ".join(missing)
        )

    return settings
