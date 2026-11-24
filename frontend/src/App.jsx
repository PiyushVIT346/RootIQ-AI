import { useEffect, useState } from "react";
import {
  Activity, Upload, Search, Network, ShieldCheck, FileText,
  AlertTriangle, Cpu, CheckCircle2, Loader2, Server, ChevronRight
} from "lucide-react";

const API = "http://127.0.0.1:8000";

function App() {
  const [query, setQuery] = useState("");
  const [files, setFiles] = useState([]);
  const [uploadMessage, setUploadMessage] = useState("");
  const [docs, setDocs] = useState([]);
  const [health, setHealth] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  async function refresh() {
    try {
      const [h, d] = await Promise.all([
        fetch(`${API}/api/health`).then(r => r.json()),
        fetch(`${API}/api/documents`).then(r => r.json())
      ]);
      setHealth(h);
      setDocs(d.documents || []);
    } catch {
      setHealth(null);
    }
  }

  useEffect(() => { refresh(); }, []);

  async function uploadDocument(e) {
    e.preventDefault();

    if (files.length === 0) return;

    setUploading(true);
    setError("");
    setUploadMessage("");

    try {
      const body = new FormData();

      files.forEach((file) => {
        body.append("files", file);
      });

      const response = await fetch(`${API}/api/ingest`, {
        method: "POST",
        body
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Upload failed");
      }

      setUploadMessage(
        `Successfully indexed ${data.successful} of ${data.total_files} files.`
      );

      if (data.failed > 0) {
        setError(
          data.results
            .filter(item => item.status === "failed")
            .map(item => `${item.filename}: ${item.error}`)
            .join("\n")
        );
      }

      setFiles([]);
      document.getElementById("file-input").value = "";

      await refresh();

    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
 }

  async function investigate(e) {
    e.preventDefault();
    if (!query.trim()) return;
    setBusy(true); setError(""); setResult(null);
    try {
      const response = await fetch(`${API}/api/investigate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, top_k: 8 })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Investigation failed");
      setResult(data);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-icon"><Network size={21}/></div>
          <div><b>OpsGraph</b><span>ENTERPRISE INTELLIGENCE</span></div>
        </div>
        <div className="side-label">WORKSPACE</div>
        <div className="nav-item active"><Activity size={17}/> Incident investigation</div>
        <div className="nav-item"><Network size={17}/> Knowledge graph</div>
        <div className="nav-item"><FileText size={17}/> Knowledge base</div>
        <div className="sidebar-bottom">
          <div className="status-line"><span className={`dot ${health ? "online" : ""}`}></span>
            {health ? "API connected" : "API disconnected"}</div>
          <small>OpsGraph AI · Local workspace</small>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div><span className="eyebrow">OPERATIONS INTELLIGENCE / INVESTIGATIONS</span>
            <h1>Incident Command Center</h1></div>
          <div className="top-right"><span className="mesh-pill"><span className="dot online"></span>
            MeshAPI · {health?.model || "checking"}</span></div>
        </header>

        <section className="welcome">
          <div>
            <div className="eyebrow">MULTI-AGENT INVESTIGATION SYSTEM</div>
            <h2>Understand incidents.<br/><em>Find the evidence.</em></h2>
            <p>Investigate operational issues using hybrid retrieval, knowledge graphs and specialized AI agents.</p>
          </div>
          <div className="welcome-art"><Network size={110} strokeWidth={0.8}/><span>AGENTIC RAG</span></div>
        </section>

        <div className="stats-grid">
          <Stat icon={<FileText/>} label="Indexed chunks" value={health?.indexed_chunks ?? "—"} />
          <Stat icon={<Server/>} label="Knowledge sources" value={docs.length} />
          <Stat icon={<Cpu/>} label="LLM gateway" value={health?.mesh_api_key_configured ? "Connected" : "Not configured"} />
          <Stat icon={<ShieldCheck/>} label="Workflow" value="7 agents" />
        </div>

        <div className="content-grid">
          <section className="panel investigate-panel">
            <div className="panel-heading"><div><span className="eyebrow">NEW INVESTIGATION</span><h3>Describe the incident</h3></div>
              <span className="live-tag"><span className="dot online"></span> READY</span></div>
            <form onSubmit={investigate}>
              <label>INCIDENT DESCRIPTION</label>
              <textarea value={query} onChange={e => setQuery(e.target.value)}
                placeholder="Example: Our FastAPI application started returning 500 errors after deployment. Database connections are timing out. Investigate possible root causes and recommend safe troubleshooting steps."
                rows={6}/>
              <div className="form-footer"><span>Be specific about symptoms, time and affected services.</span>
                <button className="primary-btn" disabled={busy || !query.trim()}>
                  {busy ? <><Loader2 className="spin" size={16}/> Investigating...</> : <><Search size={16}/> Investigate incident</>}
                </button></div>
            </form>
            {error && <div className="error-box"><AlertTriangle size={16}/>{error}</div>}
            {busy && <div className="working"><Loader2 className="spin" size={20}/> Agents are retrieving evidence and analyzing the incident...</div>}
          </section>

          
          <section className="panel upload-panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">KNOWLEDGE BASE</span>
                <h3>Add knowledge</h3>
              </div>
              <Upload size={19}/>
            </div>

            <form onSubmit={uploadDocument}>
              <label>UPLOAD TECHNICAL DOCUMENTS</label>

              <div className="dropzone">
                <Upload size={23}/>

                <b>
                  {files.length > 0
                    ? `${files.length} files selected`
                    : "Choose multiple documents"}
                </b>

                <span>
                  PDF, DOCX, TXT, MD, LOG or CSV · Max 20 MB per file
                </span>

                <input
                  id="file-input"
                  type="file"
                  multiple
                  accept=".pdf,.docx,.txt,.md,.log,.csv"
                  onChange={(e) => {
                    const selectedFiles = Array.from(e.target.files || []);

                    setFiles(selectedFiles);
                    setUploadMessage("");
                    setError("");
                  }}
              />
              </div>

              {files.length > 0 && (
                <div className="selected-files">
                  <div className="doc-list-title">
                    SELECTED FILES
                    <span>{files.length}</span>
                  </div>

                  {files.map((f, index) => (
                    <div className="doc-row" key={`${f.name}-${index}`}>
                      <FileText size={15}/>
                      <span>{f.name}</span>
                      <small>
                        {(f.size / (1024 * 1024)).toFixed(2)} MB
                      </small>
                    </div>
                  ))}

                  <button
                    type="button"
                    className="remove-files-btn"
                    onClick={() => {
                      setFiles([]);
                      document.getElementById("file-input").value = "";
                    }}
                  >
                    Clear selection
                  </button>
                </div>
              )}

              <button
                type="submit"
                className="secondary-btn"
                disabled={files.length === 0 || uploading}
              >
                {uploading ? (
                  <>
                    <Loader2 className="spin" size={15}/>
                    Indexing files...
                  </>
                ) : (
                  <>
                    <Upload size={15}/>
                    Upload and index {files.length > 0 ? files.length : ""} files
                  </>
                )}
              </button>
            </form>

            {uploadMessage && (
              <div className="success-box">
                <CheckCircle2 size={16}/>
                {uploadMessage}
              </div>
            )}

            <div className="doc-list">
              <div className="doc-list-title">
                INDEXED DOCUMENTS
                <span>{docs.length}</span>
              </div>

              {docs.length === 0 ? (
                <p className="muted">No documents indexed yet.</p>
              ) : (
                docs.map(d => (
                  <div className="doc-row" key={d.filename}>
                    <FileText size={15}/>
                    <span>{d.filename}</span>
                    <small>{d.chunks} chunks</small>
                  </div>
                ))
              )}
            </div>
          </section>

        </div>

        {result && <section className="results">
          <div className="result-title"><div><span className="eyebrow">INVESTIGATION COMPLETE</span><h2>Investigation report</h2></div>
            <span className={result.verification?.sufficient ? "verified" : "unverified"}>
              {result.verification?.sufficient ? <CheckCircle2 size={15}/> : <AlertTriangle size={15}/>}
              {result.verification?.sufficient ? "Evidence verified" : "Evidence needs review"}
            </span></div>
          <div className="result-metrics">
            <Metric label="Evidence passages" value={result.evaluation?.evidence_count ?? 0}/>
            <Metric label="Retrieval coverage" value={`${Math.round((result.evaluation?.retrieval_coverage || 0)*100)}%`}/>
            <Metric label="Verification" value={`${Math.round((result.evaluation?.evidence_verification || 0)*100)}%`}/>
            <Metric label="Workflow score" value={result.evaluation?.workflow_score ?? 0}/>
          </div>
          <div className="report-grid">
            <div className="panel report-main"><h3><ShieldCheck size={18}/> Recommended investigation</h3>
              <div className="markdown-text">{result.answer}</div></div>
            <div className="panel"><h3><Activity size={18}/> Agent execution trace</h3>
              <div className="trace-list">{(result.trace || []).map((t, i) =>
                <div className="trace-item" key={i}><div className="trace-number">{String(i+1).padStart(2,"0")}</div>
                  <div><b>{t.agent}</b><p>{t.detail}</p></div><ChevronRight size={15}/></div>)}</div>
            </div>
          </div>
          <div className="panel evidence-panel"><h3><FileText size={18}/> Retrieved evidence</h3>
            {(result.evidence || []).map((item, i) => <div className="evidence-item" key={i}>
              <div><b>{item.source}</b><small>{item.chunk_id}</small></div>
              <p>{item.text}</p></div>)}
          </div>
          <div className="panel"><h3><Network size={18}/> Knowledge graph context</h3>
            <div className="graph-grid">{(result.graph_context || []).map((node, i) =>
              <div className="graph-node" key={i}><b>{node.entity}</b><small>{node.type}</small>
                {node.relationships?.map((r,j) => <span key={j}>{r.relation} → {r.name}</span>)}</div>)}
              {(!result.graph_context || result.graph_context.length === 0) && <p className="muted">No matching graph entities found.</p>}
            </div>
          </div>
        </section>}
        <footer>OPSGRAPH AI <span>Evidence-led operational intelligence</span></footer>
      </main>
    </div>
  );
}

function Stat({icon,label,value}) {
  return <div className="stat-card"><div className="stat-icon">{icon}</div><div><span>{label}</span><b>{value}</b></div></div>;
}
function Metric({label,value}) {
  return <div className="metric"><span>{label}</span><b>{value}</b></div>;
}
export default App;
