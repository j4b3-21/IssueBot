import { useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api";
import { DetailPage } from "./pages/Detail";
import { HealthPage } from "./pages/Health";
import { InvestigationsPage } from "./pages/Investigations";
import { LoginPage } from "./pages/Login";
import { OverviewPage } from "./pages/Overview";
import { SettingsPage } from "./pages/Settings";

export function App() {
  const [user, setUser] = useState<string | null | undefined>(undefined);
  const [demo, setDemo] = useState(false);
  const location = useLocation();

  useEffect(() => {
    api<{ username: string; demo_mode: boolean }>("/api/v1/auth/me")
      .then((me) => {
        setUser(me.username);
        setDemo(me.demo_mode);
      })
      .catch(() => setUser(null));
  }, []);

  useEffect(() => {
    const heading = document.querySelector("h1");
    if (heading instanceof HTMLElement) heading.focus();
  }, [location.pathname]);

  if (user === undefined) return <p>Loading IssueBot.</p>;

  return (
    <>
      <a className="skip-link" href="#content">
        Skip to content
      </a>
      {user ? (
        <header className="border-b border-line bg-sheet px-4 py-3">
          <div className="flex items-center justify-between gap-4">
            <p className="text-lg font-semibold">IssueBot</p>
            <button
              type="button"
              onClick={() => {
                void api("/api/v1/auth/logout", { method: "POST" }).finally(() => setUser(null));
              }}
            >
              Sign out
            </button>
          </div>
          <nav className="mt-2 flex flex-wrap gap-4" aria-label="Primary">
            <Link to="/">Overview</Link>
            <Link to="/investigations">Investigations</Link>
            <Link to="/health">Health</Link>
            <Link to="/settings">Settings</Link>
          </nav>
          {demo ? (
            <p className="mt-2 border border-line px-2 py-1">Demo data. Nothing is published to GitHub.</p>
          ) : null}
        </header>
      ) : null}
      <main id="content" className="mx-auto max-w-5xl px-4 py-6">
        <Routes>
          <Route path="/login" element={user ? <Navigate to="/" /> : <LoginPage onSignedIn={(name, isDemo) => { setUser(name); setDemo(isDemo); }} />} />
          <Route path="/" element={user ? <OverviewPage /> : <Navigate to="/login" />} />
          <Route path="/investigations" element={user ? <InvestigationsPage /> : <Navigate to="/login" />} />
          <Route path="/investigations/:id" element={user ? <DetailPage /> : <Navigate to="/login" />} />
          <Route path="/settings" element={user ? <SettingsPage /> : <Navigate to="/login" />} />
          <Route path="/health" element={user ? <HealthPage /> : <Navigate to="/login" />} />
          <Route path="*" element={<Navigate to={user ? "/" : "/login"} />} />
        </Routes>
      </main>
    </>
  );
}
