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


class AIPipeline:

    def __init__(self):

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

    def predict_intent(self, clean_text):

        vector = vectorizer.transform([clean_text])

        return model.predict(vector)[0]

    def process(self, user_id: str, user_message: str):

        # -----------------------------------
        # 1. Check memory expiration
        # -----------------------------------

        self.memory_manager.cleanup(
            user_id,
            self.memory
        )

        # -----------------------------------
        # 2. Preprocess
        # -----------------------------------

        clean_text = self.preprocessor.clean_text(
            user_message
        )

        # -----------------------------------
        # 3. Predict intent
        # -----------------------------------

        predicted_intent = self.predict_intent(
            clean_text
        )

        # -----------------------------------
        # 4. Extract entities
        # -----------------------------------

        entity_result = self.extractor.extract(
            clean_text
        )

        entities = entity_result["entities"]

        #5. Get existing memory
        memory = self.memory.get_memory(
            user_id
        )

        #6. Resolve conversational context
        resolved = self.context_resolver.resolve(
            current_intent=predicted_intent,
            current_entities=entities,
            memory = memory,
        )

        intent = resolved["intent"]

        # -----------------------------------
        # 5. Update user memory
        # -----------------------------------

        self.memory.update(
            user_id=user_id,
            intent=intent,
            entities=entities
        )

        self.memory_manager.touch(user_id)

        # -----------------------------------
        # 6. Get updated memory
        # -----------------------------------

        memory = self.memory.get_memory(
            user_id
        )

        # -----------------------------------
        # 8. Build context
        # -----------------------------------

        context = self.context_manager.build_context(
            original_text=user_message,
            clean_text=clean_text,
            intent=intent,
            entities=entities,
            memory=memory
        )

        # -----------------------------------
        # 9. Decision
        # -----------------------------------

        decision = self.decision_engine.decide(
            context
        )

        # -----------------------------------
        # 10. Generate response
        # -----------------------------------

        action = decision["action"]

        if action == "local_response":

            response = self.local_response.generate(
                intent
            )

        elif action == "gemini":

            prompt = self.prompt_builder.build(
                context
            )

            response = self.gemini.generate(
                prompt
            )

        else:

            response = (
                f"Route '{action}' is not implemented yet."
            )

        # -----------------------------------
        # 11. Return complete result
        # -----------------------------------

        return {

            "user_id": user_id,

            "user_message": user_message,

            "clean_text": clean_text,

            "intent": intent,

            "entities": entities,

            "memory": memory,

            "decision": decision,

            "response": response
        }


if __name__ == "__main__":

    pipeline = AIPipeline()

    user_id = "demo_user"

    print("=" * 60)
    print("FitNova AI Health Coach")
    print("Type 'exit' to quit.")
    print("=" * 60)

    while True:

        text = input("\nYou: ")

        if text.lower() == "exit":
            break

        result = pipeline.process(
            user_id=user_id,
            user_message=text
        )

        print("\nIntent:")
        print(result["intent"])

        print("\nEntities:")
        print(result["entities"])

        print("\nMemory:")
        print(result["memory"])

        print("\nDecision:")
        print(result["decision"])

        print("\nResponse:")
        print(result["response"])

# if __name__ == "__main__":

#     pipeline = AIPipeline()

#     result1 = pipeline.process(
#         user_id="user_1",
#         user_message="My shoulder hurts"
#     )

#     result2 = pipeline.process(
#         user_id="user_2",
#         user_message="I want a muscle gain diet"
#     )

#     print("\nUSER 1")
#     print(result1["memory"])

#     print("\nUSER 2")
#     print(result2["memory"])