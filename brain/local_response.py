import random


class LocalResponse:

    def __init__(self):

        self.responses = {

            "greeting": [
                "Hello! I'm FitNova AI Coach. How can I help you today?",
                "Hi! What can I help you with today?",
                "Welcome to FitNova! How can I assist you?"
            ],

            "goodbye": [
                "Goodbye! Stay healthy and keep training.",
                "See you again! Have a great day.",
                "Take care! Keep progressing toward your fitness goals."
            ],

            "thanks": [
                "You're welcome!",
                "Happy to help!",
                "Glad I could help."
            ]
        }

    def generate(self, intent):

        if intent not in self.responses:
            return "I'm not sure how to answer that."

        return random.choice(self.responses[intent])


if __name__ == "__main__":

    responder = LocalResponse()

    print(responder.generate("greeting"))
    print(responder.generate("thanks"))
    print(responder.generate("goodbye"))