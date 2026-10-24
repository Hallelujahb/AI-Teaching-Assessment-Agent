// Pick an assessment and batch, or describe the job in words. Add a batch for fresh input.
import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import AddBatchForm from "../components/AddBatchForm.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";

export default function SelectPage({ onStart }) {
  const [list, setList] = useState([]);
  const [aid, setAid] = useState("");
  const [batches, setBatches] = useState([]);
  const [bid, setBid] = useState("");
  const [text, setText] = useState("");
  const [adding, setAdding] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => { api.assessments().then((l) => { setList(l); if (l[0]) setAid(String(l[0].id)); }).catch(setErr); }, []);
  const loadBatches = (id) => api.batches(id).then((b) => { setBatches(b); setBid(String((b.find((x) => !x.confirmed) || b[0] || {}).id ?? "")); }).catch(setErr);
  useEffect(() => { if (aid) loadBatches(aid); }, [aid]);

  const batch = batches.find((b) => String(b.id) === bid);
  return (
    <div className="stack">
      <h1>Grade a batch</h1>
      <ErrorBanner error={err} />
      <div className="panel stack">
        <div className="row" style={{ alignItems: "flex-end" }}>
          <div style={{ flex: 1, minWidth: 220 }}>
            <label htmlFor="as">Assessment</label>
            <select id="as" value={aid} onChange={(e) => setAid(e.target.value)}>{list.map((a) => <option key={a.id} value={a.id}>{a.title}</option>)}</select>
          </div>
          <div style={{ flex: 1, minWidth: 220 }}>
            <label htmlFor="ba">Batch</label>
            <select id="ba" value={bid} onChange={(e) => setBid(e.target.value)}>
              {batches.map((b) => <option key={b.id} value={b.id}>{b.label} ({b.student_count} answers{b.confirmed ? ", confirmed" : ""})</option>)}
            </select>
          </div>
          <button className="btn primary" disabled={!bid || batch?.confirmed || !batch?.student_count}
            onClick={() => onStart({ assessment_id: +aid, batch_id: +bid, request: text.trim() || null })}>Grade this batch</button>
        </div>
        {batch && !batch.student_count && <p className="muted small">No student has handed in an answer to this batch yet.</p>}
        {batch?.confirmed && <p className="muted small">This batch is confirmed and read-only. Open it under Confirmed results.</p>}
      </div>
      <div className="panel stack">
        <div>
          <label htmlFor="rq">Or ask in your own words</label>
          <input id="rq" placeholder="For example: grade the Python batch" maxLength={500} value={text} onChange={(e) => setText(e.target.value)} />
        </div>
        <div className="row"><button className="btn" disabled={!text.trim()} onClick={() => onStart({ request: text.trim() })}>Send request</button>
          <span className="muted small">If the request is unclear, the agent asks you a question instead of guessing.</span></div>
      </div>
      <div><button className="btn" onClick={() => setAdding(!adding)}>{adding ? "Close" : "Add a batch of answers"}</button></div>
      {adding && aid && <AddBatchForm assessmentId={aid} onAdded={() => { loadBatches(aid); setAdding(false); }} />}
    </div>
  );
}
