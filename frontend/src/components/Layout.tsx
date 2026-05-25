import { NavLink, Outlet } from "react-router-dom";

import SpeakerPicker from "./SpeakerPicker";

const NAV = [
  { to: "/", label: "今日训练", end: true, icon: "🔥" },
  { to: "/series", label: "番剧", icon: "📺" },
  { to: "/review", label: "复习", icon: "🧠" },
  { to: "/grammar", label: "语法清单", icon: "📚" },
  { to: "/progress", label: "进度", icon: "📈" },
];

export default function Layout() {
  return (
    <div className="min-h-screen">
      <nav className="bg-white/85 backdrop-blur border-b border-ink-200/70 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center gap-1">
          <span className="font-bold text-brand-700 mr-3">追番日语</span>
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `nav-link ${isActive ? "nav-link-active" : ""}`
              }
            >
              <span className="mr-1 opacity-80">{n.icon}</span>{n.label}
            </NavLink>
          ))}
          <div className="ml-auto"><SpeakerPicker /></div>
        </div>
      </nav>
      <main className="max-w-5xl mx-auto px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
