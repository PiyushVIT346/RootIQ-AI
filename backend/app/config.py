import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()
UPLOAD_DIR = DATA_DIR / "uploads"
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", str(DATA_DIR / "chroma"))).resolve()
GRAPH_PATH = DATA_DIR / "knowledge_graph.json"
CHUNKS_PATH = DATA_DIR / "chunks.json"

MESH_API_KEY = os.getenv("MESH_API_KEY", "")
MESH_BASE_URL = os.getenv("MESH_BASE_URL", "https://api.meshapi.ai/v1")
MESH_MODEL = os.getenv("MESH_MODEL", "openai/gpt-4o")
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
TOP_K = int(os.getenv("TOP_K", "8"))
MAX_RETRIEVAL_RETRIES = int(os.getenv("MAX_RETRIEVAL_RETRIES", "1"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

for directory in (DATA_DIR, UPLOAD_DIR, CHROMA_DIR):
    directory.mkdir(parents=True, exist_ok=True)

RERANKER_MODEL = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
