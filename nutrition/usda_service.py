from __future__ import annotations

from typing import Any

import httpx

from .config import require_settings


FDC_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
FDC_DETAILS_URL = "https://api.nal.usda.gov/fdc/v1/food"


class USDAService:
    def __init__(self) -> None:
        settings = require_settings()
        self.api_key = settings["usda_api_key"]

    async def search(
        self,
        query: str,
        page_size: int = 50,
    ) -> list[dict[str, Any]]:
        payload = {
            "query": query,
            "pageSize": min(max(page_size, 1), 200),
            "pageNumber": 1,
        }

        params = {"api_key": self.api_key}

        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.post(
                FDC_SEARCH_URL,
                params=params,
                json=payload,
            )

        if response.status_code == 429:
            raise RuntimeError(
                "USDA FoodData Central rate limit reached. "
                "Try again later."
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"USDA search failed ({response.status_code}): "
                f"{response.text[:500]}"
            )

        data = response.json()
        foods = data.get("foods", [])
        return foods if isinstance(foods, list) else []

    async def details(self, fdc_id: int) -> dict[str, Any]:
        params = {"api_key": self.api_key}

        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.get(
                f"{FDC_DETAILS_URL}/{fdc_id}",
                params=params,
            )

        if response.status_code == 429:
            raise RuntimeError(
                "USDA FoodData Central rate limit reached. "
                "Try again later."
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"USDA details failed ({response.status_code}): "
                f"{response.text[:500]}"
            )

        return response.json()
