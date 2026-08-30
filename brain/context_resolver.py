class ContextResolver:

    def resolve(self, current_intent: str, current_entities: dict, memory: dict):

        previous_intent = memory.get("intent")

        previous_entities = memory.get(
            "entities",
            {}
        )

        # ------------------------------------------------
        # 1. Check whether the current message has useful
        #    entities.
        # ------------------------------------------------

        has_current_entities = any(
            values
            for values in current_entities.values()
        )

        # ------------------------------------------------
        # 2. If the current message has no entities and
        #    previous conversation was meaningful,
        #    consider it a continuation.
        # ------------------------------------------------

        if not has_current_entities and previous_intent:

            continuation_intents = {
                "injury_question",
                "exercise_advice",
                "diet_plan",
                "workout_plan",
                "nutrition_advice",
                "skin_care",
                "hair_care",
                "progress_analysis"
            }

            if previous_intent in continuation_intents:

                return {
                    "intent": previous_intent,
                    "reason": "Current message appears to continue the previous conversation.",
                    "used_memory": True
                }

        # ------------------------------------------------
        # 3. Otherwise keep the ML prediction.
        # ------------------------------------------------

        return {
            "intent": current_intent,
            "reason": "Current intent is used.",
            "used_memory": False
        }


if __name__ == "__main__":

    resolver = ContextResolver()

    memory = {
        "intent": "injury_question",

        "entities": {
            "body_parts": ["shoulder"],
            "symptoms": ["hurt"],
            "foods": [],
            "nutrients": [],
            "exercises": ["bench_press"],
            "equipment": [],
            "goals": [],
            "skin": [],
            "hair": [],
            "time": []
        }
    }

    current_entities = {
        "body_parts": [],
        "symptoms": [],
        "foods": [],
        "nutrients": [],
        "exercises": [],
        "equipment": [],
        "goals": [],
        "skin": [],
        "hair": [],
        "time": []
    }

    result = resolver.resolve(
        current_intent="motivation",
        current_entities=current_entities,
        memory=memory
    )

    print(result)