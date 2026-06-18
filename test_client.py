import os
from google import genai
try:
    client = genai.Client(api_key=None)
    print("Success with None")
except Exception as e:
    print("Failed with None:", type(e))

try:
    client = genai.Client(api_key="dummy")
    print("Success with dummy")
except Exception as e:
    print("Failed with dummy:", type(e))
