import { NavLink, Outlet } from "react-router-dom";

const NAV = [
  { to: "/", label: "今日训练", end: true },
  { to: "/series", label: "番剧" },
  { to: "/review", label: "复习" },
  { to: "/grammar", label: "语法清单" },
  { to: "/progress", label: "进度" },
];

export default function Layout() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <nav className="bg-white border-b">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center gap-6">
          <span className="font-semibold">追番日语</span>
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `text-sm hover:text-indigo-600 ${
                  isActive ? "text-indigo-600 font-medium" : "text-slate-600"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </div>
      </nav>
      <main className="max-w-5xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
