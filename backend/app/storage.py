
import json
from typing import List, Dict, Optional
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from .config import CHROMA_DIR, EMBEDDING_MODEL, CHUNKS_PATH

_embeddings = None
_vectorstore = None


def get_embeddings():
    global _embeddings

    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

    return _embeddings


def get_vectorstore():
    global _vectorstore

    if _vectorstore is None:
        _vectorstore = Chroma(
            collection_name="opsgraph_documents",
            persist_directory=str(CHROMA_DIR),
            embedding_function=get_embeddings(),
        )

    return _vectorstore


def add_documents(
    documents: List[Document],
    ids: Optional[List[str]] = None
):
    if documents:
        get_vectorstore().add_documents(
            documents=documents,
            ids=ids
        )


def delete_documents_by_source(source: str):
    """
    Delete all vectors belonging to a particular source document.
    """
    get_vectorstore().delete(
        where={"source": source}
    )


def load_chunks() -> List[Dict]:
    if not CHUNKS_PATH.exists():
        return []

    try:
        return json.loads(
            CHUNKS_PATH.read_text(encoding="utf-8")
        )
    except Exception:
        return []


def save_chunks(chunks: List[Dict]):
    CHUNKS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    CHUNKS_PATH.write_text(
        json.dumps(
            chunks,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


def get_all_chunks():
    return load_chunks()
