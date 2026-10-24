// The name in Amharic (Qeleme). Each letter lifts in turn on hover.
const LETTERS = ["\u1240", "\u1208", "\u121C"];

export default function Logo({ size = 28 }) {
  return (
    <span className="wordmark" style={{ fontSize: size }} role="img" aria-label="Qeleme">
      {LETTERS.map((g, i) => <span key={i} style={{ "--i": i }}>{g}</span>)}
    </span>
  );
}