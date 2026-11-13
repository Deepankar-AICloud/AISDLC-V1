import { useEffect, useState } from "react";
import { api, errorText, setCsrf } from "../api";
import { Alert } from "../components/ui";
import { GitHubLogo, MicrosoftLogo } from "../components/Logos";

type DevUser = { username: string; roles: string[]; github_login: string };
type Options = { microsoft: boolean; github: boolean; dev: boolean };

const ERRORS: Record<string, string> = {
  signin_failed: "Sign-in failed. Try again.",
  no_role: "Your account has no portal role. Ask an administrator to assign Requester or Reviewer.",
  github_disabled: "GitHub sign-in is not enabled on this server.",
  github_no_access:
    "Your GitHub account doesn't have access to the AISDLC repository yet. Ask a repository admin to add you (triage access or more), then try again.",
  github_linked_to_microsoft:
    "That GitHub account is linked to a Microsoft work account. Sign in with Microsoft instead.",
};

const ACCENTS = ["red", "green", "blue", "yellow"] as const;

export function LoginPage({ onSignedIn }: { onSignedIn: () => Promise<void> }) {
  const [options, setOptions] = useState<Options | null>(null);
  const [devUsers, setDevUsers] = useState<DevUser[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const errParam = new URLSearchParams(window.location.search).get("error");

  useEffect(() => {
    api<Options>("/auth/options")
      .then((o) => {
        setOptions(o);
        if (o.dev)
          api<DevUser[]>("/auth/dev-users")
            .then(setDevUsers)
            .catch(() => setDevUsers(null));
      })
      .catch(() => setOptions({ microsoft: true, github: false, dev: false }));
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

          <a
            className={`ms-button${options && !options.microsoft ? " is-unavailable" : ""}`}
            href={options && !options.microsoft ? undefined : "/auth/login"}
            aria-disabled={options ? !options.microsoft : undefined}
          >
            <MicrosoftLogo />
            <span>Sign in with Microsoft</span>
          </a>
          {options && !options.microsoft && (
            <p className="login-note">Microsoft sign-in isn't configured on this server yet.</p>
          )}

          {options?.github && (
            <>
              <div className="login-divider" role="separator">
                <span>New here? Use your GitHub account</span>
              </div>
              <a className="gh-button" href="/auth/github/login">
                <GitHubLogo size={20} />
                <span>Sign in with GitHub</span>
              </a>
              <p className="login-note">
                For people without a work account. You need access to the AISDLC repository on GitHub; your role there
                decides what you can do in the portal.
              </p>
            </>
          )}

          <ol className="login-steps">
            <li>
              <span className="step-icon step-ms">
                <MicrosoftLogo size={16} />
              </span>
              <span>
                <strong>Sign in{options?.github ? " with Microsoft or GitHub" : " with your work account"}.</strong>{" "}
                Your organisation, or your GitHub repository access, decides whether you are a Requester or a Reviewer.
              </span>
            </li>
            <li>
              <span className="step-icon step-gh">
                <GitHubLogo size={16} />
              </span>
              <span>
                <strong>Your GitHub identity is used for every action.</strong> Answers, reviews and approvals appear on
                GitHub under your own name.
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
                        <span className="dev-meta">{u.roles.join(", ")}</span>
                        <span className="dev-meta">
                          <GitHubLogo size={11} /> {u.github_login}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
        <p className="login-footer">Secured by Microsoft Entra ID and GitHub · Human approval stays human</p>
      </main>
    </div>
  );
}
