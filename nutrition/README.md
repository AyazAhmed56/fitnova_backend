# FitNova Macro Nutrition Search

## What this module does

The user searches for a nutrient, not a food.

Examples:

- calcium -> calcium-rich foods
- protein -> protein-rich foods
- iron -> iron-rich foods
- fiber -> fiber-rich foods
- vitamin C -> vitamin-C foods

USDA FoodData Central is used as the nutrition source. FitNova recipes
are stored separately in Supabase.

## Backend environment

Add these variables to `fitnova_backend/.env`:

```env
USDA_API_KEY=YOUR_DATA_GOV_KEY
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVER_ONLY_SERVICE_ROLE_KEY
```

Never expose `SUPABASE_SERVICE_ROLE_KEY` or `USDA_API_KEY` in Flutter.

## Install

Add to `requirements.txt`:

```txt
httpx>=0.27,<1
python-dotenv>=1.0,<2
pydantic>=2,<3
fastapi>=0.110,<1
uvicorn[standard]>=0.30,<1
```

If these packages are already present, do not duplicate them.

## Register the router

In your existing `main.py`:

```python
from nutrition.router import router as nutrition_router

app.include_router(nutrition_router)
```

Do not replace your existing AI routes. Just add these two lines.

## Test

Start FastAPI:

```bash
uvicorn main:app --reload
```

Then test:

```text
GET http://127.0.0.1:8000/nutrition/suggestions
GET http://127.0.0.1:8000/nutrition/search?query=calcium
GET http://127.0.0.1:8000/nutrition/search?query=protein
GET http://127.0.0.1:8000/nutrition/search?query=iron
```

The response contains separate `foods` and `recipes`.

## Important

The API key is server-side only.

Flutter calls your FastAPI backend, never USDA directly.
