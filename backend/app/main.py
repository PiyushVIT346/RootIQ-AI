from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .config import UPLOAD_DIR, CORS_ORIGINS, MESH_API_KEY, MESH_MODEL
from .schemas import IncidentRequest, IngestResponse
from .ingestion import ingest_file
from .agents import investigate
from .storage import load_chunks

app = FastAPI(
    title="OpsGraph AI API",
    description="Multi-agent enterprise incident intelligence powered by MeshAPI.",
    version="1.0.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "mesh_api_key_configured": bool(MESH_API_KEY),
        "model": MESH_MODEL,
        "indexed_chunks": len(load_chunks())
    }

@app.get("/api/documents")
def documents():
    chunks = load_chunks()
    grouped = {}
    for item in chunks:
        name = item.get("metadata", {}).get("source", "unknown")
        grouped[name] = grouped.get(name, 0) + 1
    return {"documents": [{"filename": k, "chunks": v} for k, v in grouped.items()]}

@app.post("/api/ingest")
async def upload_documents(files: list[UploadFile] = File(...)):

    results = []

    for file in files:
        filename = Path(file.filename or "upload.txt").name

        try:
            content = await file.read()

            if len(content) > 20 * 1024 * 1024:
                raise HTTPException(
                    status_code=413,
                    detail="File exceeds 20 MB limit."
                )

            destination = UPLOAD_DIR / filename
            destination.write_bytes(content)

            # Use your existing ingestion pipeline
            count = ingest_file(destination)

            results.append({
                "filename": filename,
                "status": "success",
                "chunks_added": count,
                "message": "Document indexed successfully."
            })

        except Exception as exc:
            results.append({
                "filename": filename,
                "status": "failed",
                "error": str(exc)
            })

    successful = sum(
        1 for item in results if item["status"] == "success"
    )

    failed = len(results) - successful

    return {
        "total_files": len(files),
        "successful": successful,
        "failed": failed,
        "results": results
    }

@app.post("/api/investigate")
async def investigate_incident(request: IncidentRequest):

    try:

        result = investigate(
            query=request.query,
            top_k=request.top_k,
            retrieval_mode=request.retrieval_mode,
            use_reranker=request.use_reranker
        )

        evidence = result.get("evidence", [])

        retrieved_contexts = [
            item["text"]
            for item in evidence
            if item.get("text")
        ]

        return {
            "query": request.query,

            "answer": result.get("final_answer", ""),

            "retrieved_contexts": retrieved_contexts,

            "evidence": evidence,

            "analysis": result.get("analysis", ""),

            "verification": result.get("verification", {}),

            "evaluation": result.get("evaluation", {}),

            "trace": result.get("trace", []),

            "retrieval_mode": request.retrieval_mode,

            "reranking_enabled": (
                request.retrieval_mode == "hybrid"
                and request.use_reranker
            ),

            "retrieval_seconds": result.get(
                "retrieval_seconds", 0
            ),

            "retrieval_count": len(evidence),

            "retry_count": result.get("retries", 0)
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Incident investigation failed: {str(exc)}"
        )
