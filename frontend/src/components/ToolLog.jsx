export default function ToolLog({ log }) {
  if (!log || !log.length) return null;
  return (
    <details className="panel">
      <summary>What the agent did ({log.length} steps)</summary>
      <table>
        <thead><tr><th>Step</th><th>Result</th><th>Time</th></tr></thead>
        <tbody>
          {log.map((l, i) => (
            <tr key={i}><td>{l.tool_name}</td><td>{l.outcome}</td><td className="num">{l.duration_ms} ms</td></tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}