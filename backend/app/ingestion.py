
import hashlib
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from docx import Document as DocxDocument

from .storage import (
    add_documents,
    delete_documents_by_source,
    load_chunks,
    save_chunks
)

from .graph_store import add_graph_facts


SUPPORTED = {".pdf", ".docx",".txt",".md",".log",".csv"}


def calculate_file_hash(path: Path) -> str:
    """
    Generate SHA-256 hash of the file.
    """
    sha256 = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(block)

    return sha256.hexdigest()


def extract_text(path: Path) -> str:

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        reader = PdfReader(str(path))

        return "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )

    if suffix == ".docx":
        doc = DocxDocument(str(path))

        return "\n".join(
            paragraph.text
            for paragraph in doc.paragraphs
        )

    return path.read_text(
        encoding="utf-8",
        errors="ignore"
    )


def ingest_file(path: Path) -> int:

    if path.suffix.lower() not in SUPPORTED:
        raise ValueError(
            f"Unsupported file type: {path.suffix}"
        )

    # Step 1: Calculate file hash
    file_hash = calculate_file_hash(path)

    # Step 2: Check existing lexical records
    old = load_chunks()

    existing_records = [
        chunk for chunk in old
        if chunk.get("metadata", {}).get("source") == path.name
    ]

    # Step 3: Skip unchanged files
    if existing_records:
        existing_hashes = {
            chunk.get("metadata", {}).get("file_hash")
            for chunk in existing_records
        }

        if existing_hashes == {file_hash}:
            print(
                f"[SKIPPED] {path.name} is already indexed. "
                "No new embeddings generated."
            )

            return 0

    # Step 4: Extract document text
    text = extract_text(path).strip()

    if not text:
        raise ValueError(
            "No readable text found in this file."
        )

    # Step 5: Split into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=900,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    pieces = splitter.split_text(text)

    docs: List[Document] = []
    new_records = []
    vector_ids = []

    # Step 6: Prepare documents and metadata
    for index, piece in enumerate(pieces):

        chunk_id = f"{path.name}:{file_hash[:16]}:{index}"

        metadata = {
            "source": path.name,
            "chunk_id": chunk_id,
            "chunk_index": index,
            "file_hash": file_hash
        }

        docs.append(
            Document(
                page_content=piece,
                metadata=metadata
            )
        )

        vector_ids.append(chunk_id)

        new_records.append({
            "id": chunk_id,
            "text": piece,
            "metadata": metadata
        })

    # Step 7: Remove previous vectors for this document
    # This also cleans up vectors created by the older
    # ingestion implementation.
    delete_documents_by_source(path.name)

    # Step 8: Add new vectors to persistent ChromaDB
    add_documents(
        docs,
        ids=vector_ids
    )

    # Step 9: Update lexical index
    updated_chunks = [
        chunk for chunk in old
        if chunk.get("metadata", {}).get("source") != path.name
    ]

    updated_chunks.extend(new_records)

    save_chunks(updated_chunks)

    # Step 10: Update knowledge graph
    add_graph_facts(
        path.name,
        text[:18000]
    )

    print(
        f"[INDEXED] {path.name}: "
        f"{len(docs)} chunks added."
    )

    return len(docs)
