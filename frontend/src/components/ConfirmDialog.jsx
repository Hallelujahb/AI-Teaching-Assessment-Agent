export default function ConfirmDialog({ open, title, body, yes, onYes, onNo, busy }) {
  if (!open) return null;
  return (
    <div className="scrim" onClick={onNo}>
      <div className="modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <h2>{title}</h2>
        <p>{body}</p>
        <div className="row">
          <button className="btn primary" onClick={onYes} disabled={busy}>{yes}</button>
          <button className="btn" onClick={onNo} disabled={busy}>Cancel</button>
        </div>
      </div>
    </div>
  );
}