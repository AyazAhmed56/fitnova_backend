from __future__ import annotations

import asyncio
import re
from typing import Any

from .models import (
    NutrientInfo,
    NutritionFood,
    NutritionFoodDetailsResponse,
    NutritionSearchResponse,
)
from .nutrient_map import (
    NUTRIENTS,
    SEARCH_TERMS,
    NutrientDefinition,
    normalize_query,
    resolve_nutrient,
)
from .supabase_repository import SupabaseRepository
from .usda_service import USDAService


NUTRIENT_TO_COLUMN: dict[str, str] = {
    "protein": "protein_g",
    "calcium": "calcium_mg",
    "iron": "iron_mg",
    "fiber": "fiber_g",
    "potassium": "potassium_mg",
    "magnesium": "magnesium_mg",
    "zinc": "zinc_mg",
    "vitamin_a": "vitamin_a_ug",
    "vitamin_c": "vitamin_c_mg",
    "vitamin_d": "vitamin_d_ug",
    "vitamin_b12": "vitamin_b12_ug",
    "folate": "folate_ug",
    "omega_3": "omega_3_g",
    "healthy_fats": "fat_g",
    "carbohydrates": "carbohydrates_g",
}

USDA_NUTRIENT_ALIASES: dict[str, set[str]] = {
    "protein": {"protein"},
    "calcium": {"calcium"},
    "iron": {"iron"},
    "fiber": {"fiber", "dietary fiber"},
    "potassium": {"potassium"},
    "magnesium": {"magnesium"},
    "zinc": {"zinc"},
    "vitamin_a": {
        "vitamin a", "retinol", "retinol activity equivalents"
    },
    "vitamin_c": {"vitamin c", "ascorbic acid"},
    "vitamin_d": {
        "vitamin d", "vitamin d2", "vitamin d3"
    },
    "vitamin_b12": {"vitamin b-12", "vitamin b12", "vitamin b 12"},
    "folate": {
        "folate", "folic acid", "folate, total"
    },
    "omega_3": {
        "fatty acids, total n-3", "alpha-linolenic acid",
        "18:3 n-3", "epa", "dha"
    },
}


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_name(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value


# USDA contains many technically valid records that are not useful
# as everyday food recommendations (for example baking powder,
# additives, salts, and supplements). These should not appear in
# FitNova's nutrient-rich food list.
GENERIC_EXCLUDED_TERMS = (
    "baking powder",
    "baking soda",
    "leavening agent",
    "food additive",
    "food coloring",
    "food colour",
    "flavoring",
    "flavor enhancer",
    "flavouring",
    "thickener",
    "preservative",
    "stabilizer",
    "emulsifier",
    "sweetener",
    "salt substitute",
    "calcium carbonate",
    "calcium citrate",
    "calcium phosphate",
    "calcium sulfate",
    "calcium lactate",
    "calcium gluconate",
    "supplement",
    "protein powder",
    "vitamin supplement",
    "mineral supplement",
)


PREFERRED_FOOD_TERMS: dict[str, tuple[str, ...]] = {
    "calcium": (
        "milk", "yogurt", "cheese", "paneer", "ragi",
        "sesame", "tofu", "soy", "spinach", "sardine",
    ),
    "protein": (
        "chicken", "egg", "fish", "paneer", "milk",
        "lentil", "chickpea", "soy", "tofu", "yogurt",
    ),
    "iron": (
        "spinach", "lentil", "chickpea", "bean",
        "sesame", "pumpkin seed", "tofu", "beef",
    ),
    "fiber": (
        "oat", "lentil", "bean", "chickpea",
        "apple", "pear", "guava", "chia", "flax",
    ),
    "potassium": (
        "banana", "potato", "spinach", "avocado",
        "tomato", "bean", "yogurt", "coconut",
    ),
    "magnesium": (
        "almond", "cashew", "pumpkin seed",
        "spinach", "bean", "oat",
    ),
    "zinc": (
        "pumpkin seed", "sesame", "chickpea",
        "lentil", "egg", "milk", "cashew",
    ),
    "vitamin_a": (
        "carrot", "spinach", "sweet potato",
        "pumpkin", "mango", "egg", "milk",
    ),
    "vitamin_c": (
        "guava", "amla", "orange", "lemon",
        "kiwi", "bell pepper", "tomato", "broccoli",
    ),
    "vitamin_d": (
        "milk", "egg", "salmon", "sardine",
        "mushroom", "yogurt",
    ),
    "vitamin_b12": (
        "milk", "egg", "yogurt", "cheese",
        "chicken", "fish", "salmon",
    ),
    "folate": (
        "spinach", "lentil", "chickpea",
        "bean", "avocado", "asparagus", "broccoli",
    ),
    "omega_3": (
        "salmon", "sardine", "mackerel", "flax",
        "chia", "walnut",
    ),
    "healthy_fats": (
        "avocado", "almond", "walnut", "peanut",
        "olive", "chia", "flax",
    ),
    "carbohydrates": (
        "rice", "oat", "potato", "sweet potato",
        "banana", "bread", "whole wheat", "quinoa",
    ),
}


def _is_useful_food(name: str) -> bool:
    normalized = _normalize_name(name)

    if not normalized:
        return False

    return not any(
        term in normalized
        for term in GENERIC_EXCLUDED_TERMS
    )


def _food_relevance_score(
    name: str,
    nutrient: NutrientDefinition,
) -> float:
    normalized = _normalize_name(name)

    if not _is_useful_food(normalized):
        return -100000.0

    terms = PREFERRED_FOOD_TERMS.get(nutrient.key, ())

    # A positive relevance score is used only to prefer recognizable
    # food sources. The nutrient amount remains part of the final score.
    score = 0.0

    for index, term in enumerate(terms):
        if term in normalized:
            score += 1000.0 - (index * 25.0)

    # Prefer simple food names over highly processed/compound records.
    word_count = len(normalized.split())

    if word_count <= 6:
        score += 50.0
    elif word_count > 15:
        score -= 100.0

    return score


def _nutrient_value_from_search_food(
    food: dict[str, Any],
    nutrient: NutrientDefinition,
) -> float | None:
    wanted = USDA_NUTRIENT_ALIASES.get(nutrient.key, set())
    values: list[float] = []

    for item in food.get("foodNutrients", []) or []:
        name = str(item.get("nutrientName", "")).lower().strip()
        if name in wanted:
            number = _safe_float(item.get("value"))
            if number is not None:
                values.append(number)

    if not values:
        # Fallback fuzzy match, useful when USDA changes the exact
        # nutrient label.
        for item in food.get("foodNutrients", []) or []:
            name = str(item.get("nutrientName", "")).lower().strip()
            if any(alias in name for alias in wanted):
                number = _safe_float(item.get("value"))
                if number is not None:
                    values.append(number)

    if not values:
        return None

    if nutrient.key == "omega_3":
        # For omega-3, prefer the first matching total n-3 value.
        return values[0]

    return max(values)


def _extract_basic_nutrients(food: dict[str, Any]) -> dict[str, float | None]:
    result: dict[str, float | None] = {
        "calories": None,
        "protein_g": None,
        "carbohydrates_g": None,
        "fat_g": None,
        "fiber_g": None,
        "calcium_mg": None,
        "iron_mg": None,
        "magnesium_mg": None,
        "potassium_mg": None,
        "zinc_mg": None,
        "vitamin_a_ug": None,
        "vitamin_c_mg": None,
        "vitamin_d_ug": None,
        "vitamin_b12_ug": None,
        "folate_ug": None,
        "omega_3_g": None,
    }

    nutrient_map = {
        "energy": "calories",
        "energy (atwater general factor)": "calories",
        "protein": "protein_g",
        "carbohydrate, by difference": "carbohydrates_g",
        "total lipid (fat)": "fat_g",
        "fiber, total dietary": "fiber_g",
        "dietary fiber": "fiber_g",
        "calcium, ca": "calcium_mg",
        "calcium": "calcium_mg",
        "iron, fe": "iron_mg",
        "iron": "iron_mg",
        "magnesium, mg": "magnesium_mg",
        "magnesium": "magnesium_mg",
        "potassium, k": "potassium_mg",
        "potassium": "potassium_mg",
        "zinc, zn": "zinc_mg",
        "zinc": "zinc_mg",
        "vitamin a, rae": "vitamin_a_ug",
        "vitamin c, total ascorbic acid": "vitamin_c_mg",
        "vitamin c": "vitamin_c_mg",
        "vitamin d (d2 + d3)": "vitamin_d_ug",
        "vitamin d": "vitamin_d_ug",
        "vitamin b-12": "vitamin_b12_ug",
        "vitamin b12": "vitamin_b12_ug",
        "folate, total": "folate_ug",
        "folate": "folate_ug",
    }

    for item in food.get("foodNutrients", []) or []:
        name = str(item.get("nutrientName", "")).lower().strip()
        target = nutrient_map.get(name)

        if target is None:
            continue

        value = _safe_float(item.get("value"))
        if value is not None:
            result[target] = value

    # Total n-3 fatty acids / omega-3 is represented under several
    # USDA labels. Store the first available value.
    omega3_names = {
        "fatty acids, total n-3",
        "alpha-linolenic acid",
        "18:3 n-3",
    }
    for item in food.get("foodNutrients", []) or []:
        name = str(item.get("nutrientName", "")).lower().strip()
        if name in omega3_names:
            value = _safe_float(item.get("value"))
            if value is not None:
                result["omega_3_g"] = value
                break

    return result


class NutritionService:
    def __init__(self) -> None:
        self.usda = USDAService()
        self.db = SupabaseRepository()

    async def get_suggestions(self) -> list[dict[str, str]]:
        # Database can be extended without changing Flutter.
        try:
            rows = await self.db.select(
                "nutrition_targets",
                [
                    ("select", "key,display_name,unit"),
                    ("is_active", "eq.true"),
                    ("order", "sort_order.asc"),
                ],
            )
            if rows:
                return [
                    {
                        "key": str(row["key"]),
                        "display_name": str(row["display_name"]),
                        "unit": str(row["unit"]),
                    }
                    for row in rows
                ]
        except Exception:
            pass

        return [
            {
                "key": n.key,
                "display_name": n.display_name,
                "unit": n.unit,
            }
            for n in NUTRIENTS
        ]

    async def search(
        self,
        query: str,
        limit: int = 20,
    ) -> NutritionSearchResponse:
        query = query.strip()

        if not query:
            raise ValueError("Search query cannot be empty.")

        nutrient = resolve_nutrient(query)
        if nutrient is None:
            raise ValueError(
                "Please search for a supported nutrient such as "
                "calcium, protein, iron, fiber, potassium or vitamin C."
            )

        limit = min(max(limit, 1), 50)

        # IMPORTANT: do not rank the entire 13k+ food table by nutrient
        # amount. That makes ingredients/additives such as baking powder
        # outrank normal foods. Search the nutrient's preferred food terms
        # directly first.
        cached = await self._search_preferred_cached_foods(
            nutrient,
            candidate_limit=max(limit * 5, 100),
        )

        # Use the broad nutrient cache only as a fallback.
        if len(cached) < limit:
            fallback = await self._search_cached_foods(
                nutrient,
                candidate_limit=500,
            )

            existing_names = {item.normalized_name for item in cached}
            for item in fallback:
                if item.normalized_name not in existing_names:
                    cached.append(item)
                    existing_names.add(item.normalized_name)

        # USDA is searched using actual food names, never just
        # "calcium", "iron", etc. This avoids generic ingredient results.
        usda_foods: list[dict[str, Any]] = []

        if len(cached) < limit:
            search_queries = list(
                SEARCH_TERMS.get(nutrient.key, ())
            )

            seen_queries: set[str] = set()

            for search_query in search_queries:
                normalized_query = normalize_query(search_query)
                if normalized_query in seen_queries:
                    continue

                seen_queries.add(normalized_query)

                try:
                    results = await self.usda.search(
                        search_query,
                        page_size=50,
                    )
                    usda_foods.extend(results)
                except RuntimeError:
                    # Cached results remain usable if USDA is unavailable.
                    break

                if len(usda_foods) >= 300:
                    break

        converted = self._convert_usda_foods(
            usda_foods,
            nutrient,
        )

        merged: dict[str, NutritionFood] = {}

        for item in cached:
            if _is_useful_food(item.name):
                merged[item.normalized_name] = item

        for item in converted:
            if not _is_useful_food(item.name):
                continue

            existing = merged.get(item.normalized_name)
            if existing is None:
                merged[item.normalized_name] = item
            else:
                old_value = existing.nutrient_value or 0.0
                new_value = item.nutrient_value or 0.0
                if new_value > old_value:
                    merged[item.normalized_name] = item

        foods = [
            item
            for item in merged.values()
            if _is_useful_food(item.name)
            and (item.nutrient_value or 0.0) >= nutrient.min_value
        ]

        # Preferred recognizable foods come first. Nutrient amount is the
        # secondary ranking factor, so additives cannot dominate the list.
        foods.sort(
            key=lambda item: (
                _food_relevance_score(item.name, nutrient),
                item.nutrient_value or 0.0,
            ),
            reverse=True,
        )

        foods = foods[:limit]

        if converted:
            await self._cache_foods(converted)

        return NutritionSearchResponse(
            query=query,
            nutrient=NutrientInfo(
                key=nutrient.key,
                name=nutrient.display_name,
                unit=nutrient.unit,
            ),
            foods=foods,
            total=len(foods),
        )

    async def get_food(
        self,
        food_id: str,
    ) -> NutritionFoodDetailsResponse:
        rows = await self.db.select(
            "nutrition_foods",
            [
                ("select", "*"),
                ("id", f"eq.{food_id}"),
                ("limit", "1"),
            ],
        )

        if not rows:
            raise ValueError("Nutrition food was not found.")

        food = self._food_from_row(rows[0])

        return NutritionFoodDetailsResponse(food=food)

    
    async def _search_preferred_cached_foods(
        self,
        nutrient: NutrientDefinition,
        candidate_limit: int = 100,
    ) -> list[NutritionFood]:
        column = NUTRIENT_TO_COLUMN.get(nutrient.key)
        if not column:
            return []

        terms = SEARCH_TERMS.get(nutrient.key, ())
        results: dict[str, NutritionFood] = {}

        # Search Supabase by actual food terms. This is the key fix:
        # we no longer ask Supabase for the globally highest calcium rows.
        for term in terms:
            try:
                rows = await self.db.select(
                    "nutrition_foods",
                    [
                        ("select", "*"),
                        ("food_type", "eq.raw"),
                        (column, "not.is.null"),
                        ("normalized_name", f"ilike.*{term}*"),
                        ("order", f"{column}.desc"),
                        ("limit", "50"),
                    ],
                )
            except RuntimeError:
                continue

            for row in rows:
                name = str(row.get("name") or "").strip()
                if not name or not _is_useful_food(name):
                    continue

                food = self._food_from_row(
                    row,
                    nutrient=nutrient,
                )

                if food.nutrient_value is None:
                    continue
                if food.nutrient_value < nutrient.min_value:
                    continue

                key = food.normalized_name
                existing = results.get(key)
                if existing is None or (
                    food.nutrient_value > (existing.nutrient_value or 0.0)
                ):
                    results[key] = food

        foods = list(results.values())
        foods.sort(
            key=lambda item: (
                _food_relevance_score(item.name, nutrient),
                item.nutrient_value or 0.0,
            ),
            reverse=True,
        )

        return foods[:candidate_limit]

    async def _search_cached_foods(
        self,
        nutrient: NutrientDefinition,
        candidate_limit: int = 100,
    ) -> list[NutritionFood]:
        column = NUTRIENT_TO_COLUMN.get(nutrient.key)
        if not column:
            return []

        rows = await self.db.select(
            "nutrition_foods",
            [
                ("select", "*"),
                ("food_type", "eq.raw"),
                (column, "not.is.null"),
                ("order", f"{column}.desc"),
                ("limit", str(min(max(candidate_limit, 100), 1000))),
            ],
        )

        candidates: list[NutritionFood] = []

        for row in rows:
            name = str(row.get("name") or "").strip()
            if not name or not _is_useful_food(name):
                continue

            food = self._food_from_row(
                row,
                nutrient=nutrient,
            )

            if food.nutrient_value is None:
                continue
            if food.nutrient_value < nutrient.min_value:
                continue

            candidates.append(food)

        candidates.sort(
            key=lambda item: (
                _food_relevance_score(item.name, nutrient),
                item.nutrient_value or 0.0,
            ),
            reverse=True,
        )

        return candidates[:candidate_limit]

    def _convert_usda_foods(
        self,
        foods: list[dict[str, Any]],
        nutrient: NutrientDefinition,
    ) -> list[NutritionFood]:
        output: list[NutritionFood] = []
        seen: set[str] = set()

        for food in foods:
            fdc_id = food.get("fdcId")
            name = str(food.get("description") or "").strip()

            if not fdc_id or not name:
                continue

            normalized = _normalize_name(name)
            if not normalized or normalized in seen:
                continue

            value = _nutrient_value_from_search_food(
                food,
                nutrient,
            )

            if value is None or value < nutrient.min_value:
                continue

            if not _is_useful_food(name):
                continue

            seen.add(normalized)

            basic = _extract_basic_nutrients(food)

            output.append(
                NutritionFood(
                    id=f"usda-{fdc_id}",
                    name=name,
                    normalized_name=normalized,
                    food_type="raw",
                    fdc_id=int(fdc_id),
                    data_type=food.get("dataType"),
                    serving_size=100,
                    serving_unit="g",
                    **basic,
                    source="USDA FoodData Central",
                    source_url=(
                        "https://fdc.nal.usda.gov/food-details/"
                        f"{fdc_id}/nutrients"
                    ),
                    nutrient_value=value,
                    nutrient_unit=nutrient.unit,
                )
            )

        return output

    async def _cache_foods(
        self,
        foods: list[NutritionFood],
    ) -> None:
        rows: list[dict[str, Any]] = []

        for food in foods:
            if food.fdc_id is None:
                continue

            rows.append(
                {
                    "name": food.name,
                    "normalized_name": food.normalized_name,
                    "fdc_id": food.fdc_id,
                    "data_type": food.data_type,
                    "food_type": "raw",
                    "serving_size": food.serving_size,
                    "serving_unit": food.serving_unit,
                    "calories": food.calories,
                    "protein_g": food.protein_g,
                    "carbohydrates_g": food.carbohydrates_g,
                    "fat_g": food.fat_g,
                    "fiber_g": food.fiber_g,
                    "calcium_mg": food.calcium_mg,
                    "iron_mg": food.iron_mg,
                    "magnesium_mg": food.magnesium_mg,
                    "potassium_mg": food.potassium_mg,
                    "zinc_mg": food.zinc_mg,
                    "vitamin_a_ug": food.vitamin_a_ug,
                    "vitamin_c_mg": food.vitamin_c_mg,
                    "vitamin_d_ug": food.vitamin_d_ug,
                    "vitamin_b12_ug": food.vitamin_b12_ug,
                    "folate_ug": food.folate_ug,
                    "omega_3_g": food.omega_3_g,
                    "source": "USDA FoodData Central",
                    "source_url": food.source_url,
                }
            )

        # nutrition_foods currently has no unique constraint on
        # fdc_id in the user's screenshot. Insert safely in chunks and
        # let duplicates be cleaned by the normalized name check below.
        for row in rows:
            existing = await self.db.select(
                "nutrition_foods",
                [
                    ("select", "id"),
                    ("normalized_name", f"eq.{row['normalized_name']}"),
                    ("limit", "1"),
                ],
            )

            if existing:
                continue

            try:
                await self.db.insert("nutrition_foods", [row])
            except RuntimeError:
                # A cache failure must never break the user's search.
                continue

    def _food_from_row(
        self,
        row: dict[str, Any],
        nutrient: NutrientDefinition | None = None,
    ) -> NutritionFood:
        value = None

        if nutrient:
            column = NUTRIENT_TO_COLUMN.get(nutrient.key)
            if column:
                value = _safe_float(row.get(column))

        return NutritionFood(
            id=str(row["id"]),
            name=str(row.get("name") or ""),
            normalized_name=str(row.get("normalized_name") or ""),
            food_type=str(row.get("food_type") or "raw"),
            fdc_id=(
                int(row["fdc_id"])
                if row.get("fdc_id") is not None
                else None
            ),
            data_type=row.get("data_type"),
            serving_size=_safe_float(row.get("serving_size")),
            serving_unit=row.get("serving_unit"),
            calories=_safe_float(row.get("calories")),
            protein_g=_safe_float(row.get("protein_g")),
            carbohydrates_g=_safe_float(row.get("carbohydrates_g")),
            fat_g=_safe_float(row.get("fat_g")),
            fiber_g=_safe_float(row.get("fiber_g")),
            calcium_mg=_safe_float(row.get("calcium_mg")),
            iron_mg=_safe_float(row.get("iron_mg")),
            magnesium_mg=_safe_float(row.get("magnesium_mg")),
            potassium_mg=_safe_float(row.get("potassium_mg")),
            zinc_mg=_safe_float(row.get("zinc_mg")),
            vitamin_a_ug=_safe_float(row.get("vitamin_a_ug")),
            vitamin_c_mg=_safe_float(row.get("vitamin_c_mg")),
            vitamin_d_ug=_safe_float(row.get("vitamin_d_ug")),
            vitamin_b12_ug=_safe_float(row.get("vitamin_b12_ug")),
            folate_ug=_safe_float(row.get("folate_ug")),
            omega_3_g=_safe_float(row.get("omega_3_g")),
            image_url=row.get("image_url"),
            source=str(row.get("source") or "USDA"),
            source_url=row.get("source_url"),
            nutrient_value=value,
            nutrient_unit=nutrient.unit if nutrient else None,
        )

    