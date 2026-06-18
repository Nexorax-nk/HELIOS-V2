import json
from pathlib import Path

transcript_path = Path(r"C:\Users\navee\.gemini\antigravity-ide\brain\c137e6bf-7c94-40e6-a444-2a2186fc506f\.system_generated\logs\transcript.jsonl")

files = {}

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            step = json.loads(line)
        except:
            continue
            
        if "tool_calls" in step:
            for call in step["tool_calls"]:
                name = call.get("function", {}).get("name") or call.get("name")
                args = call.get("function", {}).get("arguments") or call.get("arguments", "{}")
                
                try:
                    args_dict = json.loads(args) if isinstance(args, str) else args
                except:
                    continue

                if name == "default_api:write_to_file" or name == "write_to_file":
                    target = args_dict.get("TargetFile")
                    code = args_dict.get("CodeContent")
                    if target and code and "agents" in target and ".py" in target:
                        files[target] = code
                        print(f"Found complete file {target}")
                elif name == "default_api:replace_file_content" or name == "replace_file_content":
                    target = args_dict.get("TargetFile")
                    if target in files:
                        old = args_dict.get("TargetContent")
                        new = args_dict.get("ReplacementContent")
                        if old and new:
                            files[target] = files[target].replace(old, new)
                            print(f"Applied replacement to {target}")

for k, v in files.items():
    if v:
        print(f"Recovered {k} from tool_calls ({len(v)} bytes)")
        Path(k).write_text(v, encoding='utf-8')
