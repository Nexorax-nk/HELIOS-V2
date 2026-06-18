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
                if call.get("name") == "default_api:write_to_file":
                    args = call.get("arguments", "{}")
                    try:
                        args_dict = json.loads(args) if isinstance(args, str) else args
                        if "TargetFile" in args_dict and "CodeContent" in args_dict:
                            files[args_dict["TargetFile"]] = args_dict["CodeContent"]
                    except:
                        pass
                elif call.get("name") == "default_api:replace_file_content":
                    args = call.get("arguments", "{}")
                    try:
                        args_dict = json.loads(args) if isinstance(args, str) else args
                        target = args_dict.get("TargetFile")
                        if target in files:
                            # Try to apply replacement
                            old = args_dict.get("TargetContent")
                            new = args_dict.get("ReplacementContent")
                            if old and new:
                                files[target] = files[target].replace(old, new)
                    except:
                        pass

for k, v in files.items():
    if "agents" in k and ".py" in k:
        print(f"Recovered {k} from tool_calls ({len(v)} bytes)")
        Path(k).write_text(v, encoding='utf-8')
