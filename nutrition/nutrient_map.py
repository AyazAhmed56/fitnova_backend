import re
from dataclasses import dataclass


@dataclass(frozen=True)
class NutrientDefinition:
    key: str
    display_name: str
    unit: str
    aliases: tuple[str, ...]
    min_value: float


# Keep this mapping in code as a safe fallback. The database also
# contains the same nutrient dictionary.
NUTRIENTS = (
    NutrientDefinition(
        "protein", "Protein", "g",
        ("protein", "protein rich", "protein rich foods",
         "high protein", "protein foods"), 5.0
    ),
    NutrientDefinition(
        "calcium", "Calcium", "mg",
        ("calcium", "calcium rich", "calcium rich foods",
         "foods for calcium", "calcium foods"), 20.0
    ),
    NutrientDefinition(
        "iron", "Iron", "mg",
        ("iron", "iron rich", "iron rich foods",
         "foods for iron", "iron foods"), 1.0
    ),
    NutrientDefinition(
        "fiber", "Fiber", "g",
        ("fiber", "fibre", "high fiber", "high fibre",
         "fiber rich", "fiber rich foods"), 2.0
    ),
    NutrientDefinition(
        "potassium", "Potassium", "mg",
        ("potassium", "potassium rich", "potassium foods"), 50.0
    ),
    NutrientDefinition(
        "magnesium", "Magnesium", "mg",
        ("magnesium", "magnesium rich", "magnesium foods"), 20.0
    ),
    NutrientDefinition(
        "zinc", "Zinc", "mg",
        ("zinc", "zinc rich", "zinc foods"), 0.5
    ),
    NutrientDefinition(
        "vitamin_a", "Vitamin A", "µg",
        ("vitamin a", "vitamin a rich", "vitamin a foods"), 20.0
    ),
    NutrientDefinition(
        "vitamin_c", "Vitamin C", "mg",
        ("vitamin c", "vitamin c rich", "vitamin c foods"), 2.0
    ),
    NutrientDefinition(
        "vitamin_d", "Vitamin D", "µg",
        ("vitamin d", "vitamin d rich", "vitamin d foods"), 0.5
    ),
    NutrientDefinition(
        "vitamin_b12", "Vitamin B12", "µg",
        ("vitamin b12", "b12", "vitamin b 12", "b12 rich"), 0.1
    ),
    NutrientDefinition(
        "folate", "Folate", "µg",
        ("folate", "folic acid", "folate rich", "folate foods"), 10.0
    ),
    NutrientDefinition(
        "omega_3", "Omega-3", "g",
        ("omega 3", "omega-3", "omega3", "omega 3 rich",
         "omega-3 rich", "healthy omega 3"), 0.05
    ),
    NutrientDefinition(
        "healthy_fats", "Healthy Fats", "g",
        ("healthy fats", "healthy fat", "good fats",
         "healthy fat foods"), 2.0
    ),
    NutrientDefinition(
        "carbohydrates", "Carbohydrates", "g",
        ("carbohydrates", "carbs", "carb rich",
         "carbohydrate foods"), 10.0
    ),
)


def normalize_query(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\s\-]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value


def resolve_nutrient(query: str) -> NutrientDefinition | None:
    normalized = normalize_query(query)

    exact_matches = []
    for nutrient in NUTRIENTS:
        for alias in nutrient.aliases:
            if normalized == normalize_query(alias):
                exact_matches.append(nutrient)
                break

    if exact_matches:
        return exact_matches[0]

    # Support natural queries such as "foods high in calcium".
    for nutrient in NUTRIENTS:
        for alias in nutrient.aliases:
            alias_normalized = normalize_query(alias)
            if alias_normalized and alias_normalized in normalized:
                return nutrient

    return None


def suggestions() -> list[dict[str, str]]:
    return [
        {
            "key": item.key,
            "display_name": item.display_name,
            "unit": item.unit,
        }
        for item in NUTRIENTS
    ]


# Nutrient -> food search terms used as a fallback when USDA's
# component search does not return enough records. These are broad,
# ordinary foods rather than a hard-coded final ranking.
SEARCH_TERMS: dict[str, tuple[str, ...]] = {
    "calcium": (
        "milk", "yogurt", "cheese", "paneer", "ragi",
        "sesame", "tofu", "spinach"
    ),
    "protein": (
        "chicken", "egg", "fish", "paneer", "milk",
        "lentils", "chickpeas", "soybean", "tofu", "yogurt"
    ),
    "iron": (
        "spinach", "lentils", "chickpeas", "beans",
        "sesame", "pumpkin seeds", "tofu", "beef"
    ),
    "fiber": (
        "oats", "lentils", "beans", "chickpeas",
        "apple", "pear", "guava", "chia seeds", "flaxseed"
    ),
    "potassium": (
        "banana", "potato", "spinach", "avocado",
        "tomato", "beans", "yogurt", "coconut water"
    ),
    "magnesium": (
        "almonds", "cashews", "pumpkin seeds",
        "spinach", "dark chocolate", "beans", "oats"
    ),
    "zinc": (
        "pumpkin seeds", "sesame", "chickpeas",
        "lentils", "egg", "milk", "cashews"
    ),
    "vitamin_a": (
        "carrot", "spinach", "sweet potato",
        "pumpkin", "mango", "egg", "milk"
    ),
    "vitamin_c": (
        "guava", "amla", "orange", "lemon",
        "kiwi", "bell pepper", "tomato", "broccoli"
    ),
    "vitamin_d": (
        "milk", "egg", "salmon", "sardine",
        "mushroom", "yogurt"
    ),
    "vitamin_b12": (
        "milk", "egg", "yogurt", "cheese",
        "chicken", "fish", "salmon"
    ),
    "folate": (
        "spinach", "lentils", "chickpeas",
        "beans", "avocado", "asparagus", "broccoli"
    ),
    "omega_3": (
        "salmon", "sardine", "mackerel", "flaxseed",
        "chia seeds", "walnuts"
    ),
    "healthy_fats": (
        "avocado", "almonds", "walnuts", "peanuts",
        "olive oil", "chia seeds", "flaxseed"
    ),
    "carbohydrates": (
        "rice", "oats", "potato", "sweet potato",
        "banana", "bread", "whole wheat", "quinoa"
    ),
}
