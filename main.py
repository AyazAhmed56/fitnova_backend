from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from ai_pipeline import AIPipeline


app = FastAPI(title="FitNova AI Coach API")


# Allow Flutter/frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Create pipeline once
pipeline = AIPipeline()


class ChatRequest(BaseModel):
    user_id: str
    message: str


@app.get("/")
def home():
    return {
        "message": "FitNova AI Coach API is running"
    }


@app.post("/api/ai-coach/chat")
def chat(request: ChatRequest):

    result = pipeline.process(
        user_id=request.user_id,
        user_message=request.message
    )

    return {
        "response": result["response"],
        "intent": result["intent"],
        "entities": result["entities"]
    }