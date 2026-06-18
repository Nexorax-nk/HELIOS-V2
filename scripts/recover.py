import json
from pathlib import Path
import re

transcript_path = Path(r"C:\Users\navee\.gemini\antigravity-ide\brain\c137e6bf-7c94-40e6-a444-2a2186fc506f\.system_generated\logs\transcript.jsonl")

files_to_recover = [
    "c:/Users/navee/HELIOS/agents/models.py",
    "c:/Users/navee/HELIOS/agents/sentinel.py",
    "c:/Users/navee/HELIOS/agents/chronicle.py",
    "c:/Users/navee/HELIOS/agents/meridian.py",
    "c:/Users/navee/HELIOS/agents/context.py",
    "c:/Users/navee/HELIOS/agents/oracle.py",
    "c:/Users/navee/HELIOS/agents/arbiter.py",
]

file_contents = {f: None for f in files_to_recover}

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            step = json.loads(line)
        except:
            continue
            
        if "tool_calls" in step:
            for call in step["tool_calls"]:
                # If we used replace_file_content, we might be able to reconstruct it, but view_file gives full content
                pass
                
        if "content" in step and step["content"]:
            content = step["content"]
            # Look for view_file output format
            if "The following code has been modified to include a line number before every line" in content:
                for f_path in files_to_recover:
                    if f"File Path: `file:///{f_path}`" in content:
                        # Extract the content lines
                        lines = content.splitlines()
                        extracted = []
                        capture = False
                        for l in lines:
                            if l.startswith("The following code has been modified"):
                                capture = True
                                continue
                            if l.startswith("The above content shows the entire"):
                                capture = False
                                break
                            if capture:
                                # Remove line number "123: "
                                m = re.match(r"^\d+:\s?(.*)$", l)
                                if m:
                                    extracted.append(m.group(1))
                                else:
                                    extracted.append(l)
                        file_contents[f_path] = "\n".join(extracted)

for k, v in file_contents.items():
    if v:
        print(f"Recovered {k} ({len(v)} bytes)")
        out_path = Path(k)
        out_path.write_text(v, encoding='utf-8')
    else:
        print(f"Could not fully recover {k}")
