from copy import deepcopy


class ContextManager:

    def build_context(
        self,
        original_text: str,
        clean_text: str,
        intent: str,
        entities: dict,
        memory: dict
    ):
        """
        Build a request-specific context.

        This class does not store context internally.
        Every request gets its own context object.
        """

        return {
            "user_message": original_text,
            "clean_text": clean_text,
            "intent": intent,
            "current_entities": deepcopy(entities),
            "memory": deepcopy(memory)
        }


if __name__ == "__main__":

    manager = ContextManager()

    memory = {
        "intent": "injury_question",
        "entities": {
            "body_parts": ["shoulder"],
            "symptoms": ["pain"],
            "foods": [],
            "nutrients": [],
            "exercises": [],
            "equipment": [],
            "goals": [],
            "skin": [],
            "hair": [],
            "time": []
        }
    }

    entities = {
        "body_parts": [],
        "symptoms": [],
        "foods": [],
        "nutrients": [],
        "exercises": ["bench_press"],
        "equipment": [],
        "goals": [],
        "skin": [],
        "hair": [],
        "time": []
    }

    context = manager.build_context(
        original_text="Can I do bench press?",
        clean_text="bench press",
        intent="exercise_advice",
        entities=entities,
        memory=memory
    )

    from pprint import pprint

    pprint(context)