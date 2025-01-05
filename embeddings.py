import openai
from config import Config

async def generate_embedding(text: str):
    try:
        if not Config.openai_api_key:
            raise ValueError("OpenAI API key is not set in Config.")
        openai.api_key = Config.openai_api_key
        response = await openai.Embedding.acreate(model="text-embedding-ada-002", input=text)
        return response["data"][0]["embedding"]
    except Exception as e:
        return f"Error generating embeddings: {e}"
