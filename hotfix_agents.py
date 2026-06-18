import os, re

agents = ['sentinel', 'chronicle', 'meridian', 'context', 'oracle', 'arbiter']
for agent in agents:
    file_path = f"agents/{agent}.py"
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Add a default fallback 'dummy_key' if the env variable is missing
    # so that the client instantiation doesn't immediately crash.
    content = content.replace('api_key=os.getenv("AZURE_OPENAI_API_KEY")', 'api_key=os.getenv("AZURE_OPENAI_API_KEY", "dummy_fallback_key")')

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
print("Hotfix applied.")
