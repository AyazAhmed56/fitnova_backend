class RouteManager:

    def __init__(self):

        self.routes = {

            # Local Responses
            "greeting": "local_response",
            "goodbye": "local_response",
            "thanks": "local_response",

            # Calculator
            "bmi_calculation": "calculator",
            "bmr_calculation": "calculator",
            "calorie_calculation": "calculator",
            "protein_requirement": "calculator",
            "water_requirement": "calculator",

            # Nutrition Database
            "food_nutrition": "nutrition_db",
            "macro_search": "nutrition_db",
            "food_substitution": "nutrition_db",

            # Exercise Library
            "exercise_library": "exercise_db",
            "exercise_details": "exercise_db",

            # Equipment Library
            "equipment_library": "equipment_db",

            # User Database
            "my_profile": "user_db",
            "today_meal": "user_db",
            "today_workout": "user_db",
            "my_progress": "user_db",

            # Gemini
            "diet_plan": "gemini",
            "workout_plan": "gemini",
            "injury_question": "gemini",
            "nutrition_advice": "gemini",
            "exercise_advice": "gemini",
            "skin_care": "gemini",
            "hair_care": "gemini",
            "motivation": "gemini",
            "progress_analysis": "gemini",
            "general_health": "gemini"
        }

    def get_route(self, intent: str):

        return self.routes.get(intent, "gemini")


if __name__ == "__main__":

    router = RouteManager()

    tests = [

        "greeting",
        "bmi_calculation",
        "food_nutrition",
        "exercise_library",
        "diet_plan",
        "today_meal",
        "injury_question",
        "unknown_intent"

    ]

    for intent in tests:

        print(f"{intent} -> {router.get_route(intent)}")