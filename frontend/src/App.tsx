import React, { useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, Link, useLocation } from "react-router-dom";
import { LandingPage } from "./pages/LandingPage";
import SmartRecommendationPage from "./pages/SmartRecommendationPage";
import { DashboardPage } from "./pages/DashboardPage";
import { VenuesPage } from "./pages/VenuesPage";
import { VenuesProvider } from "./pages/VenuesContext";
import { AboutPage } from "./pages/AboutPage";

const navItems = [
  {
    to: "/",
    label: "Home",
    exact: true,
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5">
        <path d="M3 12L12 3l9 9" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M9 21V12h6v9" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M3 12v9h18V12" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    to: "/dashboard",
    label: "Dashboard",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5">
        <rect x="3" y="3" width="7" height="7" rx="1"/>
        <rect x="14" y="3" width="7" height="7" rx="1"/>
        <rect x="3" y="14" width="7" height="7" rx="1"/>
        <rect x="14" y="14" width="7" height="7" rx="1"/>
      </svg>
    ),
  },
  {
    to: "/venues",
    label: "All Venues",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5">
        <path d="M4 6h16M4 10h16M4 14h16M4 18h16" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    to: "/conferences",
    label: "Conferences",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" strokeLinecap="round"/>
        <circle cx="9" cy="7" r="4"/>
        <path d="M23 21v-2a4 4 0 0 0-3-3.87" strokeLinecap="round"/>
        <path d="M16 3.13a4 4 0 0 1 0 7.75" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    to: "/journals",
    label: "Journals",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" strokeLinecap="round"/>
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    to: "/recommendations",
    label: "Smart Pick",
    highlight: true,
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5">
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
      </svg>
    ),
  },
  {
    to: "/about",
    label: "About",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12" strokeLinecap="round"/>
        <line x1="12" y1="16" x2="12.01" y2="16" strokeLinecap="round"/>
      </svg>
    ),
  },
];

function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const location = useLocation();

  return (
    <aside
      className={`sidebar ${collapsed ? "sidebar-collapsed" : "sidebar-expanded"}`}
    >
      {/* Logo / brand */}
      <div className="sidebar-brand">
        {!collapsed && (
          <div className="flex-1 min-w-0">
            <p className="font-bold text-gray-900 text-sm leading-tight truncate">Academic Venue</p>
            <p className="text-xs text-gray-500 truncate">Recommender</p>
          </div>
        )}
        <button
          onClick={onToggle}
          className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 shrink-0"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4">
            {collapsed
              ? <path d="M9 18l6-6-6-6" strokeLinecap="round" strokeLinejoin="round"/>
              : <path d="M15 18l-6-6 6-6" strokeLinecap="round" strokeLinejoin="round"/>
            }
          </svg>
        </button>
      </div>

      {/* Nav items */}
      <nav className="flex-1 px-2 py-3 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = item.exact
            ? location.pathname === item.to
            : location.pathname.startsWith(item.to) && item.to !== "/";
          return (
            <Link
              key={item.to}
              to={item.to}
              title={collapsed ? item.label : undefined}
              className={`sidebar-link ${isActive ? "sidebar-link-active" : "sidebar-link-inactive"} ${item.highlight && !isActive ? "sidebar-link-highlight" : ""}`}
            >
              <span className="shrink-0">{item.icon}</span>
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

export const App: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <BrowserRouter>
      <VenuesProvider>
        <div className="app-layout">
          <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
          <main className="app-content">
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/venues" element={<VenuesPage />} />
              <Route path="/conferences" element={<VenuesPage kind="conference" />} />
              <Route path="/journals" element={<VenuesPage kind="journal" />} />
              <Route path="/recommendations" element={<SmartRecommendationPage />} />
              <Route path="/about" element={<AboutPage />} />
              <Route path="/recommend" element={<Navigate to="/recommendations" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </VenuesProvider>
    </BrowserRouter>
  );
};

