import { useEffect, useState } from "react";
import { api, errorText, setCsrf } from "../api";
import { Alert } from "../components/ui";

type DevUser = { username: string; roles: string[]; github_login: string };

const ERRORS: Record<string, string> = {
  signin_failed: "Sign-in failed. Try again.",
  no_role: "Your account has no portal role. Ask an administrator to assign Requester or Reviewer.",
};

export function LoginPage({ onSignedIn }: { onSignedIn: () => Promise<void> }) {
  const [devUsers, setDevUsers] = useState<DevUser[] | null>(null);
  const [error, setError] = useState("");
  const params = new URLSearchParams(window.location.search);
  const errParam = params.get("error");

  useEffect(() => {
    api<DevUser[]>("/auth/dev-users")
      .then(setDevUsers)
      .catch(() => setDevUsers(null));
  }, []);

  async function devLogin(username: string) {
    try {
      const r = await api<{ csrf_token: string }>("/auth/dev-login", { json: { username } });
      setCsrf(r.csrf_token);
      window.history.replaceState(null, "", "/");
      await onSignedIn();
    } catch (e) {
      setError(errorText(e));
    }
  }

  return (
    <main id="main">
      <h1>AISDLC Portal</h1>
      <p>Submit requirements to AISDLC and review each stage, using your own identity.</p>
      {errParam && <Alert kind="error">{ERRORS[errParam] ?? "Sign-in failed."}</Alert>}
      {error && <Alert kind="error">{error}</Alert>}
      <div className="card">
        <a className="button" href="/auth/login">
          Sign in with Microsoft
        </a>
      </div>
      {devUsers && devUsers.length > 0 && (
        <div className="card">
          <h2>Development sign-in</h2>
          <p className="hint">Only available when the server runs in development mode on localhost.</p>
          <ul>
            {devUsers.map((u) => (
              <li key={u.username} style={{ marginBottom: "0.5rem" }}>
                <button type="button" className="secondary" onClick={() => devLogin(u.username)}>
                  Sign in as {u.username}
                </button>{" "}
                <span className="muted">
                  {u.roles.join(", ")} · GitHub {u.github_login}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </main>
  );
}
