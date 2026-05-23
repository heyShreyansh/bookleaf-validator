from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise EnvironmentError("GEMINI_API_KEY not set in .env")

client = genai.Client(api_key=GEMINI_API_KEY)

print("Available Gemini models:\n")

try:
    models = list(client.models.list())

    if not models:
        print("  No models returned — check your API key or quota.")
    else:
        for model in models:
            # Show name + supported actions if available
            actions = getattr(model, "supported_actions", None)
            actions_str = f"  →  {', '.join(actions)}" if actions else ""
            print(f"  {model.name}{actions_str}")

        print(f"\nTotal: {len(models)} models")

except Exception as e:
    print(f"Error listing models: {e}")