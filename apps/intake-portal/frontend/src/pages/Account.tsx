import { useState } from "react";
import { api, errorText } from "../api";
import { useMe } from "../App";
import { Alert } from "../components/ui";

const REASONS: Record<string, string> = {
  already_linked:
    "That GitHub account is already linked to another portal user. Each GitHub account can be linked once.",
  different_account: "You are already linked to a different GitHub account. Disconnect it first.",
  state: "The connection request expired or did not match. Try again.",
  exchange: "GitHub did not accept the connection. Try again.",
  session: "Your portal session ended. Sign in and try again.",
};

export function AccountPage() {
  const { me, reload } = useMe();
  const [error, setError] = useState("");
  const params = new URLSearchParams(window.location.search);
  const result = params.get("github");
  const reason = params.get("reason") ?? "";

  async function disconnect() {
    try {
      await api("/api/github/disconnect", { method: "POST" });
      await reload();
    } catch (e) {
      setError(errorText(e));
    }
  }

  return (
    <>
      <h1>Account</h1>
      {result === "connected" && <Alert kind="ok">GitHub connected.</Alert>}
      {result === "error" && <Alert kind="error">{REASONS[reason] ?? "GitHub connection failed."}</Alert>}
      {error && <Alert kind="error">{error}</Alert>}
      <div className="card">
        <h2>Portal identity</h2>
        <p>
          {me.user.name} ({me.user.email}) · roles: {me.user.roles.join(", ") || "none"}
        </p>
      </div>
      <div className="card">
        <h2>GitHub</h2>
        <p>
          Answers, reviews, approvals and AISDLC commands are posted with <strong>your own</strong> GitHub account, so
          GitHub shows your name and applies branch protection and CODEOWNERS. The portal never uses a shared account
          for them.
        </p>
        {me.github.connected ? (
          <>
            <p>
              Connected as <strong>{me.github.login}</strong>.
            </p>
            {me.user.sign_in === "github" ? (
              <p className="hint">You signed in with GitHub, so this connection is your identity. Sign out to leave.</p>
            ) : (
              <button type="button" className="secondary" onClick={disconnect}>
                Disconnect GitHub
              </button>
            )}
          </>
        ) : (
          <a className="button" href="/auth/github/connect">
            {me.github.needs_reconnect ? "Reconnect GitHub" : "Connect GitHub"}
          </a>
        )}
      </div>
    </>
  );
}
