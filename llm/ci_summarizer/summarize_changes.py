import os
import subprocess
from openai import OpenAI

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
client = OpenAI()

def get_git_diff() -> str:
    base = os.getenv("GITHUB_BASE_REF", "main")
    subprocess.run(["git", "fetch", "origin", base], check=False)
    diff = subprocess.check_output(
        ["git", "diff", f"origin/{base}...HEAD"], text=True
    )
    return diff[:12000]  # guardrail: avoid huge diffs

def summarize(diff_text: str) -> str:
    prompt = f"""
You are a senior backend engineer.

Summarize the following git diff for CI visibility.

Return markdown with:
- Summary
- Affected modules
- Risks / things to double-check
- Suggested tests

DIFF:
{diff_text}
"""
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You generate concise CI summaries."},
            {"role": "user", "content": prompt},
        ],
    )
    return resp.choices[0].message.content

if __name__ == "__main__":
    diff = get_git_diff()
    if not diff.strip():
        print("No meaningful diff found.")
    else:
        print("===== LLM CI SUMMARY =====")
        print(summarize(diff))
