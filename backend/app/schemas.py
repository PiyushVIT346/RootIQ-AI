from pydantic import BaseModel, Field
from typing import Optional, Literal


class IncidentRequest(BaseModel):
    query: str = Field(min_length=8, max_length=8000)

    top_k: Optional[int] = Field(
        default=8,
        ge=1,
        le=20
    )

    retrieval_mode: Literal[
        "vector",
        "bm25",
        "hybrid"
    ] = "hybrid"

    use_reranker: bool = True


class IngestResponse(BaseModel):
    filename: str
    chunks_added: int
    message: str