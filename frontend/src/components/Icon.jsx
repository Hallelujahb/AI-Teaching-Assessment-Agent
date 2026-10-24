// Small line icons for the side menu.
const P = {
  dashboard: "M3 3h8v8H3zM13 3h8v5h-8zM13 10h8v11h-8zM3 13h8v8H3z",
  assess: "M5 3h11l3 3v15H5zM9 9h6M9 13h6M9 17h4",
  grade: "M4 20l1-4L16 5l3 3L8 19zM14 7l3 3",
  runs: "M3 12h4l3-8 4 16 3-8h4",
  results: "M5 3h14v18H5zM9 12l2 2 4-4",
  approvals: "M9 11a4 4 0 100-8 4 4 0 000 8zM2 21c0-4 3-6 7-6s7 2 7 6M17 11l2 2 4-4",
  users: "M9 11a4 4 0 100-8 4 4 0 000 8zM2 21c0-4 3-6 7-6s7 2 7 6M17 4a4 4 0 010 7M22 21c0-3-2-5-4-5.5",
  mine: "M5 3h14v18H5zM9 9h6M9 13h6",
  classes: "M3 8l9-5 9 5-9 5zM7 10.5V16c0 1.5 2.5 3 5 3s5-1.5 5-3v-5.5",
  menu: "M4 6h16M4 12h16M4 18h16",
};

export default function Icon({ name, size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={P[name]} />
    </svg>
  );
}
