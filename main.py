import os
import sys
from dotenv import load_dotenv
from llm_client import LLMClient


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python main.py <input_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        sys.exit(1)

    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("Missing GROQ_API_KEY in .env")
        sys.exit(1)

    model = "llama-3.1-8b-instant"

    with open(input_file, "r", encoding="utf-8") as f:
        text = f.read()

    llm = LLMClient(api_key=api_key, model=model)
    summary = llm.summarize(text)

    print("\n=== SUMMARY ===\n")
    print(summary)


if __name__ == "__main__":
    main()
