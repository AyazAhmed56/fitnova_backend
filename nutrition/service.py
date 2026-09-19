from __future__ import annotations

import asyncio
import re
from typing import Any

from .models import (
    NutrientInfo,
    NutritionFood,
    NutritionFoodDetailsResponse,
    NutritionRecipe,
    NutritionSearchResponse,
    RecipeIngredient,
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

        # 1. First search FitNova's cached food records.
        cached = await self._search_cached_foods(nutrient, limit)

        # 2. If cache is insufficient, ask USDA.
        #    We first use the nutrient term, then fallback food terms.
        usda_foods: list[dict[str, Any]] = []

        search_queries = [nutrient.display_name]
        search_queries.extend(SEARCH_TERMS.get(nutrient.key, ())[:6])

        # Avoid unnecessary calls when cache already has enough data.
        if len(cached) < limit:
            seen_queries: set[str] = set()

            for search_query in search_queries:
                normalized = normalize_query(search_query)
                if normalized in seen_queries:
                    continue

                seen_queries.add(normalized)

                try:
                    results = await self.usda.search(
                        search_query,
                        page_size=50,
                    )
                    usda_foods.extend(results)
                except RuntimeError:
                    # Keep cached results available if USDA is temporarily
                    # unavailable or rate limited.
                    break

                if len(usda_foods) >= 150:
                    break

        converted = self._convert_usda_foods(
            usda_foods,
            nutrient,
        )

        # Merge cache + USDA results, keeping the best nutrient value
        # for duplicate names.
        merged: dict[str, NutritionFood] = {}

        for item in cached:
            merged[item.normalized_name] = item

        for item in converted:
            existing = merged.get(item.normalized_name)
            if existing is None:
                merged[item.normalized_name] = item
            else:
                old_value = existing.nutrient_value or 0
                new_value = item.nutrient_value or 0
                if new_value > old_value:
                    merged[item.normalized_name] = item

        foods = [
            item for item in merged.values()
            if (item.nutrient_value or 0) >= nutrient.min_value
        ]

        foods.sort(
            key=lambda item: item.nutrient_value or 0,
            reverse=True,
        )
        foods = foods[:limit]

        # Save newly obtained USDA foods.
        if converted:
            await self._cache_foods(converted)

        # Recipes are FitNova-managed and searched separately.
        recipes = await self._search_recipes(nutrient, limit)

        return NutritionSearchResponse(
            query=query,
            nutrient=NutrientInfo(
                key=nutrient.key,
                name=nutrient.display_name,
                unit=nutrient.unit,
            ),
            foods=foods,
            recipes=recipes,
            total=len(foods) + len(recipes),
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

    async def get_recipe(
        self,
        recipe_id: str,
    ) -> NutritionRecipe:
        rows = await self.db.select(
            "nutrition_recipes",
            [
                ("select", "*"),
                ("id", f"eq.{recipe_id}"),
                ("is_active", "eq.true"),
                ("limit", "1"),
            ],
        )

        if not rows:
            raise ValueError("Recipe was not found.")

        row = rows[0]

        ingredient_rows = await self.db.select(
            "nutrition_recipe_ingredients",
            [
                ("select", "id,ingredient_name,quantity,unit,sort_order"),
                ("recipe_id", f"eq.{recipe_id}"),
                ("order", "sort_order.asc"),
            ],
        )

        return self._recipe_from_row(row, ingredient_rows)

    async def _search_cached_foods(
        self,
        nutrient: NutrientDefinition,
        limit: int,
    ) -> list[NutritionFood]:
        column = NUTRIENT_TO_COLUMN.get(nutrient.key)

        if not column:
            return []

        # We intentionally use a broad read here because the table is
        # cached and limited by the backend. PostgREST supports ordering.
        rows = await self.db.select(
            "nutrition_foods",
            [
                ("select", "*"),
                ("food_type", "eq.raw"),
                (column, "not.is.null"),
                ("order", f"{column}.desc"),
                ("limit", str(min(limit, 50))),
            ],
        )

        return [
            self._food_from_row(
                row,
                nutrient=nutrient,
            )
            for row in rows
        ]

    async def _search_recipes(
        self,
        nutrient: NutrientDefinition,
        limit: int,
    ) -> list[NutritionRecipe]:
        # For recipes we use the nutrition columns available in the
        # recipe table. Nutrients not represented there simply return
        # no recipe rows.
        column_map = {
            "protein": "protein_g",
            "calcium": "calcium_mg",
            "iron": "iron_mg",
            "fiber": "fiber_g",
            "carbohydrates": "carbohydrates_g",
        }

        column = column_map.get(nutrient.key)
        if not column:
            return []

        rows = await self.db.select(
            "nutrition_recipes",
            [
                (
                    "select",
                    "id,name,normalized_name,description,image_url,"
                    "calories,protein_g,carbohydrates_g,fat_g,fiber_g,"
                    "calcium_mg,iron_mg,instructions,source,source_url"
                ),
                ("is_active", "eq.true"),
                (column, "not.is.null"),
                ("order", f"{column}.desc"),
                ("limit", str(min(limit, 20))),
            ],
        )

        recipes: list[NutritionRecipe] = []

        for row in rows:
            value = _safe_float(row.get(column))
            if value is None or value < nutrient.min_value:
                continue

            ingredient_rows = await self.db.select(
                "nutrition_recipe_ingredients",
                [
                    (
                        "select",
                        "id,ingredient_name,quantity,unit,sort_order",
                    ),
                    ("recipe_id", f"eq.{row['id']}"),
                    ("order", "sort_order.asc"),
                ],
            )

            recipes.append(
                self._recipe_from_row(
                    row,
                    ingredient_rows,
                    nutrient_value=value,
                    nutrient_unit=nutrient.unit,
                )
            )

        return recipes

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

    def _recipe_from_row(
        self,
        row: dict[str, Any],
        ingredient_rows: list[dict[str, Any]],
        nutrient_value: float | None = None,
        nutrient_unit: str | None = None,
    ) -> NutritionRecipe:
        ingredients = [
            RecipeIngredient(
                id=str(item["id"]),
                ingredient_name=str(item["ingredient_name"]),
                quantity=_safe_float(item.get("quantity")),
                unit=item.get("unit"),
                sort_order=int(item.get("sort_order") or 0),
            )
            for item in ingredient_rows
        ]

        return NutritionRecipe(
            id=str(row["id"]),
            name=str(row["name"]),
            normalized_name=str(row["normalized_name"]),
            description=row.get("description"),
            image_url=row.get("image_url"),
            calories=_safe_float(row.get("calories")),
            protein_g=_safe_float(row.get("protein_g")),
            carbohydrates_g=_safe_float(row.get("carbohydrates_g")),
            fat_g=_safe_float(row.get("fat_g")),
            fiber_g=_safe_float(row.get("fiber_g")),
            calcium_mg=_safe_float(row.get("calcium_mg")),
            iron_mg=_safe_float(row.get("iron_mg")),
            instructions=row.get("instructions"),
            ingredients=ingredients,
            nutrient_value=nutrient_value,
            nutrient_unit=nutrient_unit,
        )
