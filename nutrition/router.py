from fastapi import APIRouter, HTTPException, Query

from .models import (
    NutritionFoodDetailsResponse,
    NutritionRecipe,
    NutritionSearchResponse,
)
from .service import NutritionService


router = APIRouter(
    prefix="/nutrition",
    tags=["Nutrition Search"],
)


@router.get(
    "/search",
    response_model=NutritionSearchResponse,
)
async def search_nutrition(
    query: str = Query(
        ...,
        min_length=2,
        max_length=80,
        description=(
            "Nutrient search such as calcium, protein, iron, fiber."
        ),
    ),
    limit: int = Query(default=20, ge=1, le=50),
):
    try:
        service = NutritionService()
        return await service.search(query=query, limit=limit)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Nutrition search failed: {exc}",
        ) from exc


@router.get("/suggestions")
async def nutrition_suggestions():
    try:
        service = NutritionService()
        return await service.get_suggestions()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to load nutrition suggestions: {exc}",
        ) from exc


@router.get(
    "/food/{food_id}",
    response_model=NutritionFoodDetailsResponse,
)
async def nutrition_food(food_id: str):
    try:
        service = NutritionService()
        return await service.get_food(food_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to load food: {exc}",
        ) from exc


@router.get(
    "/recipe/{recipe_id}",
    response_model=NutritionRecipe,
)
async def nutrition_recipe(recipe_id: str):
    try:
        service = NutritionService()
        return await service.get_recipe(recipe_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to load recipe: {exc}",
        ) from exc
