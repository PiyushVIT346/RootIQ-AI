
import os
import time
import json
import requests
import pandas as pd

from pathlib import Path
from dotenv import load_dotenv
from datasets import Dataset

from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings

from ragas import evaluate
from ragas.metrics import (faithfulness,answer_relevancy,context_precision,context_recall)

load_dotenv()

# ==================================================
# CONFIGURATION
# ==================================================

API_URL = "http://127.0.0.1:8000/api/investigate"

MESH_API_KEY = os.getenv("MESH_API_KEY")
MESH_BASE_URL = os.getenv("MESH_BASE_URL","https://api.meshapi.ai/v1")
MESH_MODEL = os.getenv(
    "MESH_MODEL",
    "openai/gpt-4o"
)

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2"
)

TOP_K = 5

OUTPUT_DIR = Path("evaluation_results")
OUTPUT_DIR.mkdir(exist_ok=True)

if not MESH_API_KEY:
    raise ValueError("MESH_API_KEY missing from .env")


# ==================================================
# EXPERIMENT CONFIGURATIONS
# ==================================================

EXPERIMENTS = [
    {
        "name": "Vector Only",
        "mode": "vector",
        "reranker": False
    },
    {
        "name": "BM25 Only",
        "mode": "bm25",
        "reranker": False
    },
    {
        "name": "Hybrid Without Reranking",
        "mode": "hybrid",
        "reranker": False
    },
    {
        "name": "Hybrid With Reranking",
        "mode": "hybrid",
        "reranker": True
    }
]


# ==================================================
# TEST QUESTIONS AND REFERENCE ANSWERS
# ==================================================

TEST_CASES = [
    {
        "id": "Q1",
        "question": (
            "Why did checkout-api return HTTP 503 "
            "in incident INC-1001?"
        ),
        "ground_truth": (
            "Checkout API returned HTTP 503 because "
            "payment-api experienced database connection "
            "exhaustion. Payment retries amplified database "
            "connection demand and affected checkout requests."
        )
    },
    {
        "id": "Q2",
        "question": "What happened in incident INC-1003?",
        "ground_truth": (
            "INC-1003 involved an expired TLS certificate "
            "that caused authentication failures."
        )
    },
    {
        "id": "Q3",
        "question": (
            "What caused Kafka consumer lag in INC-1004?"
        ),
        "ground_truth": (
            "Kafka consumer lag was associated with oversized "
            "consumer batches and database timeouts."
        )
    },
    {
        "id": "Q4",
        "question": (
            "Compare INC-1002 and INC-1006. "
            "Did they have the same root cause?"
        ),
        "ground_truth": (
            "INC-1002 involved database connection exhaustion, "
            "whereas INC-1006 involved a payment API memory leak "
            "caused by middleware object retention. "
            "They had different root causes."
        )
    },
    {
        "id": "Q5",
        "question": (
            "What caused PostgreSQL disk pressure in INC-1007?"
        ),
        "ground_truth": (
            "PostgreSQL disk pressure was associated with "
            "temporary tables and delayed WAL archiving."
        )
    },
   
]


# ==================================================
# MESHAPI JUDGE
# ==================================================

def create_judge():

    return ChatOpenAI(
        model=MESH_MODEL,
        api_key=MESH_API_KEY,
        base_url=MESH_BASE_URL,
        temperature=0
    )


def create_embeddings():

    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )


# ==================================================
# COLLECT EXPERIMENT RESULTS
# ==================================================

def run_experiment(experiment):

    print("\n" + "=" * 65)
    print("EXPERIMENT:", experiment["name"])
    print("=" * 65)

    rows = []
    performance_rows = []

    for test in TEST_CASES:

        print("\nQuestion:", test["id"])

        payload = {
            "query": test["question"],
            "top_k": TOP_K,
            "retrieval_mode": experiment["mode"],
            "use_reranker": experiment["reranker"]
        }

        start = time.perf_counter()

        try:

            response = requests.post(
                API_URL,
                json=payload,
                timeout=300
            )

            response.raise_for_status()

            elapsed = time.perf_counter() - start

            data = response.json()

            answer = data.get("answer", "")
            contexts = data.get("retrieved_contexts", [])

            if not answer or not answer.strip():
                raise ValueError("Empty answer received.")

            if not isinstance(contexts, list) or not contexts:
                raise ValueError("No retrieved contexts received.")

            contexts = [
                str(context)
                for context in contexts
                if context and str(context).strip()
            ]

            if not contexts:
                raise ValueError("Retrieved contexts are empty.")

            rows.append({
                "question": test["question"],
                "answer": answer,
                "contexts": contexts,
                "ground_truth": test["ground_truth"]
            })

            performance_rows.append({
                "experiment": experiment["name"],
                "test_id": test["id"],
                "total_seconds": round(elapsed, 4),
                "retrieval_seconds": data.get(
                    "retrieval_seconds", 0
                ),
                "retrieval_count": data.get(
                    "retrieval_count", len(contexts)
                ),
                "retry_count": data.get("retry_count", 0),
                "status": "SUCCESS"
            })

            print("Success")
            print("Retrieved passages:", len(contexts))
            print("Total time:", round(elapsed, 2), "seconds")
            print(
                "Retrieval time:",
                data.get("retrieval_seconds", 0),
                "seconds"
            )

        except Exception as exc:

            elapsed = time.perf_counter() - start

            print("Failed:", exc)

            performance_rows.append({
                "experiment": experiment["name"],
                "test_id": test["id"],
                "total_seconds": round(elapsed, 4),
                "retrieval_seconds": None,
                "retrieval_count": 0,
                "retry_count": 0,
                "status": "FAILED"
            })

    return rows, performance_rows


# ==================================================
# RAGAS EVALUATION
# ==================================================

def evaluate_experiment(experiment, rows):

    if not rows:
        print("No successful samples. Skipping RAGAS.")
        return []

    dataset = Dataset.from_list(rows)

    metrics = [
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall
    ]

    print("\nRunning RAGAS:", experiment["name"])

    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=create_judge(),
        embeddings=create_embeddings(),
        raise_exceptions=True
    )

    scores = result.to_pandas()

    scores["experiment"] = experiment["name"]

    scores["retrieval_mode"] = experiment["mode"]

    scores["reranking"] = experiment["reranker"]

    return scores.to_dict(orient="records")


# ==================================================
# MAIN EXPERIMENT RUNNER
# ==================================================

def main():

    all_scores = []
    all_performance = []
    all_samples = []

    for experiment in EXPERIMENTS:

        rows, performance = run_experiment(experiment)

        all_performance.extend(performance)

        for index, row in enumerate(rows):
            all_samples.append({
                "experiment": experiment["name"],
                "question": row["question"],
                "answer": row["answer"],
                "contexts": row["contexts"],
                "ground_truth": row["ground_truth"]
            })

        scores = evaluate_experiment(
            experiment,
            rows
        )

        all_scores.extend(scores)

    # ------------------------------------------------
    # SAVE QUESTION-LEVEL RAGAS SCORES
    # ------------------------------------------------

    scores_df = pd.DataFrame(all_scores)

    scores_df.to_csv(
        OUTPUT_DIR / "ragas_question_scores.csv",
        index=False
    )

    # ------------------------------------------------
    # SAVE PERFORMANCE RESULTS
    # ------------------------------------------------

    performance_df = pd.DataFrame(all_performance)

    performance_df.to_csv(
        OUTPUT_DIR / "experiment_performance.csv",
        index=False
    )

    # ------------------------------------------------
    # SAVE ANSWERS AND CONTEXTS
    # ------------------------------------------------

    with open(
        OUTPUT_DIR / "experiment_samples.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            all_samples,
            file,
            indent=4,
            ensure_ascii=False
        )

    # ------------------------------------------------
    # AGGREGATE METRICS
    # ------------------------------------------------

    metric_names = [
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall"
    ]

    if scores_df.empty:
        raise RuntimeError(
            "No RAGAS scores were generated."
        )

    summary = (
        scores_df.groupby("experiment")[metric_names]
        .mean()
        .reset_index()
    )

    summary.to_csv(
        OUTPUT_DIR / "ragas_comparison.csv",
        index=False
    )

    # ------------------------------------------------
    # ADD LATENCY COMPARISON
    # ------------------------------------------------

    successful_performance = performance_df[
        performance_df["status"] == "SUCCESS"
    ].copy()

    latency_summary = (
        successful_performance
        .groupby("experiment")
        .agg(
            average_total_seconds=("total_seconds", "mean"),
            average_retrieval_seconds=("retrieval_seconds", "mean"),
            successful_requests=("status", "count")
        )
        .reset_index()
    )

    latency_summary.to_csv(
        OUTPUT_DIR / "latency_comparison.csv",
        index=False
    )

    # ------------------------------------------------
    # BEST CONFIGURATION
    # ------------------------------------------------

    summary["mean_ragas_score"] = summary[
        metric_names
    ].mean(axis=1)

    best = summary.sort_values(
        "mean_ragas_score",
        ascending=False
    ).iloc[0]

    best_result = {
        "best_experiment": best["experiment"],
        "mean_ragas_score": float(
            best["mean_ragas_score"]
        ),
        "metrics": {
            metric: float(best[metric])
            for metric in metric_names
        },
        "selection_method": (
            "Unweighted mean of the four RAGAS metrics"
        )
    }

    with open(
        OUTPUT_DIR / "best_pipeline.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            best_result,
            file,
            indent=4
        )

    # ------------------------------------------------
    # DISPLAY RESULTS
    # ------------------------------------------------

    print("\n" + "=" * 65)
    print("OPSGRAPH AI - RAGAS COMPARISON")
    print("=" * 65)

    print(summary.to_string(index=False))

    print("\nLATENCY COMPARISON")

    print(latency_summary.to_string(index=False))

    print("\nBEST CONFIGURATION")

    print(json.dumps(best_result, indent=4))

    print("\nFiles saved in:", OUTPUT_DIR.resolve())


if __name__ == "__main__":
    main()
