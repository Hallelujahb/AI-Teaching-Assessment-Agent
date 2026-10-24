// The name in Amharic (Qeleme). Each letter lifts in turn on hover. Pass no size to let CSS decide.
const LETTERS = ["\u1240", "\u1208", "\u121C"];

export default function Logo({ size }) {
  return (
    <span className="wordmark" style={size ? { fontSize: size } : undefined} role="img" aria-label="Qeleme">
      {LETTERS.map((g, i) => <span key={i} style={{ "--i": i }}>{g}</span>)}
    </span>
  );
}