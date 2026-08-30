class KnowledgeRouter:

    def __init__(self):

        self.routes = {

            "calculator": "calculator",

            "nutrition_db": "nutrition_db",

            "exercise_db": "exercise_db",

            "equipment_db": "equipment_db",

            "user_db": "user_db",

            "local_response": "local_response",

            "gemini": "gemini"

        }

    def route(self, decision):

        action = decision["action"]

        return self.routes.get(action, "gemini")


if __name__ == "__main__":

    router = KnowledgeRouter()

    tests = [

        {"action": "calculator"},

        {"action": "nutrition_db"},

        {"action": "exercise_db"},

        {"action": "gemini"},

        {"action": "local_response"}

    ]

    for test in tests:

        print(test["action"], "->", router.route(test))