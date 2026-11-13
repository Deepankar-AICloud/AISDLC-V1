import { useRef, useState, type DragEvent } from "react";
import { formatBytes } from "./ui";

export type LocalFile = { key: string; file: File; problem: string | null };

export function checkFile(file: File, allowed: string[], maxMb: number): string | null {
  const dot = file.name.lastIndexOf(".");
  const ext = dot >= 0 ? file.name.slice(dot).toLowerCase() : "";
  if (!allowed.includes(ext)) return `File type ${ext || "(none)"} is not allowed.`;
  if (file.size === 0) return "The file is empty.";
  if (file.size > maxMb * 1024 * 1024) return `Larger than the ${maxMb} MB per-file limit.`;
  return null;
}

export function Dropzone({
  files,
  onChange,
  allowed,
  maxFiles,
  maxMb,
}: {
  files: LocalFile[];
  onChange: (files: LocalFile[]) => void;
  allowed: string[];
  maxFiles: number;
  maxMb: number;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [active, setActive] = useState(false);

  function add(list: FileList | null) {
    if (!list) return;
    const next = [...files];
    for (const f of Array.from(list)) {
      if (next.length >= maxFiles) break;
      next.push({
        key: `${f.name}-${f.size}-${f.lastModified}-${Math.random()}`,
        file: f,
        problem: checkFile(f, allowed, maxMb),
      });
    }
    onChange(next);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setActive(false);
    add(e.dataTransfer.files);
  }

  return (
    <div>
      <div
        className={`dropzone${active ? " active" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setActive(true);
        }}
        onDragLeave={() => setActive(false)}
        onDrop={onDrop}
      >
        <p>Drag and drop files here, or</p>
        <button type="button" className="secondary" onClick={() => input.current?.click()}>
          Choose files
        </button>
        <input
          ref={input}
          id="file-input"
          type="file"
          multiple
          accept={allowed.join(",")}
          className="sr-only"
          aria-label="Upload documents"
          onChange={(e) => {
            add(e.target.files);
            e.target.value = "";
          }}
        />
        <p className="hint">
          {allowed.join(", ")} · up to {maxFiles} files · {maxMb} MB each
        </p>
      </div>
      {files.length > 0 && (
        <ul aria-label="Selected files">
          {files.map((f) => (
            <li key={f.key}>
              {f.file.name} <span className="muted">({formatBytes(f.file.size)})</span>{" "}
              {f.problem && <span className="badge danger">{f.problem}</span>}{" "}
              <button
                type="button"
                className="secondary"
                aria-label={`Remove ${f.file.name}`}
                onClick={() => onChange(files.filter((x) => x.key !== f.key))}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
