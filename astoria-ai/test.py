from fastapi import FastAPI
from dotenv import load_dotenv
import os
from openai import OpenAI

# Load the .env file
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# Create OpenAI client
client = OpenAI(api_key=api_key)

app = FastAPI()

@app.get("/test-openai")
async def test_openai():
    try:
        response = client.chat.completions.create(
            model="gpt-4-0613",
            messages=[
                {"role": "user", "content": "Say hello from GPT-4"}
            ]
        )
        return {
            "status": "success",
            "model": response.model,
            "response": response.choices[0].message.content
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
