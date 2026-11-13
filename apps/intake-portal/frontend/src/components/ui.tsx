import { useEffect, useRef, type ReactNode } from "react";

export function Alert({
  kind,
  title,
  children,
}: {
  kind: "info" | "warn" | "error" | "ok";
  title?: string;
  children?: ReactNode;
}) {
  return (
    <div className={`alert ${kind}`} role={kind === "error" ? "alert" : "status"}>
      {title && <strong>{title}</strong>}
      {title && children ? <div>{children}</div> : children}
    </div>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <p role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" /> {label}
    </p>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="card muted">{children}</div>;
}

const STATUS: Record<string, { label: string; tone: "" | "ok" | "warn" | "danger" }> = {
  submitting: { label: "Submitting", tone: "" },
  submit_failed: { label: "Submit failed", tone: "danger" },
  submitted: { label: "Submitted", tone: "" },
  queued: { label: "Queued (waiting for CodeQL)", tone: "" },
  running: { label: "Running", tone: "" },
  awaiting_info: { label: "Needs information", tone: "warn" },
  awaiting_model: { label: "Model confirmation needed", tone: "warn" },
  in_review: { label: "Stage in review", tone: "warn" },
  needs_attention: { label: "Paused (QC)", tone: "danger" },
  complete: { label: "Complete", tone: "ok" },
  closed: { label: "Closed", tone: "" },
};

export function StatusBadge({ status }: { status: string }) {
  const s = STATUS[status] ?? { label: status, tone: "" };
  return <span className={`badge ${s.tone}`}>{s.label}</span>;
}

export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  confirmDisabled,
  busy,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  confirmDisabled?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} aria-labelledby="confirm-title" onCancel={onCancel}>
      <h2 id="confirm-title">{title}</h2>
      {children}
      <div className="actions">
        <button type="button" onClick={onConfirm} disabled={confirmDisabled || busy}>
          {busy ? "Working…" : confirmLabel}
        </button>
        <button type="button" className="secondary" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
      </div>
    </dialog>
  );
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}
