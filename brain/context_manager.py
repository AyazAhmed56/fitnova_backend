from copy import deepcopy


class ContextManager:
    """Build a request-specific context without retaining user data."""

    def build_context(
        self,
        original_text: str,
        clean_text: str,
        intent: str,
        entities: dict,
        memory: dict,
        user_profile: dict | None = None,
    ) -> dict:
        """
        Build an isolated context for one AI Coach request.

        user_profile is loaded by the backend profile service. A new context
        is returned for every request to avoid cross-user profile leakage.
        """
        return {
            "user_message": original_text,
            "clean_text": clean_text,
            "intent": intent,
            "current_entities": deepcopy(entities or {}),
            "memory": deepcopy(memory or {}),
            "user_profile": deepcopy(user_profile or {}),
        }


if __name__ == "__main__":
    from pprint import pprint

    manager = ContextManager()
    context = manager.build_context(
        original_text="Can I do bench press?",
        clean_text="bench press",
        intent="exercise_advice",
        entities={
            "body_parts": [],
            "symptoms": [],
            "foods": [],
            "nutrients": [],
            "exercises": ["bench_press"],
            "equipment": [],
            "goals": [],
            "skin": [],
            "hair": [],
            "time": [],
        },
        memory={
            "intent": "injury_question",
            "entities": {"body_parts": ["shoulder"], "symptoms": ["pain"]},
        },
        user_profile={
            "goal": "Build Muscle",
            "workoutDays": 4,
            "equipmentPrefer": "Barbell, dumbbells",
        },
    )
    pprint(context)
