import re
import string

from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize


class NLPPreprocessor:

    def __init__(self):

        self.stop_words = set(stopwords.words("english"))
        self.lemmatizer = WordNetLemmatizer()

        self.custom_words = {

            # Muscles
            "biceps": "bicep",
            "triceps": "tricep",
            "shoulders": "shoulder",
            "forearms": "forearm",
            "glutes": "glute",
            "quads": "quad",
            "hamstrings": "hamstring",
            "calves": "calf",
            "abs": "abdominal",
            "obliques": "oblique",

            # Joints
            "knees": "knee",
            "elbows": "elbow",
            "wrists": "wrist",
            "ankles": "ankle",

            # Nutrition
            "proteins": "protein",
            "calories": "calorie",
            "carbs": "carbohydrate",
            "fats": "fat",

            # Skin
            "pimples": "pimple",
            "acnes": "acne",

            # Hair
            "hairs": "hair"
        }

    def clean_text(self, text: str) -> str:

        # print("\n==============================")
        # print("Original:", text)

        # Lowercase
        text = text.lower()
        # print("Lowercase:", text)

        # Remove URLs
        text = re.sub(r"http\S+", "", text)

        # Remove numbers
        text = re.sub(r"\d+", "", text)

        # Remove punctuation
        text = text.translate(
            str.maketrans("", "", string.punctuation)
        )

        # print("Without punctuation:", text)

        # Tokenize
        words = word_tokenize(text)
        # print("Tokenized:", words)

        # Remove stop words
        words = [
            word
            for word in words
            if word not in self.stop_words
        ]

        # print("After stopword removal:", words)

        processed_words = []

        for word in words:

            word = self.lemmatizer.lemmatize(word)

            if word in self.custom_words:
                word = self.custom_words[word]

            processed_words.append(word)

        print("Final words:", processed_words)

        return " ".join(processed_words)

if __name__ == "__main__":

    preprocessor = NLPPreprocessor()

    samples = ["My biceps are sore after workout",]

    for sentence in samples:

        print("-" * 60)
        print("Original :", sentence)
        print("Processed:", preprocessor.clean_text(sentence))