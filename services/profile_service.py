"""Loads a user's saved onboarding profile from Supabase REST API.

Required backend environment variables:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY

Optional:
    FITNOVA_PROFILE_TABLE (default: profiles)
    FITNOVA_PROFILE_USER_ID_COLUMN (default: user_id)

Keep the service-role key on the backend only; never ship it in Flutter.
Adjust the table/column variables to match your Supabase schema.
"""

import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class ProfileService:
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.service_key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
            or os.getenv("SUPABASE_SERVICE_KEY", "")
        )
        self.table = os.getenv("FITNOVA_PROFILE_TABLE", "profiles")
        self.user_id_column = os.getenv(
            "FITNOVA_PROFILE_USER_ID_COLUMN", "user_id"
        )
        self.timeout = float(os.getenv("FITNOVA_PROFILE_TIMEOUT", "8"))

    def get_profile(self, user_id: str) -> dict:
        """Return the matching profile row, or an empty dict if unconfigured."""
        if not user_id:
            return {}

        if not self.supabase_url or not self.service_key:
            logger.warning(
                "Profile lookup skipped: SUPABASE_URL or "
                "SUPABASE_SERVICE_ROLE_KEY is not configured."
            )
            return {}

        # Quote identifiers and values to prevent malformed REST URLs.
        table = quote(self.table, safe="")
        column = quote(self.user_id_column, safe="")
        value = quote(str(user_id), safe="")
        url = (
            f"{self.supabase_url}/rest/v1/{table}"
            f"?{column}=eq.{value}&select=*"
        )

        request = Request(
            url,
            headers={
                "apikey": self.service_key,
                "Authorization": f"Bearer {self.service_key}",
                "Accept": "application/json",
            },
            method="GET",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Supabase profile query failed ({exc.code}): {details}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(
                f"Could not connect to Supabase: {exc.reason}"
            ) from exc

        try:
            rows = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Supabase returned invalid profile JSON.") from exc

        if not isinstance(rows, list) or not rows:
            return {}

        # A profile table should have one row per user. Use the first row.
        row = rows[0]
        return row if isinstance(row, dict) else {}
