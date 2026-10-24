// One criterion: AI score, evidence, explanation, and the lecturer's own score box.
export default function CriterionCard({ c, value, onChange }) {
  const ev = c.evidence_status;
  return (
    <div className="crit">
      <div>
        <h3>{c.name} <span className="muted small">out of {c.max_score}</span></h3>
        {ev === "found" && <p className="quote">"{c.evidence}"</p>}
        {ev === "not_found" && <p className="quote missing">Quote not found in answer: "{c.evidence}"</p>}
        {ev === "none" && <p className="quote">No supporting evidence found</p>}
        {c.explanation && <p className="small">{c.explanation}</p>}
      </div>
      <div>
        <label htmlFor={"s" + c.criterion_id}>AI: {c.proposed_score ?? "none"}</label>
        <input id={"s" + c.criterion_id} className="score num" type="number" min="0" max={c.max_score} step="1"
          value={value} onChange={(e) => onChange(e.target.value)} />
      </div>
    </div>
  );
}