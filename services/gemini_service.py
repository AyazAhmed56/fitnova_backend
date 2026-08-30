import os

from dotenv import load_dotenv
from google import genai

load_dotenv()


class GeminiService:

    def __init__(self):

        self.client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY")
        )

        self.model = "gemini-2.5-flash"

    def generate(self, prompt: str):

        try:

            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )

            return response.text.strip()

        except Exception as e:

            return f"Gemini Error: {e}"


if __name__ == "__main__":

    gemini = GeminiService()

    answer = gemini.generate(
        "Say hello in one sentence."
    )

    print(answer)