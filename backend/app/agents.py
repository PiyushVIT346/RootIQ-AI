import json
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from .llm import chat, chat_json
from .retrieval import search
import time
from .config import TOP_K, MAX_RETRIEVAL_RETRIES

class OpsState(TypedDict, total=False):
    query: str
    top_k: int
    retrieval_mode: str
    use_reranker: bool
    retrieval_seconds: float

    plan: List[str]
    evidence: List[Dict[str, Any]]
    analysis: str
    verification: Dict[str, Any]
    resolution: str
    evaluation: Dict[str, Any]
    retries: int
    trace: List[Dict[str, str]]
    final_answer: str

def trace(state, agent, detail):
    return state.get("trace", []) + [{"agent": agent, "detail": detail}]

def planner(state):
    result = chat_json(
        "You are a query planning agent for production incident investigations.",
        f'''Break this incident into 3-5 focused retrieval queries. Return JSON
        {{"queries":["..."]}}. User incident: {state["query"]}'''
    )
    try:
        queries = json.loads(result).get("queries", [])
    except Exception:
        queries = [state["query"]]
    return {
        "plan": queries[:5] or [state["query"]],
        "trace": trace(state, "Query Planner", f"Created {len(queries[:5]) or 1} retrieval queries.")
    }

def retrieval_agent(state):

    all_results = []
    seen = set()
    total_retrieval_time = 0.0

    mode = state.get("retrieval_mode", "hybrid")
    reranker_enabled = state.get("use_reranker", True)
    top_k = state.get("top_k", TOP_K)

    for q in state.get("plan", [state["query"]]):

        output = search(
            query=q,
            top_k=top_k,
            retrieval_mode=mode,
            use_reranker=reranker_enabled
        )

        total_retrieval_time += output["retrieval_seconds"]

        for item in output["results"]:

            chunk_id = item["chunk_id"]

            if chunk_id not in seen:
                seen.add(chunk_id)
                all_results.append(item)

    all_results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return {
        "evidence": all_results[:top_k],

        "retrieval_seconds": (
            state.get("retrieval_seconds", 0)
            + total_retrieval_time
        ),

        "trace": trace(
            state,
            "RAG Retrieval Agent",
            (
                f"Retrieved {len(all_results[:top_k])} passages. "
                f"Mode={mode}, reranking={reranker_enabled}."
            )
        )
    }


def analyst(state):
    evidence = state.get("evidence", [])

    prompt = f'''
Incident:
{state["query"]}

Retrieved passages:
{json.dumps(evidence, ensure_ascii=False)}

Analyze the incident using only the retrieved document evidence.

List:
1. Plausible root causes
2. Supporting evidence IDs and sources
3. Contradicting or missing evidence
4. Confidence (low, medium, high)

Do not claim a root cause is confirmed unless
the evidence directly establishes it.
'''

    answer = chat(
        "You are a careful senior site reliability engineer. "
        "Separate facts from hypotheses. Never invent logs, "
        "metrics, or causes.",
        prompt
    )

    return {
        "analysis": answer,
        "trace": trace(
            state,
            "Root Cause Analyst",
            "Analyzed hybrid-retrieved document evidence."
        )
    }

def verifier(state):
    prompt = f'''
User incident: {state["query"]}
Evidence: {json.dumps(state.get("evidence", []), ensure_ascii=False)}
Analysis: {state.get("analysis", "")}

Check whether each important claim is supported by retrieved evidence.
Return JSON:
{{"sufficient":true/false,"issues":["..."],"supported_claims":["..."],"missing_evidence":["..."]}}
Mark sufficient false if there is no usable evidence or key claims are unsupported.
'''
    raw = chat_json(
        "You are a strict evidence verification agent. Do not approve unsupported claims.",
        prompt
    )
    try:
        result = json.loads(raw)
    except Exception:
        result = {
            "sufficient": bool(state.get("evidence")),
            "issues": ["Verifier returned unparseable output; manual review required."],
            "supported_claims": [],
            "missing_evidence": []
        }
    return {
        "verification": result,
        "trace": trace(state, "Evidence Verifier", "Checked analysis claims against retrieved passages.")
    }

def route_after_verify(state):
    sufficient = state.get("verification", {}).get("sufficient", False)
    retries = state.get("retries", 0)
    if not sufficient and retries < MAX_RETRIEVAL_RETRIES:
        return "retry"
    return "resolution"

def retry_retrieval(state):

    missing = state.get(
        "verification", {}
    ).get("missing_evidence", [])

    extra = " ".join(missing)

    new_query = state["query"] + " " + extra

    mode = state.get("retrieval_mode", "hybrid")
    reranker_enabled = state.get("use_reranker", True)

    output = search(
        query=new_query,
        top_k=state.get("top_k", TOP_K) + 4,
        retrieval_mode=mode,
        use_reranker=reranker_enabled
    )

    merged = {
        item["chunk_id"]: item
        for item in state.get("evidence", [])
    }

    for item in output["results"]:
        merged[item["chunk_id"]] = item

    return {
        "evidence": sorted(
            merged.values(),
            key=lambda item: item["score"],
            reverse=True
        ),

        "retrieval_seconds": (
            state.get("retrieval_seconds", 0)
            + output["retrieval_seconds"]
        ),

        "retries": state.get("retries", 0) + 1,

        "trace": trace(
            state,
            "Corrective Retrieval",
            f"Expanded {mode} retrieval using verifier feedback."
        )
    }

def resolution(state):
    prompt = f'''
Incident: {state["query"]}
Root cause analysis: {state.get("analysis", "")}
Verification: {json.dumps(state.get("verification", {}), ensure_ascii=False)}
Evidence: {json.dumps(state.get("evidence", []), ensure_ascii=False)}

Create an actionable troubleshooting plan with:
1. Executive summary
2. Ranked probable causes (clearly label hypotheses)
3. Safe diagnostic checks
4. Recommended remediation steps
5. Rollback / escalation considerations
6. Evidence citations using [source: filename, chunk: chunk_id]
7. Unknowns and what additional data is required

Do not suggest destructive actions without explicit warnings. Do not invent citations.
'''
    answer = chat(
        "You are a cautious production incident response engineer. Give safe, testable, evidence-grounded recommendations.",
        prompt
    )
    return {
        "resolution": answer,
        "trace": trace(state, "Resolution Agent", "Generated prioritized diagnostic and remediation steps with source references.")
    }

def evaluator(state):
    evidence_count = len(state.get("evidence", []))
    sufficient = state.get("verification", {}).get("sufficient", False)
    # Transparent heuristic indicators, not a claim of formal RAGAS evaluation.
    retrieval_score = min(1.0, evidence_count / max(1, state.get("top_k", TOP_K)))
    verification_score = 1.0 if sufficient else 0.35
    overall = round(0.55 * retrieval_score + 0.45 * verification_score, 2)
    final = state.get("resolution", "")
    if not sufficient:
        final += (
            "\n\n**Evidence warning:** The verifier could not establish that all "
            "important claims are supported. Treat the root causes as hypotheses "
            "and collect the missing evidence before taking action."
        )
    return {
        "evaluation": {
            "retrieval_coverage": round(retrieval_score, 2),
            "evidence_verification": round(verification_score, 2),
            "workflow_score": overall,
            "evidence_count": evidence_count,
            "verified": sufficient
        },
        "final_answer": final,
        "trace": trace(state, "Evaluation Agent", f"Computed transparent workflow indicators; score={overall}.")
    }

def build_graph():
    graph = StateGraph(OpsState)

    graph.add_node("planner", planner)
    graph.add_node("retrieval", retrieval_agent)
    graph.add_node("analyst", analyst)
    graph.add_node("verifier", verifier)
    graph.add_node("retry", retry_retrieval)
    graph.add_node("resolution", resolution)
    graph.add_node("evaluator", evaluator)

    graph.set_entry_point("planner")

    graph.add_edge("planner", "retrieval")
    graph.add_edge("retrieval", "analyst")
    graph.add_edge("analyst", "verifier")

    graph.add_conditional_edges(
        "verifier",
        route_after_verify,
        {
            "retry": "retry",
            "resolution": "resolution"
        }
    )

    graph.add_edge("retry", "analyst")
    graph.add_edge("resolution", "evaluator")
    graph.add_edge("evaluator", END)

    return graph.compile()

workflow = build_graph()

def investigate(
    query: str,
    top_k: int = TOP_K,
    retrieval_mode: str = "hybrid",
    use_reranker: bool = True
):

    return workflow.invoke({
        "query": query,
        "top_k": top_k,
        "retrieval_mode": retrieval_mode,
        "use_reranker": use_reranker,
        "retrieval_seconds": 0.0,
        "retries": 0,
        "trace": []
    })
