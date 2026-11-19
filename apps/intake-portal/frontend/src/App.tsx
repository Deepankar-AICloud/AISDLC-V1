import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { BrowserRouter, NavLink, Navigate, Route, Routes } from "react-router-dom";
import { api, ApiError, errorText, setCsrf } from "./api";
import { Alert, Loading } from "./components/ui";
import type { Me } from "./types";
import { AccountPage } from "./pages/Account";
import { LoginPage } from "./pages/Login";
import { NewRequestPage } from "./pages/NewRequest";
import { ProductionPage } from "./pages/Production";
import { RequestDetailPage } from "./pages/RequestDetail";
import { RequestsPage } from "./pages/Requests";
import { StageReviewPage } from "./pages/StageReview";

type MeState = { me: Me; reload: () => Promise<void> };
const MeContext = createContext<MeState | null>(null);

export function useMe(): MeState {
  const ctx = useContext(MeContext);
  if (!ctx) throw new Error("useMe outside provider");
  return ctx;
}

export function isReviewer(me: Me): boolean {
  return me.user.roles.includes(me.config.reviewer_role);
}

export function isRequester(me: Me): boolean {
  return me.user.roles.includes(me.config.requester_role);
}

function Layout({ me, children }: { me: Me; children: React.ReactNode }) {
  async function logout() {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    window.location.assign("/login");
  }
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="app-header">
        <div className="header-inner">
          <a className="brand" href="/">
            AISDLC Portal
          </a>
          <nav aria-label="Main">
            <ul>
              {isRequester(me) && (
                <li>
                  <NavLink to="/new">New request</NavLink>
                </li>
              )}
              <li>
                <NavLink to="/requests" end>
                  Requests
                </NavLink>
              </li>
              {isReviewer(me) && (
                <li>
                  <NavLink to="/production">Production</NavLink>
                </li>
              )}
              <li>
                <NavLink to="/account">Account</NavLink>
              </li>
            </ul>
          </nav>
          <div className="header-user">
            {me.user.sign_in !== "password" && (
              <span>
                {me.user.name} · {me.user.roles.join(", ")}
                {me.github.connected ? ` · GitHub: ${me.github.login}` : " · GitHub not connected"}
              </span>
            )}
            {me.config.auth_mode !== "open" && (
              <button type="button" className="secondary" onClick={logout}>
                Sign out
              </button>
            )}
          </div>
        </div>
      </header>
      <main id="main" tabIndex={-1}>
        {me.config.github_mode === "fake" && (
          <Alert kind="info">Development mode: GitHub is simulated. Nothing is sent to a real repository.</Alert>
        )}
        {me.github.needs_reconnect && (
          <Alert kind="warn" title="Your GitHub connection expired.">
            <a href="/account">Reconnect GitHub</a> to answer questions or review stages.
          </Alert>
        )}
        {children}
      </main>
    </>
  );
}

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [state, setState] = useState<"loading" | "anon" | "error" | "ready">("loading");
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    const loadMe = async () => {
      const m = await api<Me>("/api/me");
      setCsrf(m.csrf_token);
      setMe(m);
      setState("ready");
    };
    try {
      await loadMe();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        try {
          const options = await api<{ open?: boolean }>("/auth/options");
          if (options.open) {
            const r = await api<{ csrf_token: string }>("/auth/open-session", { method: "POST" });
            setCsrf(r.csrf_token);
            await loadMe();
            return;
          }
          setState("anon");
        } catch (inner) {
          setError(errorText(inner));
          setState("error");
        }
      } else {
        setError(errorText(e));
        setState("error");
      }
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  if (state === "loading")
    return (
      <main>
        <Loading />
      </main>
    );
  if (state === "error")
    return (
      <main>
        <Alert kind="error" title="The portal could not load.">
          {error}
        </Alert>
      </main>
    );
  if (state === "anon" || !me)
    return (
      <BrowserRouter>
        <Routes>
          <Route path="*" element={<LoginPage onSignedIn={reload} />} />
        </Routes>
      </BrowserRouter>
    );

  return (
    <MeContext.Provider value={{ me, reload }}>
      <BrowserRouter>
        <Layout me={me}>
          <Routes>
            <Route path="/" element={<Navigate to={isRequester(me) ? "/new" : "/requests"} replace />} />
            <Route path="/login" element={<Navigate to="/" replace />} />
            <Route path="/new" element={<NewRequestPage />} />
            <Route path="/requests" element={<RequestsPage />} />
            <Route path="/requests/:id" element={<RequestDetailPage />} />
            <Route path="/requests/:id/stages/:pr" element={<StageReviewPage />} />
            <Route path="/production" element={<ProductionPage />} />
            <Route path="/account" element={<AccountPage />} />
            <Route path="*" element={<Alert kind="info">Page not found.</Alert>} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </MeContext.Provider>
  );
}
