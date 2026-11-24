from openai import OpenAI
from .config import MESH_API_KEY, MESH_BASE_URL, MESH_MODEL

_client = None

def get_client():
    global _client
    if not MESH_API_KEY:
        raise RuntimeError(
            "MESH_API_KEY is missing. Copy .env.example to .env and add your MeshAPI key."
        )
    if _client is None:
        _client = OpenAI(api_key=MESH_API_KEY, base_url=MESH_BASE_URL)
    return _client

def chat(system: str, user: str, temperature: float = 0.2) -> str:
    response = get_client().chat.completions.create(
        model=MESH_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content or ""

def chat_json(system: str, user: str) -> str:
    # JSON mode is not enabled because model support can vary by MeshAPI route.
    return chat(system + "\nReturn valid JSON only. Do not use markdown fences.", user, 0.1)
