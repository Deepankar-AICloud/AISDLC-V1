import { useEffect, useState } from "react";
import { api, errorText, setCsrf } from "../api";
import { Alert } from "../components/ui";
import { GitHubLogo, MicrosoftLogo } from "../components/Logos";

type DevUser = { username: string; roles: string[]; github_login: string };

const ERRORS: Record<string, string> = {
  signin_failed: "Sign-in failed. Try again.",
  no_role: "Your account has no portal role. Ask an administrator to assign Requester or Reviewer.",
};

const ACCENTS = ["red", "green", "blue", "yellow"] as const;

export function LoginPage({ onSignedIn }: { onSignedIn: () => Promise<void> }) {
  const [devUsers, setDevUsers] = useState<DevUser[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const errParam = new URLSearchParams(window.location.search).get("error");

  useEffect(() => {
    api<DevUser[]>("/auth/dev-users")
      .then(setDevUsers)
      .catch(() => setDevUsers(null));
  }, []);

  async function devLogin(username: string) {
    setBusy(username);
    try {
      const r = await api<{ csrf_token: string }>("/auth/dev-login", { json: { username } });
      setCsrf(r.csrf_token);
      window.history.replaceState(null, "", "/");
      await onSignedIn();
    } catch (e) {
      setError(errorText(e));
      setBusy("");
    }
  }

  return (
    <div className="login-page">
      <div className="login-blob blob-red" aria-hidden="true" />
      <div className="login-blob blob-green" aria-hidden="true" />
      <div className="login-blob blob-blue" aria-hidden="true" />
      <div className="login-blob blob-yellow" aria-hidden="true" />

      <main id="main" className="login-main">
        <section className="login-card" aria-labelledby="login-title">
          <div className="login-stripe" aria-hidden="true">
            {ACCENTS.map((c) => (
              <span key={c} className={`stripe-${c}`} />
            ))}
          </div>

          <div className="login-brand">
            <span className="brand-tile">
              <MicrosoftLogo size={34} />
            </span>
            <span className="brand-plus" aria-hidden="true">
              +
            </span>
            <span className="brand-tile brand-github">
              <GitHubLogo size={34} />
            </span>
          </div>

          <h1 id="login-title" className="login-title">
            AISDLC Portal
          </h1>
          <p className="login-subtitle">
            Turn business requirements into reviewed software. Submit ideas, answer questions and approve every stage,
            using your own identity.
          </p>

          {errParam && <Alert kind="error">{ERRORS[errParam] ?? "Sign-in failed."}</Alert>}
          {error && <Alert kind="error">{error}</Alert>}

          <a className="ms-button" href="/auth/login">
            <MicrosoftLogo />
            <span>Sign in with Microsoft</span>
          </a>

          <ol className="login-steps">
            <li>
              <span className="step-icon step-ms">
                <MicrosoftLogo size={16} />
              </span>
              <span>
                <strong>Sign in with your work account.</strong> Your organisation decides whether you are a Requester
                or a Reviewer.
              </span>
            </li>
            <li>
              <span className="step-icon step-gh">
                <GitHubLogo size={16} />
              </span>
              <span>
                <strong>Connect GitHub once.</strong> Answers, reviews and approvals then appear on GitHub under your
                own name.
              </span>
            </li>
          </ol>

          {devUsers && devUsers.length > 0 && (
            <div className="dev-panel">
              <h2>Development sign-in</h2>
              <p className="hint">Only available when the server runs in development mode on localhost.</p>
              <ul className="dev-users">
                {devUsers.map((u, i) => (
                  <li key={u.username}>
                    <button
                      type="button"
                      className={`dev-user accent-${ACCENTS[i % ACCENTS.length]}`}
                      onClick={() => devLogin(u.username)}
                      disabled={busy !== ""}
                      aria-label={`Sign in as ${u.username}`}
                    >
                      <span className="dev-avatar" aria-hidden="true">
                        {u.username.charAt(0).toUpperCase()}
                      </span>
                      <span className="dev-text">
                        <span className="dev-name">{busy === u.username ? "Signing in…" : u.username}</span>
                        <span className="dev-meta">
                          {u.roles.join(", ")} · <GitHubLogo size={11} /> {u.github_login}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
        <p className="login-footer">Secured by Microsoft Entra ID · Human approval stays human</p>
      </main>
    </div>
  );
}
