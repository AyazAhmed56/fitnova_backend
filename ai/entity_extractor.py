class EntityExtractor:

    def __init__(self):

        self.multi_word_entities = {

            # Exercises
            "bench press": ("exercises", "bench_press"),
            "chest press": ("exercises", "chest_press"),
            "shoulder press": ("exercises", "shoulder_press"),
            "leg press": ("exercises", "leg_press"),
            "push up": ("exercises", "pushup"),
            "pull up": ("exercises", "pullup"),

            # Goals
            "weight loss": ("goals", "weight_loss"),
            "muscle gain": ("goals", "muscle_gain"),
            "fat loss": ("goals", "fat_loss"),
            "body weight": ("goals", "body_weight"),
            "calorie deficit": ("goals", "calorie_deficit"),

            # Symptoms
            "hair fall": ("symptoms", "hair_fall")
        }

        self.entity_map = {

            "body_parts": {
                "shoulder", "neck", "chest", "back",
                "bicep", "tricep", "forearm",
                "elbow", "wrist",
                "abdominal", "oblique",
                "glute", "quad", "hamstring",
                "knee", "calf", "ankle"
            },

            "symptoms": {
                "pain", "hurt", "hurts", "sore",
                "injury", "injured", "swelling",
                "stiff", "cramp", "weakness",
                "burning", "fatigue", "tired",
                "itching", "falling", "dry",
                "oily", "bleeding"
            },

            "foods": {
                "rice", "oats", "banana", "apple",
                "egg", "eggs", "milk", "paneer",
                "chicken", "fish", "bread",
                "curd", "dal", "roti",
                "almond", "peanut", "butter"
            },

            "nutrients": {
                "protein",
                "carbohydrate",
                "fat",
                "fiber",
                "calorie",
                "vitamin",
                "iron",
                "calcium",
                "zinc",
                "magnesium",
                "omega"
            },

            "exercises": {
                "workout",
                "gym",
                "bench",
                "press",
                "benchpress",
                "squat",
                "deadlift",
                "pushup",
                "pullup",
                "plank",
                "running",
                "walking",
                "cycling",
                "cardio",
                "yoga"
            },

            "equipment": {
                "dumbbell",
                "barbell",
                "machine",
                "cable",
                "treadmill",
                "band",
                "kettlebell"
            },

            "goals": {
                "weight",
                "loss",
                "gain",
                "muscle",
                "fat",
                "bulking",
                "cutting",
                "maintain"
            },

            "skin": {
                "skin",
                "acne",
                "pimple",
                "tan",
                "tanning",
                "glowing",
                "pigmentation"
            },

            "hair": {
                "hair",
                "scalp",
                "dandruff",
                "baldness"
            },

            "time": {
                "today",
                "tomorrow",
                "morning",
                "afternoon",
                "evening",
                "night",
                "before",
                "after"
            }
        }

    def extract(self, clean_text: str):

        words = clean_text.split()

        entities = {
            category: []
            for category in self.entity_map.keys()
        }

        used_indexes = set()

        # -------- Multi-word entities --------

        for i in range(len(words) - 1):

            phrase = f"{words[i]} {words[i + 1]}"

            if phrase in self.multi_word_entities:

                category, value = self.multi_word_entities[phrase]

                entities[category].append(value)

                used_indexes.update([i, i + 1])

        # -------- Single-word entities --------

        for index, word in enumerate(words):

            if index in used_indexes:
                continue

            for category, vocabulary in self.entity_map.items():

                if word in vocabulary:
                    entities[category].append(word)

        return {
            "clean_text": clean_text,
            "entities": entities
        }

if __name__ == "__main__":

    extractor = EntityExtractor()

    tests = [

        "shoulder hurt bench press",

        "eat chicken protein after workout",

        "hair falling protein",

        "knee pain squat",

        "acne dry skin",

        "banana milk oats",

        "running ankle pain",

        "weight loss",

        "muscle gain",

        "push up",

        "pull up",

        "leg press",

        "calorie deficit"

    ]

    for text in tests:

        print("=" * 70)
        print("Input :", text)

        result = extractor.extract(text)

        print("Output:")
        print(result)