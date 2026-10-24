export const when = (s) => (s ? new Date(s).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "");
export const initials = (s) => String(s || "?").trim().slice(0, 2).toUpperCase();