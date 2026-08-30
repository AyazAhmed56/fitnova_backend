from copy import deepcopy


class ConversationMemory:

    def __init__(self):
        self.user_memories = {}

    def _create_user_memory(self):

        return {
            "intent": None,
            "entities": {
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
        }

    def update(self, user_id: str, intent: str, entities: dict):
        """
        Update memory for a specific user.
        """

        if user_id not in self.user_memories:
            self.user_memories[user_id] = self._create_user_memory()

        memory = self.user_memories[user_id]

        memory["intent"] = intent

        for category, values in entities.items():

            if category not in memory["entities"]:
                continue

            for value in values:

                if value not in memory["entities"][category]:
                    memory["entities"][category].append(value)

    def get_memory(self, user_id: str):

        if user_id not in self.user_memories:
            self.user_memories[user_id] = self._create_user_memory()

        return deepcopy(self.user_memories[user_id])

    def clear_user(self, user_id: str):

        if user_id in self.user_memories:
            del self.user_memories[user_id]

    def clear_all(self):

        self.user_memories.clear()


if __name__ == "__main__":

    memory = ConversationMemory()

    memory.update(
        user_id="user_1",
        intent="injury_question",
        entities={
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
    )

    memory.update(
        user_id="user_2",
        intent="diet_plan",
        entities={
            "body_parts": [],
            "symptoms": [],
            "foods": ["egg"],
            "nutrients": ["protein"],
            "exercises": [],
            "equipment": [],
            "goals": ["muscle_gain"],
            "skin": [],
            "hair": [],
            "time": []
        }
    )

    print("\nUser 1")
    print(memory.get_memory("user_1"))

    print("\nUser 2")
    print(memory.get_memory("user_2"))