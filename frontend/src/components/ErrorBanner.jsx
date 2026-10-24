// Plain-language errors with field-level details and an optional retry.
export default function ErrorBanner({ error, onRetry }) {
  if (!error) return null;
  const fields = error.details && error.details.fields;
  return (
    <div className="banner" role="alert">
      <div>{error.message}</div>
      {fields && <ul>{Object.entries(fields).map(([k, v]) => <li key={k}>{k}: {v}</li>)}</ul>}
      {onRetry && <p style={{ margin: ".6rem 0 0" }}><button className="btn" onClick={onRetry}>Try again</button></p>}
    </div>
  );
}