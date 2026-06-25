import { NavLink, Outlet } from "react-router-dom";

import SpeakerPicker from "./SpeakerPicker";

const MAIN_NAV = [
  { to: "/", label: "今天", end: true, icon: "🔥" },
  { to: "/series", label: "我的番剧库", icon: "📺" },
  { to: "/tower", label: "修炼塔", icon: "🗼" },
];

const SECONDARY_NAV = [
  { to: "/grammar", label: "词库", icon: "📖" },
  { to: "/progress", label: "进度", icon: "📈" },
];

export default function Layout() {
  return (
    <div className="min-h-screen">
      <nav className="bg-white/85 backdrop-blur border-b border-ink-200/70 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center gap-1">
          <span className="font-bold text-brand-700 mr-3">追番日语</span>
          {MAIN_NAV.map((n) => (
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
          <div className="ml-auto flex items-center gap-3">
            <div className="flex items-center gap-1 text-xs">
              {SECONDARY_NAV.map((n) => (
                <NavLink
                  key={n.to}
                  to={n.to}
                  className={({ isActive }) =>
                    `text-ink-400 hover:text-brand-600 transition-colors px-1.5 py-1 ${
                      isActive ? "text-brand-600 font-medium" : ""
                    }`
                  }
                >
                  <span className="mr-0.5 opacity-70">{n.icon}</span>{n.label}
                </NavLink>
              ))}
            </div>
            <SpeakerPicker />
          </div>
        </div>
      </nav>
      <main className="max-w-5xl mx-auto px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
