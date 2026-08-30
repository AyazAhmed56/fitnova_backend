import joblib
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from ai.preprocessing import NLPPreprocessor


# Load dataset
data = pd.read_csv("ai/intent_dataset.csv")

# Initialize preprocessor
preprocessor = NLPPreprocessor()

# Clean all sentences
data["clean_text"] = data["text"].apply(preprocessor.clean_text)

# Features
X = data["clean_text"]

# Labels
y = data["intent"]

# Convert text into numbers
vectorizer = TfidfVectorizer()

X_vectorized = vectorizer.fit_transform(X)

# Train model
model = LogisticRegression(max_iter=1000)

model.fit(X_vectorized, y)

# Save model
joblib.dump(model, "ai/intent_model.pkl")

# Save vectorizer
joblib.dump(vectorizer, "ai/vectorizer.pkl")

print("\nModel trained successfully.")
print("Files saved:")
print("- ai/intent_model.pkl")
print("- ai/vectorizer.pkl")