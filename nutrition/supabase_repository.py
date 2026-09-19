from __future__ import annotations

from typing import Any

import httpx

from .config import require_settings


class SupabaseRepository:
    def __init__(self) -> None:
        settings = require_settings()
        self.base_url = settings["supabase_url"]
        self.headers = {
            "apikey": settings["supabase_service_role_key"],
            "Authorization": (
                f"Bearer {settings['supabase_service_role_key']}"
            ),
            "Content-Type": "application/json",
        }

    async def select(
        self,
        table: str,
        params: list[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        url = f"{self.base_url}/rest/v1/{table}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                url,
                headers=self.headers,
                params=params,
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Supabase SELECT failed ({response.status_code}): "
                f"{response.text[:500]}"
            )

        data = response.json()
        return data if isinstance(data, list) else []

    async def insert(
        self,
        table: str,
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not rows:
            return []

        url = f"{self.base_url}/rest/v1/{table}"
        headers = {**self.headers, "Prefer": "return=representation"}

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                url,
                headers=headers,
                json=rows,
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Supabase INSERT failed ({response.status_code}): "
                f"{response.text[:500]}"
            )

        data = response.json()
        return data if isinstance(data, list) else []

    async def upsert(
        self,
        table: str,
        rows: list[dict[str, Any]],
        on_conflict: str,
    ) -> list[dict[str, Any]]:
        if not rows:
            return []

        url = f"{self.base_url}/rest/v1/{table}"
        headers = {
            **self.headers,
            "Prefer": "resolution=merge-duplicates,return=representation",
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                url,
                headers=headers,
                params={"on_conflict": on_conflict},
                json=rows,
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Supabase UPSERT failed ({response.status_code}): "
                f"{response.text[:500]}"
            )

        data = response.json()
        return data if isinstance(data, list) else []
