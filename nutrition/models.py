from typing import Any, Optional

from pydantic import BaseModel, Field


class NutrientInfo(BaseModel):
    key: str
    name: str
    unit: str


class NutritionFood(BaseModel):
    id: str
    name: str
    normalized_name: str
    food_type: str = "raw"

    fdc_id: Optional[int] = None
    data_type: Optional[str] = None

    serving_size: Optional[float] = None
    serving_unit: Optional[str] = None

    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbohydrates_g: Optional[float] = None
    fat_g: Optional[float] = None
    fiber_g: Optional[float] = None

    calcium_mg: Optional[float] = None
    iron_mg: Optional[float] = None
    magnesium_mg: Optional[float] = None
    potassium_mg: Optional[float] = None
    zinc_mg: Optional[float] = None

    vitamin_a_ug: Optional[float] = None
    vitamin_c_mg: Optional[float] = None
    vitamin_d_ug: Optional[float] = None
    vitamin_b12_ug: Optional[float] = None
    folate_ug: Optional[float] = None
    omega_3_g: Optional[float] = None

    image_url: Optional[str] = None
    source: str = "USDA"
    source_url: Optional[str] = None

    nutrient_value: Optional[float] = None
    nutrient_unit: Optional[str] = None


class NutritionSearchResponse(BaseModel):
    query: str
    nutrient: NutrientInfo
    foods: list[NutritionFood]
    total: int


class NutritionSearchSuggestion(BaseModel):
    key: str
    display_name: str
    unit: str


class NutritionFoodDetailsResponse(BaseModel):
    food: NutritionFood
