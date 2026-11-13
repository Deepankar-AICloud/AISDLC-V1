import { useEffect, useId, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Raw HTML in artifacts is not rendered (react-markdown escapes it by default).
// Mermaid runs with securityLevel "strict", which sanitises labels and disables click handlers.

function Mermaid({ code }: { code: string }) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [svg, setSvg] = useState<string>("");
  const [error, setError] = useState<string>("");
  useEffect(() => {
    let alive = true;
    import("mermaid")
      .then(async ({ default: mermaid }) => {
        mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "default" });
        const out = await mermaid.render(`m${id}`, code);
        if (alive) setSvg(out.svg);
      })
      .catch(() => alive && setError("This diagram could not be rendered; the source is shown instead."));
    return () => {
      alive = false;
    };
  }, [code, id]);
  if (error)
    return (
      <>
        <p className="muted">{error}</p>
        <pre>{code}</pre>
      </>
    );
  if (!svg) return <p className="muted">Rendering diagram…</p>;
  return (
    <figure className="mermaid-box" aria-label="Diagram">
      <div dangerouslySetInnerHTML={{ __html: svg }} />
      <details>
        <summary>Diagram source</summary>
        <pre>{code}</pre>
      </details>
    </figure>
  );
}

export function Markdown({ source }: { source: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children, ...rest }) {
            const lang = /language-(\w+)/.exec(className ?? "")?.[1];
            const text = String(children).replace(/\n$/, "");
            if (lang === "mermaid") return <Mermaid code={text} />;
            return (
              <code className={className} {...rest}>
                {children}
              </code>
            );
          },
          a({ href, children }) {
            return (
              <a href={href} rel="noopener noreferrer nofollow" target="_blank">
                {children}
              </a>
            );
          },
          img({ alt }) {
            return <span className="muted">[image: {alt || "not displayed"}]</span>;
          },
        }}
      >
        {source}
      </ReactMarkdown>
    </div>
  );
}

export function Diff({ patch }: { patch: string }) {
  if (!patch) return <p className="muted">No textual diff (binary or too large).</p>;
  return (
    <pre className="diff">
      {patch.split("\n").map((line, i) => {
        const cls = line.startsWith("@@") ? "hunk" : line.startsWith("+") ? "add" : line.startsWith("-") ? "del" : "";
        return (
          <span key={i} className={cls}>
            {line || " "}
            {"\n"}
          </span>
        );
      })}
    </pre>
  );
}
