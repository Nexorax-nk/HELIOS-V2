import json

lines = \"\"\"C:\Users\navee\HELIOS\cli\helios.py:214: DeprecationWarning...
SENTINEL API error: ...
CHRONICLE API error: ...
{
  "eval_id": "87892ac9",
  "arbiter": {
    "verdict": "BLOCK"
  }
}\"\"\".split('\n')

data = None
for line in reversed(lines):
    line = line.strip()
    if line.startswith('{') and line.endswith('}'):
        try:
            data = json.loads(line)
            break
        except:
            pass
            
print(data)
