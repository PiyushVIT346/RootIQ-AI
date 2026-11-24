
import os
import json
import asyncio
from pathlib import Path

import requests
import pandas as pd
from dotenv import load_dotenv
from datasets import Dataset

from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings

from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

from ragas.metrics import (faithfulness,answer_relevancy,context_precision,context_recall,)

load_dotenv()

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

API_URL = "http://127.0.0.1:8000/api/investigate"

MESH_API_KEY = os.getenv("MESH_API_KEY")
MESH_BASE_URL = os.getenv("MESH_BASE_URL","https://api.meshapi.ai/v1")
MESH_MODEL = os.getenv("MESH_MODEL", "openai/gpt-4o")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL","sentence-transformers/all-MiniLM-L6-v2")

if not MESH_API_KEY:
    raise ValueError("MESH_API_KEY is missing from your .env file.")

# --------------------------------------------------
# EVALUATION DATASET
# --------------------------------------------------

TEST_CASES = [
    {
        "id": "Q1",
        "question": (
            "Why did checkout-api return HTTP 503 in incident INC-1001?"
        ),
        "ground_truth": (
            "The checkout API returned HTTP 503 because "
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
            "What caused Kafka consumer lag in incident INC-1004?"
        ),
        "ground_truth": (
            "The Kafka consumer lag was associated with "
            "oversized consumer batches and database timeouts."
        )
    },
    {
        "id": "Q4",
        "question": (
            "Compare incidents INC-1002 and INC-1006. "
            "Did they have the same root cause?"
        ),
        "ground_truth": (
            "INC-1002 was related to database connection "
            "exhaustion, whereas INC-1006 involved a payment "
            "API memory leak caused by middleware object retention. "
            "They had different root causes."
        )
    },
    {
        "id": "Q5",
        "question": (
            "What caused PostgreSQL disk pressure in incident INC-1007?"
        ),
        "ground_truth": (
            "INC-1007 involved PostgreSQL disk pressure "
            "associated with temporary tables and delayed "
            "WAL archiving."
        )
    }
]


# --------------------------------------------------
# MESHAPI EVALUATOR
# --------------------------------------------------

def create_evaluator():

    judge_model = ChatOpenAI(
        model=MESH_MODEL,
        api_key=MESH_API_KEY,
        base_url=MESH_BASE_URL,
        temperature=0
    )

    judge_embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )

    evaluator_llm = LangchainLLMWrapper(judge_model)

    evaluator_embeddings = LangchainEmbeddingsWrapper(judge_embeddings)

    return evaluator_llm, evaluator_embeddings


# --------------------------------------------------
# RESPONSE EXTRACTION
# --------------------------------------------------

def find_first_value(data, possible_keys):
    """
    Recursively find the first matching field in an API response.
    """

    if isinstance(data, dict):

        for key in possible_keys:
            if key in data and data[key] is not None:
                return data[key]

        for value in data.values():
            result = find_first_value(value, possible_keys)
            if result is not None:
                return result

    elif isinstance(data, list):

        for item in data:
            result = find_first_value(item, possible_keys)
            if result is not None:
                return result

    return None


def extract_text(value):
    """
    Convert retrieved evidence into plain text.
    """

    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        for key in ["page_content", "text", "content", "snippet"]:
            if isinstance(value.get(key), str):
                return value[key]

    return str(value)


def extract_answer_and_contexts(response_data):

    answer = find_first_value(
        response_data,
        ["answer", "final_answer", "response"]
    )

    contexts = find_first_value(
        response_data,
        [
            "retrieved_contexts",
            "contexts",
            "evidence",
            "retrieved_documents"
        ]
    )

    if isinstance(answer, dict):
        answer = extract_text(answer)

    if not isinstance(answer, str) or not answer.strip():
        raise ValueError(
            "Could not find the generated answer in API response."
        )

    if not isinstance(contexts, list) or not contexts:
        raise ValueError(
            "No retrieved contexts found in API response. "
            "Expose the actual retrieved chunks from "
            "/api/investigate before running RAGAS."
        )

    contexts = [
        extract_text(item)
        for item in contexts
        if extract_text(item).strip()
    ]

    if not contexts:
        raise ValueError("Retrieved context list is empty.")

    return answer, contexts


# --------------------------------------------------
# RUN OPSGRAPH AI
# --------------------------------------------------

def collect_rag_results():

    evaluation_rows = []

    print("\n========== COLLECTING RAG RESPONSES ==========\n")

    for test in TEST_CASES:

        print(f"Running {test['id']}: {test['question']}")

        try:

            response = requests.post(
                API_URL,
                json={"query": test["question"]},
                timeout=180
            )

            response.raise_for_status()

            response_data = response.json()

            answer, contexts = extract_answer_and_contexts(
                response_data
            )

            evaluation_rows.append({
                "id": test["id"],
                "question": test["question"],
                "answer": answer,
                "contexts": contexts,
                "ground_truth": test["ground_truth"]
            })

            print("Successfully collected answer and contexts.")
            print(f"Retrieved chunks: {len(contexts)}")
            print("-" * 60)

        except Exception as exc:

            print(f"Failed {test['id']}: {exc}")
            print("-" * 60)

    if not evaluation_rows:
        raise RuntimeError("No evaluation samples collected. Check the API and response structure." )

    return evaluation_rows


# --------------------------------------------------
# RUN RAGAS
# --------------------------------------------------

def run_ragas_evaluation(rows):

    print("\n========== INITIALIZING RAGAS ==========\n")

    evaluator_llm, evaluator_embeddings = create_evaluator()

    # Configure the four RAGAS metrics.
    faithfulness.llm = evaluator_llm

    answer_relevancy.llm = evaluator_llm
    answer_relevancy.embeddings = evaluator_embeddings

    context_precision.llm = evaluator_llm
    context_recall.llm = evaluator_llm

    dataset = Dataset.from_list([
        {
            "question": row["question"],
            "answer": row["answer"],
            "contexts": row["contexts"],
            "ground_truth": row["ground_truth"]
        }
        for row in rows
    ])

    print("Running RAGAS metrics...")
    print("This may take a few minutes.\n")

    results = evaluate(
        dataset=dataset,
        metrics=[
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall
        ],
        raise_exceptions=True
    )

    return results


# --------------------------------------------------
# SAVE RESULTS
# --------------------------------------------------

def save_results(rows, results):

    results_df = results.to_pandas()

    output_dir = Path("evaluation_results")
    output_dir.mkdir(exist_ok=True)

    # Detailed metric scores
    results_df.to_csv(
        output_dir / "ragas_scores.csv",
        index=False
    )

    # Save questions, generated answers and contexts
    with open(
        output_dir / "evaluation_samples.json",
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            rows,
            file,
            indent=2,
            ensure_ascii=False
        )

    metric_columns = [
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall"
    ]

    summary = {}

    for metric in metric_columns:
        if metric in results_df.columns:
            summary[metric] = round(
                float(results_df[metric].mean()),
                4
            )

    with open(
        output_dir / "summary.json",
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(summary, file, indent=2)

    print("\n========== RAGAS EVALUATION RESULTS ==========\n")

    for metric, score in summary.items():
        print(f"{metric}: {score:.4f}")

    print("\nFiles saved inside:", output_dir.resolve())

    return summary


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    rows = collect_rag_results()

    print(f"\nCollected {len(rows)} evaluation samples.")

    results = run_ragas_evaluation(rows)

    save_results(rows, results)


if __name__ == "__main__":
    main()
