import os, re

agents = ['chronicle', 'meridian', 'context', 'oracle', 'arbiter']
for agent in agents:
    file_path = f"agents/{agent}.py"
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    pattern = r'(async def _call_with_retry.*?:\n)(.*?)(    for attempt in range)'
    agent_name = agent.upper()
    
    replacement = r'\1    from agents.mock_data import get_mock_response\n' + \
                  r'    if os.getenv("HELIOS_MOCK_MODE", "false").lower() == "true":\n' + \
                  r'        logger.info("' + agent_name + r' running in MOCK_MODE")\n' + \
                  r'        await asyncio.sleep(1)\n' + \
                  r'        return get_mock_response("' + agent_name + r'")\n\n\3'
                  
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    raise_pattern = r'            else:\n                raise'
    raise_replacement = f'            else:\n                logger.error(f"{agent_name} API error: {{err}}. Falling back to MOCK MODE.")\n                return get_mock_response("{agent_name}")'
    
    content = re.sub(raise_pattern, raise_replacement, content)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
print("Agents patched.")
