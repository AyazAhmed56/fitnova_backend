from brain.route_manager import RouteManager


class DecisionEngine:

    def __init__(self):

        self.route_manager = RouteManager()

    def decide(self, context: dict):

        intent = context.get("intent")

        route = self.route_manager.get_route(intent)

        return {
            "intent": intent,
            "action": route,
            "reason": f"Intent '{intent}' routed to '{route}'."
        }


if __name__ == "__main__":

    engine = DecisionEngine()

    tests = [
        "greeting",
        "bmi_calculation",
        "food_nutrition",
        "exercise_library",
        "diet_plan",
        "injury_question",
        "unknown_intent"
    ]

    for intent in tests:

        context = {
            "intent": intent
        }

        print(engine.decide(context))