import { useEffect, useState } from "react";
import { api, errorText, setCsrf } from "../api";
import { Alert } from "../components/ui";
import { GitHubLogo, MicrosoftLogo } from "../components/Logos";

type DevUser = { username: string; roles: string[]; github_login: string };
type Options = { microsoft: boolean; github: boolean; dev: boolean; password: boolean };

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
            .catch((e) => setError(errorText(e)));
      })
      .catch((e) => setError(errorText(e)));
  }, []);

  const [formUser, setFormUser] = useState("");
  const [formPass, setFormPass] = useState("");

  async function signIn(username: string, password = "") {
    setBusy(username);
    setError("");
    try {
      const r = await api<{ csrf_token: string }>(options?.password ? "/auth/password-login" : "/auth/dev-login", {
        json: { username, password },
      });
      setFormPass("");
      setCsrf(r.csrf_token);
      window.history.replaceState(null, "", "/");
      await onSignedIn();
    } catch (e) {
      setError(errorText(e));
      setBusy("");
    }
  }

  const passwordForm = (
    <form
      className="dev-panel dev-password-form"
      onSubmit={(e) => {
        e.preventDefault();
        void signIn(formUser.trim(), formPass);
      }}
    >
      <h2>Sign in with username and password</h2>
      <p className="hint">
        {options?.password
          ? "Submit requirements and view generated documents. No personal GitHub or Microsoft account is needed."
          : "For people without a GitHub or Microsoft account. Development mode only."}
      </p>
      <label>
        Username
        <input autoComplete="username" value={formUser} onChange={(e) => setFormUser(e.target.value)} required />
      </label>
      <label>
        Password
        <input
          type="password"
          autoComplete="current-password"
          value={formPass}
          onChange={(e) => setFormPass(e.target.value)}
          required
        />
      </label>
      <button type="submit" disabled={busy !== ""}>
        {busy && busy === formUser.trim() ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );

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
            {options?.password
              ? "Turn business requirements into reviewed software. Upload your requirements and follow your GitHub Actions pipeline."
              : "Turn business requirements into reviewed software. Submit ideas, answer questions and approve every stage, using your own identity."}
          </p>

          {errParam && <Alert kind="error">{ERRORS[errParam] ?? "Sign-in failed."}</Alert>}
          {error && <Alert kind="error">{error}</Alert>}

          {options?.password && passwordForm}
          {options?.password && (options.microsoft || options.github) && (
            <div className="login-divider" role="separator">
              <span>Reviewer sign-in</span>
            </div>
          )}
          {(!options?.password || options.microsoft) && (
            <a
              className={`ms-button${options && !options.microsoft ? " is-unavailable" : ""}`}
              href={options && !options.microsoft ? undefined : "/auth/login"}
              aria-disabled={options ? !options.microsoft : undefined}
            >
              <MicrosoftLogo />
              <span>Sign in with Microsoft</span>
            </a>
          )}
          {options && !options.password && !options.microsoft && (
            <p className="login-note">Microsoft sign-in isn't configured on this server yet.</p>
          )}

          {options?.github && (
            <>
              {!options.password && (
                <div className="login-divider" role="separator">
                  <span>New here? Use your GitHub account</span>
                </div>
              )}
              <a className="gh-button" href="/auth/github/login">
                <GitHubLogo size={20} />
                <span>Sign in with GitHub</span>
              </a>
              <p className="login-note">
                {options.password
                  ? "Reviewers use their own GitHub account. Repository permissions and approval protections still apply."
                  : "For people without a work account. You need access to the AISDLC repository on GitHub; your role there decides what you can do in the portal."}
              </p>
            </>
          )}

          <ol className="login-steps">
            <li>
              <span className="step-icon step-ms">
                <MicrosoftLogo size={16} />
              </span>
              <span>
                {options?.password ? (
                  <>
                    <strong>Upload a requirement.</strong> The backend creates the GitHub issue and starts AISDLC.
                  </>
                ) : (
                  <>
                    <strong>Sign in{options?.github ? " with Microsoft or GitHub" : " with your work account"}.</strong>{" "}
                    Your organisation, or your GitHub repository access, decides whether you are a Requester or a
                    Reviewer.
                  </>
                )}
              </span>
            </li>
            <li>
              <span className="step-icon step-gh">
                <GitHubLogo size={16} />
              </span>
              <span>
                {options?.password ? (
                  <>
                    <strong>Human approval stays human.</strong> Named reviewers answer questions, confirm models and
                    approve each stage with their own GitHub identity.
                  </>
                ) : (
                  <>
                    <strong>Your GitHub identity is used for every action.</strong> Answers, reviews and approvals
                    appear on GitHub under your own name.
                  </>
                )}
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
                      onClick={() => signIn(u.username)}
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

          {options?.dev && passwordForm}
        </section>
        <p className="login-footer">
          {options?.password
            ? "Server-side sign-in · GitHub Actions · Human approval stays human"
            : "Secured by Microsoft Entra ID and GitHub · Human approval stays human"}
        </p>
      </main>
    </div>
  );
}
