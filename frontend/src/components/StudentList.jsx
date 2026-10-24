import StatusBadge from "./StatusBadge.jsx";

export default function StudentList({ proposals, selected, onSelect, done }) {
  return (
    <div className="list">
      {proposals.map((p, i) => (
        <button key={p.student_id} className={"item" + (i === selected ? " on" : "")} onClick={() => onSelect(i)}>
          <span>{p.student_id}</span>
          {p.answer_status === "needs_manual_grading" && !done[p.student_id] ? <StatusBadge status="needs_manual_grading" /> : <StatusBadge status={p.answer_status} />}
        </button>
      ))}
    </div>
  );
}