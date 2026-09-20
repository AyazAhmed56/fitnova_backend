from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx

from .config import require_settings
from .supabase_repository import SupabaseRepository


FDC_LIST_URL = "https://api.nal.usda.gov/fdc/v1/foods/list"

# USDA supports up to 200 records per page.
PAGE_SIZE = 200

# Supabase REST batch size.
SUPABASE_BATCH_SIZE = 50

# USDA datasets we actually want.
DATA_TYPES = [
    "Foundation",
    "SR Legacy",
    "Survey (FNDDS)",
]


# USDA nutrient IDs used by FoodData Central.
#
# These are the standard nutrient IDs used in FDC.
NUTRIENT_IDS = {
    "calories": 1008,
    "protein_g": 1003,
    "fat_g": 1004,
    "carbohydrates_g": 1005,
    "fiber_g": 1079,
    "calcium_mg": 1087,
    "iron_mg": 1089,
    "magnesium_mg": 1090,
    "potassium_mg": 1092,
    "zinc_mg": 1095,
    "vitamin_a_ug": 1106,
    "vitamin_c_mg": 1162,
    "vitamin_d_ug": 1114,
    "vitamin_b12_ug": 1178,
}


class USDAFoodImporter:
    def __init__(self) -> None:
        settings = require_settings()

        self.api_key = settings["usda_api_key"]
        self.supabase = SupabaseRepository()

    async def import_all_foods(
        self,
        max_pages: int | None = None,
    ) -> None:
        print()
        print("=" * 60)
        print("       FITNOVA USDA FOOD IMPORT")
        print("=" * 60)

        print()
        print("Data types:")
        for data_type in DATA_TYPES:
            print(f"  - {data_type}")

        print()
        print(f"Page size: {PAGE_SIZE}")
        print(f"Supabase batch size: {SUPABASE_BATCH_SIZE}")

        total_fetched = 0
        total_uploaded = 0
        total_pages = 0

        seen_fdc_ids: set[int] = set()

        try:
            page_number = 1

            while True:
                if max_pages is not None and page_number > max_pages:
                    break

                print()
                print("-" * 60)
                print(f"USDA PAGE {page_number}")
                print("-" * 60)

                foods = await self._fetch_page(page_number)

                if not foods:
                    print("No more USDA foods.")
                    break

                total_pages += 1
                total_fetched += len(foods)

                print(
                    f"Foods received from USDA: "
                    f"{len(foods)}"
                )

                rows: list[dict[str, Any]] = []

                for food in foods:
                    row = self._convert_food(food)

                    if row is None:
                        continue

                    fdc_id = row["fdc_id"]

                    if fdc_id in seen_fdc_ids:
                        continue

                    seen_fdc_ids.add(fdc_id)

                    rows.append(row)

                print(
                    f"Valid unique foods: "
                    f"{len(rows)}"
                )

                if rows:
                    uploaded = await self._save_batches(rows)

                    total_uploaded += uploaded

                    print(
                        f"Uploaded this page: "
                        f"{uploaded}"
                    )

                # USDA list pagination.
                if len(foods) < PAGE_SIZE:
                    print(
                        "Last page reached "
                        "(less than page size)."
                    )
                    break

                page_number += 1

                # Avoid hammering USDA.
                await asyncio.sleep(0.25)

            print()
            print("=" * 60)
            print("       USDA IMPORT COMPLETED")
            print("=" * 60)

            print(f"Pages processed : {total_pages}")
            print(f"Foods fetched   : {total_fetched}")
            print(f"Foods uploaded  : {total_uploaded}")

            database_count = await self.get_database_count()

            print(
                f"Foods in Supabase: "
                f"{database_count}"
            )

            print("=" * 60)

        except Exception as e:
            print()
            print("=" * 60)
            print("       USDA IMPORT FAILED")
            print("=" * 60)

            print(f"Error: {e}")

            raise

    async def _fetch_page(
        self,
        page_number: int,
    ) -> list[dict[str, Any]]:
        payload = {
            "dataType": DATA_TYPES,
            "pageSize": PAGE_SIZE,
            "pageNumber": page_number,
            "sortBy": "fdcId",
            "sortOrder": "asc",
        }

        params = {
            "api_key": self.api_key,
        }

        max_attempts = 5

        for attempt in range(1, max_attempts + 1):

            try:
                async with httpx.AsyncClient(
                    timeout=60.0
                ) as client:

                    response = await client.post(
                        FDC_LIST_URL,
                        params=params,
                        json=payload,
                    )

                if response.status_code == 429:
                    if attempt == max_attempts:
                        raise RuntimeError(
                            "USDA API rate limit reached."
                        )

                    wait_seconds = attempt * 10

                    print(
                        "USDA rate limit reached. "
                        f"Waiting {wait_seconds}s..."
                    )

                    await asyncio.sleep(wait_seconds)

                    continue

                if response.status_code >= 400:
                    raise RuntimeError(
                        "USDA request failed "
                        f"({response.status_code}): "
                        f"{response.text[:500]}"
                    )

                data = response.json()

                if not isinstance(data, list):
                    raise RuntimeError(
                        "Unexpected USDA response."
                    )

                return data

            except (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.ConnectError,
            ) as e:

                if attempt == max_attempts:
                    raise

                wait_seconds = attempt * 5

                print(
                    f"USDA request failed: {e}"
                )

                print(
                    f"Retrying in {wait_seconds}s..."
                )

                await asyncio.sleep(wait_seconds)

        raise RuntimeError(
            "Unable to fetch USDA page."
        )

    def _convert_food(
        self,
        food: dict[str, Any],
    ) -> dict[str, Any] | None:

        fdc_id = food.get("fdcId")

        if fdc_id is None:
            return None

        try:
            fdc_id = int(fdc_id)
        except (TypeError, ValueError):
            return None

        name = (
            food.get("description")
            or ""
        ).strip()

        if not name:
            return None

        data_type = (
            food.get("dataType")
            or ""
        ).strip()

        nutrients = self._extract_nutrients(
            food.get("foodNutrients")
        )

        normalized_name = self._normalize_name(name)

        return {
            "name": name,
            "normalized_name": normalized_name,

            "fdc_id": fdc_id,

            "data_type": data_type,

            # USDA foods are displayed as food/raw items
            # in FitNova. FitNova recipes are stored separately.
            "food_type": "raw",

            "description": name,

            "category": None,

            "brand_name": None,

            # USDA nutrient values are generally represented
            # on a per-100g basis in the FDC nutrient data.
            "serving_size": 100,
            "serving_unit": "g",

            "calories": nutrients.get(
                "calories"
            ),

            "protein_g": nutrients.get(
                "protein_g"
            ),

            "carbohydrates_g": nutrients.get(
                "carbohydrates_g"
            ),

            "fat_g": nutrients.get(
                "fat_g"
            ),

            "fiber_g": nutrients.get(
                "fiber_g"
            ),

            "calcium_mg": nutrients.get(
                "calcium_mg"
            ),

            "iron_mg": nutrients.get(
                "iron_mg"
            ),

            "magnesium_mg": nutrients.get(
                "magnesium_mg"
            ),

            "potassium_mg": nutrients.get(
                "potassium_mg"
            ),

            "zinc_mg": nutrients.get(
                "zinc_mg"
            ),

            "vitamin_a_ug": nutrients.get(
                "vitamin_a_ug"
            ),

            "vitamin_c_mg": nutrients.get(
                "vitamin_c_mg"
            ),

            "vitamin_d_ug": nutrients.get(
                "vitamin_d_ug"
            ),

            "vitamin_b12_ug": nutrients.get(
                "vitamin_b12_ug"
            ),

            "source": "USDA",
        }

    def _extract_nutrients(
        self,
        nutrient_list: Any,
    ) -> dict[str, float]:

        result: dict[str, float] = {}

        if not isinstance(nutrient_list, list):
            return result

        id_to_column = {
            nutrient_id: column
            for column, nutrient_id
            in NUTRIENT_IDS.items()
        }

        for nutrient in nutrient_list:

            if not isinstance(nutrient, dict):
                continue

            nutrient_id = nutrient.get(
                "nutrientId"
            )

            if nutrient_id is None:
                continue

            try:
                nutrient_id = int(
                    nutrient_id
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            column = id_to_column.get(
                nutrient_id
            )

            if column is None:
                continue

            value = nutrient.get("value")

            if value is None:
                continue

            try:
                numeric_value = float(value)
            except (
                TypeError,
                ValueError,
            ):
                continue

            result[column] = numeric_value

        return result

    @staticmethod
    def _normalize_name(
        name: str,
    ) -> str:

        value = name.lower().strip()

        value = re.sub(
            r"[^a-z0-9\s]",
            " ",
            value,
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value

    async def _save_batches(
        self,
        rows: list[dict[str, Any]],
    ) -> int:

        total = 0

        for start in range(
            0,
            len(rows),
            SUPABASE_BATCH_SIZE,
        ):

            end = min(
                start + SUPABASE_BATCH_SIZE,
                len(rows),
            )

            batch = rows[start:end]

            print(
                f"Uploading batch "
                f"{start + 1}-{end}..."
            )

            await self.supabase.upsert(
                "nutrition_foods",
                batch,
                on_conflict="fdc_id",
            )

            total += len(batch)

            print(
                f"Batch uploaded: "
                f"{len(batch)}"
            )

        return total

    async def get_database_count(self) -> int:

        rows = await self.supabase.select(
            "nutrition_foods",
            [
                (
                    "select",
                    "id",
                ),
            ],
        )

        return len(rows)


async def main() -> None:
    importer = USDAFoodImporter()

    await importer.import_all_foods()


if __name__ == "__main__":
    asyncio.run(main())