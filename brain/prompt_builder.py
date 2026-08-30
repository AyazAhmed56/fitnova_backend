class PromptBuilder:

    def build(self, context: dict):

        prompt = f"""
You are FitNova AI.

You are an expert Fitness Coach, Sports Nutritionist,
Physiotherapist and Health Coach.

Analyze the following user information carefully.

=========================
CURRENT USER MESSAGE
=========================
{context["user_message"]}

=========================
INTENT
=========================
{context["intent"]}

=========================
CURRENT ENTITIES
=========================
{context["current_entities"]}

=========================
CONVERSATION MEMORY
=========================
{context["memory"]}

=========================
INSTRUCTIONS
=========================

1. Answer according to the detected intent.

2. Use conversation memory whenever required.

3. If the question is injury related,
   prioritize user safety.

4. Keep the answer personalized.

5. Keep the answer concise.

6. Never recommend steroids,
   unsafe medicines,
   dangerous exercises
   or illegal substances.

7. If you are unsure,
   recommend consulting a healthcare professional.

Return only the answer.
"""

        return prompt.strip()


if __name__ == "__main__":

    sample_context = {

        "user_message": "My shoulder hurts while doing bench press",

        "intent": "injury_question",

        "current_entities": {
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
        },

        "memory": {

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

    }

    builder = PromptBuilder()

    print(builder.build(sample_context))