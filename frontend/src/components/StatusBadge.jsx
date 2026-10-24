const LABEL = {
  complete: "Complete", incomplete: "Incomplete", unassessable: "Not assessable", blank: "Blank",
  needs_manual_grading: "Needs manual grading", ready: "Ready to grade", review: "Awaiting review",
  confirmed: "Confirmed", succeeded: "Succeeded", failed: "Failed", running: "Running",
};
const TONE = { ready: "incomplete", review: "needs_manual_grading", confirmed: "complete", succeeded: "complete", failed: "blank", running: "incomplete" };

export default function StatusBadge({ status }) {
  return <span className={"badge " + (TONE[status] || status)}>{LABEL[status] || status}</span>;
}