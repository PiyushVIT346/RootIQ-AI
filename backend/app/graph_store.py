import json
import re
import networkx as nx
from .config import GRAPH_PATH
from .llm import chat_json

def _load_graph():
    graph = nx.Graph()
    if GRAPH_PATH.exists():
        try:
            payload = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
            graph.add_nodes_from(payload.get("nodes", []))
            graph.add_edges_from(payload.get("edges", []))
        except Exception:
            pass
    return graph

def _save_graph(graph):
    payload = {
        "nodes": [{"id": n, **d} for n, d in graph.nodes(data=True)],
        "edges": [{"source": u, "target": v, **d} for u, v, d in graph.edges(data=True)]
    }
    GRAPH_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

def add_graph_facts(source: str, text: str):
    graph = _load_graph()
    prompt = f'''
Extract up to 12 important entities and up to 15 relationships from this technical text.
Entities should include services, databases, APIs, errors, incidents, teams, tools.
Return JSON: {{"entities":[{{"name":"...","type":"..."}},...],
"relations":[{{"source":"...","target":"...","relation":"depends_on / caused_by / affects / related_to"}}]}}
TEXT:
{text[:12000]}
'''
    try:
        data = json.loads(chat_json(
            "You extract factual entities and relationships. Never invent facts.",
            prompt
        ))
        entities = data.get("entities", [])
        relations = data.get("relations", [])
        for entity in entities:
            name = str(entity.get("name", "")).strip()
            if name:
                graph.add_node(name, entity_type=entity.get("type", "unknown"))
                graph.add_edge(name, source, relation="mentioned_in")
        for rel in relations:
            a, b = str(rel.get("source", "")).strip(), str(rel.get("target", "")).strip()
            if a and b:
                graph.add_node(a)
                graph.add_node(b)
                graph.add_edge(a, b, relation=rel.get("relation", "related_to"))
        _save_graph(graph)
    except Exception:
        # Ingestion remains usable even if graph extraction fails.
        graph.add_node(source, entity_type="document")
        _save_graph(graph)

def search_graph(query: str, limit: int = 12):
    graph = _load_graph()
    terms = set(re.findall(r"[a-zA-Z0-9_.-]+", query.lower()))
    matched = []
    for node, attrs in graph.nodes(data=True):
        name = str(node)
        if any(term in name.lower() or name.lower() in term for term in terms if len(term) > 2):
            matched.append(node)
    expanded = set(matched)
    for node in matched:
        expanded.update(graph.neighbors(node))
    results = []
    for node in list(expanded)[:limit]:
        neighbors = []
        for neighbor in graph.neighbors(node):
            neighbors.append({
                "name": neighbor,
                "relation": graph.edges[node, neighbor].get("relation", "related_to")
            })
        results.append({
            "entity": node,
            "type": graph.nodes[node].get("entity_type", "unknown"),
            "relationships": neighbors[:8]
        })
    return results
