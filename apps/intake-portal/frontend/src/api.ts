// Thin fetch wrapper. Session is an HttpOnly cookie; the CSRF token is sent on writes.
// GitHub tokens never reach the browser: every GitHub call is made by the server.

let csrfToken = "";

export function setCsrf(token: string | null | undefined): void {
  csrfToken = token ?? "";
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: Record<string, unknown> = {},
  ) {
    super(message);
  }

  get reasons(): string[] {
    const r = this.details["reasons"];
    return Array.isArray(r) ? r.map(String) : [];
  }

  get correlationId(): string {
    return String(this.details["correlation_id"] ?? "");
  }
}

type Options = {
  method?: string;
  json?: unknown;
  form?: FormData;
  headers?: Record<string, string>;
  signal?: AbortSignal;
};

export async function parseError(res: Response): Promise<ApiError> {
  let body: { error?: { code?: string; message?: string } & Record<string, unknown> } = {};
  try {
    body = await res.json();
  } catch {
    // non-JSON error
  }
  const err = body.error ?? {};
  const { code, message, ...rest } = err;
  return new ApiError(res.status, code ?? "http_error", message ?? `The server returned ${res.status}.`, rest);
}

export async function api<T>(path: string, opts: Options = {}): Promise<T> {
  const method = opts.method ?? (opts.json !== undefined || opts.form ? "POST" : "GET");
  const headers: Record<string, string> = { Accept: "application/json", ...(opts.headers ?? {}) };
  let body: BodyInit | undefined;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    body = opts.form;
  }
  if (method !== "GET" && csrfToken) headers["X-CSRF-Token"] = csrfToken;
  let res: Response;
  try {
    res = await fetch(path, { method, headers, body, credentials: "same-origin", signal: opts.signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "network", "Could not reach the portal. Check your connection and try again.");
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    const ref = e.correlationId ? ` (reference ${e.correlationId})` : "";
    return e.message + ref;
  }
  return "Something went wrong.";
}
