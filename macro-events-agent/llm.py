from dotenv import load_dotenv
from openai import OpenAI
import os

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "mistralai/mistral-small-3.1-24b-instruct:free"

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=OPENROUTER_API_KEY,
)

def response(messages):
    print(messages)
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages
    )
    return response.choices[0].message.content
