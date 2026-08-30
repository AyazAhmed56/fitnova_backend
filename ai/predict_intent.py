import joblib

from ai.preprocessing import NLPPreprocessor

# Load trained model
model = joblib.load("ai/intent_model.pkl")

# Load vectorizer
vectorizer = joblib.load("ai/vectorizer.pkl")

# Initialize preprocessor
preprocessor = NLPPreprocessor()


def predict(user_input: str):

    cleaned = preprocessor.clean_text(user_input)

    vector = vectorizer.transform([cleaned])

    prediction = model.predict(vector)[0]

    return prediction


if __name__ == "__main__":

    print("=" * 50)
    print("FitNova AI Intent Predictor")
    print("Type 'exit' to quit.")
    print("=" * 50)

    while True:

        user_input = input("\nYou: ")

        if user_input.lower() == "exit":
            break

        print("\nIntent:", predict(user_input))