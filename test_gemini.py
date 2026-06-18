import asyncio
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

async def main():
    client = genai.Client(api_key=os.environ.get("AZURE_OPENAI_API_KEY"))
    r = await client.aio.models.generate_content(
        model='gemini-2.5-flash',
        contents='hello'
    )
    print(r.text)

if __name__ == "__main__":
    asyncio.run(main())
