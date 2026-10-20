import logging

from ai.preprocessing import NLPPreprocessor
from ai.entity_extractor import EntityExtractor
from ai.predict_intent import model, vectorizer

from brain.conversation_memory import ConversationMemory
from brain.context_manager import ContextManager
from brain.decision_engine import DecisionEngine
from brain.local_response import LocalResponse
from brain.memory_manager import MemoryManager
from brain.prompt_builder import PromptBuilder
from brain.context_resolver import ContextResolver

from services.gemini_service import GeminiService
from services.profile_service import ProfileService


logger = logging.getLogger(__name__)


class AIPipeline:
    def __init__(self, profile_service=None):
        self.preprocessor = NLPPreprocessor()
        self.extractor = EntityExtractor()
        self.memory = ConversationMemory()
        self.memory_manager = MemoryManager()
        self.context_manager = ContextManager()
        self.context_resolver = ContextResolver()
        self.decision_engine = DecisionEngine()
        self.local_response = LocalResponse()
        self.prompt_builder = PromptBuilder()
        self.gemini = GeminiService()

        # Can be replaced with a mock/custom profile service in tests.
        self.profile_service = profile_service or ProfileService()

    def predict_intent(self, clean_text):
        vector = vectorizer.transform([clean_text])
        return model.predict(vector)[0]

    def _load_user_profile(self, user_id: str) -> dict:
        """Load only this user's saved profile; continue safely if unavailable."""
        try:
            profile = self.profile_service.get_profile(user_id)
            return profile if isinstance(profile, dict) else {}
        except Exception:
            logger.exception(
                "Unable to load FitNova profile for user_id=%s", user_id
            )
            return {}

    def process(self, user_id: str, user_message: str):
        # 1. Check memory expiration.
        self.memory_manager.cleanup(user_id, self.memory)

        # 2. Preprocess message.
        clean_text = self.preprocessor.clean_text(user_message)

        # 3. Predict intent.
        predicted_intent = self.predict_intent(clean_text)

        # 4. Extract entities.
        entity_result = self.extractor.extract(clean_text)
        entities = entity_result.get("entities", {})

        # 5. Read existing conversation memory.
        memory = self.memory.get_memory(user_id)

        # 6. Resolve references using conversation memory.
        resolved = self.context_resolver.resolve(
            current_intent=predicted_intent,
            current_entities=entities,
            memory=memory,
        )
        intent = resolved["intent"]

        # 7. Update memory for this user.
        self.memory.update(
            user_id=user_id,
            intent=intent,
            entities=entities,
        )
        self.memory_manager.touch(user_id)

        # 8. Load the saved profile belonging to this user.
        user_profile = self._load_user_profile(user_id)

        # 9. Get updated memory and construct request context.
        memory = self.memory.get_memory(user_id)
        context = self.context_manager.build_context(
            original_text=user_message,
            clean_text=clean_text,
            intent=intent,
            entities=entities,
            memory=memory,
            user_profile=user_profile,
        )

        # 10. Decide how to respond.
        decision = self.decision_engine.decide(context)
        action = decision["action"]

        # 11. Generate the response.
        if action == "local_response":
            response = self.local_response.generate(intent)
        elif action == "gemini":
            prompt = self.prompt_builder.build(context)
            response = self.gemini.generate(prompt)
        else:
            response = f"Route '{action}' is not implemented yet."

        # 12. Return the response and useful debugging context.
        return {
            "user_id": user_id,
            "user_message": user_message,
            "clean_text": clean_text,
            "intent": intent,
            "entities": entities,
            "memory": memory,
            "profile_loaded": bool(user_profile),
            "decision": decision,
            "response": response,
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pipeline = AIPipeline()

    # For local testing only. In production, use the authenticated
    # user's actual ID from your API authentication layer.
    user_id = input("Enter authenticated/demo user ID: ").strip()

    print("=" * 60)
    print("FitNova AI Health Coach")
    print("Type 'exit' to quit.")
    print("=" * 60)

    while True:
        message = input("\nYou: ").strip()
        if message.lower() == "exit":
            break
        if not message:
            continue

        result = pipeline.process(user_id=user_id, user_message=message)
        print("\nIntent:", result["intent"])
        print("Profile loaded:", result["profile_loaded"])
        print("\nResponse:\n", result["response"])
