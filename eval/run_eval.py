import re
import json
import os
import sys
from pathlib import Path
import codecs

# Fix utf-8 on Windows
sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

# Add codebase to path
ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT / "codebase"))

from app.chat import run_model_tool_loop, load_tool_declarations, to_openai_tools
from app.agent.providers import make_provider
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

def parse_golden_set(filepath):
    content = Path(filepath).read_text(encoding="utf-8")
    cases = []
    current_case = None
    for line in content.splitlines():
        if line.startswith("### Case "):
            case_match = re.search(r"Case (\d+)", line)
            if case_match:
                if current_case:
                    cases.append(current_case)
                current_case = {"case": case_match.group(1), "input": ""}
        elif current_case and line.startswith("| **Input** |"):
            input_match = re.search(r"\*\"(.*?)\"\*", line)
            if input_match:
                current_case["input"] = input_match.group(1)
            else:
                input_match = re.search(r"gửi: (.*)\|", line)
                if input_match:
                    text = input_match.group(1).strip()
                    if text.startswith('*"') and text.endswith('"*'):
                        text = text[2:-2]
                    elif text.startswith('*') and text.endswith('*'):
                        text = text[1:-1]
                    current_case["input"] = text
    if current_case:
        cases.append(current_case)
    return cases

def run_eval():
    golden_set_path = ROOT / "eval" / "golden_set.md"
    cases = parse_golden_set(golden_set_path)
    print(f"Found {len(cases)} test cases.")

    provider = make_provider("openai")
    system_prompt = (ROOT / "codebase" / "app" / "prompt" / "system_prompt.md").read_text(encoding="utf-8")
    tool_declarations = load_tool_declarations(ROOT / "codebase" / "app" / "prompt" / "tools.yaml")
    openai_tools = to_openai_tools(tool_declarations)

    results = []
    for c in cases:
        print(f"Running Case {c['case']}: {c['input'][:50]}...")
        # Simulate context injection from Discord Orchestrator
        injected_context = f"\n\n[SYSTEM CONTEXT]: The user interacting with you has user_id='student_123', group_id='group_01', and today's date is '2026-07-31'."
        
        messages = [
            {"role": "system", "content": system_prompt + injected_context},
            {"role": "user", "content": c["input"]}
        ]
        
        # We need to simulate the chat execution
        try:
            res = run_model_tool_loop(
                provider=provider,
                messages=messages,
                tools=openai_tools,
                model="gpt-4o-mini",
                max_tool_rounds=3
            )
            tools_called = [event.get("tool") for event in res.get("tool_events", [])]
            results.append({
                "case": c["case"],
                "input": c["input"],
                "assistant_text": res.get("assistant_text", ""),
                "tools_called": tools_called,
                "status": "success"
            })
        except Exception as e:
            print(f"Error on case {c['case']}: {e}")
            results.append({
                "case": c["case"],
                "input": c["input"],
                "error": str(e),
                "status": "error"
            })

    out_path = ROOT / "eval" / "eval_output.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nEvaluation completed. Results saved to {out_path}")

if __name__ == "__main__":
    run_eval()
