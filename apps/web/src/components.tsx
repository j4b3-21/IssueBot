import { useState } from "react";
import type { DisplayStatus, SourceItem } from "./types";

const STATUS_LABEL: Record<DisplayStatus, string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  awaiting_approval: "Awaiting approval",
  comment_published: "Comment published",
};

export function StatusBadge({ status }: { status: DisplayStatus }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-sm border border-line px-2 py-0.5">
      <StatusMark status={status} />
      {STATUS_LABEL[status] || status}
    </span>
  );
}

function StatusMark({ status }: { status: DisplayStatus }) {
  const common = { width: 12, height: 12, "aria-hidden": true as const };
  if (status === "queued") return <svg {...common}><circle cx="6" cy="6" r="4.5" fill="none" stroke="#1B2430" /></svg>;
  if (status === "running") return <svg {...common}><circle cx="6" cy="6" r="5" fill="#7C8B9A" /></svg>;
  if (status === "failed") return <svg {...common}><path d="M2 2 L10 10 M10 2 L2 10" stroke="#1B2430" /></svg>;
  if (status === "awaiting_approval") return <svg {...common}><path d="M6 1 L11 11 H1 Z" fill="none" stroke="#0E6B5C" /></svg>;
  if (status === "comment_published") return <svg {...common}><rect x="1" y="1" width="10" height="10" fill="#0E6B5C" /></svg>;
  return <svg {...common}><path d="M2 6 L5 9 L10 3" fill="none" stroke="#0E6B5C" /></svg>;
}

export function PageNotice({ children }: { children: string }) {
  return <p className="border border-line bg-sheet px-4 py-3">{children}</p>;
}

export function ExternalLink({ title, url }: { title: string; url: string }) {
  let host = url;
  try {
    host = new URL(url).hostname;
  } catch {
    return <span>{title}</span>;
  }
  return (
    <a className="text-mark underline" href={url} target="_blank" rel="noopener noreferrer">
      {title} ({host}, opens in a new tab)
    </a>
  );
}

export function SourceList({ sources }: { sources: SourceItem[] }) {
  if (sources.length === 0) return <p>No documentation source was returned.</p>;
  return (
    <ul className="space-y-3">
      {sources.map((source) => (
        <li key={`${source.title}-${source.url || "none"}`}>
          {source.linkable && source.url ? (
            <ExternalLink title={source.title} url={source.url} />
          ) : (
            <span>{source.title}</span>
          )}
          {source.snippet ? <p className="brief">{source.snippet}</p> : null}
        </li>
      ))}
    </ul>
  );
}

export function BriefBlock({ kind, text }: { kind: "fact" | "hypothesis" | "unknown" | "historical"; text: string }) {
  const label = {
    fact: "Documented fact",
    historical: "Historical evidence",
    hypothesis: "Hypothesis",
    unknown: "Unknown",
  }[kind];
  const rail = kind === "fact" || kind === "historical" ? "rail-fact" : kind === "hypothesis" ? "rail-hypothesis" : "";
  return (
    <div className={`mb-3 ${rail}`}>
      <p className="font-sans text-sm">{label}</p>
      <p className="brief">{text}</p>
    </div>
  );
}

export function PublishPanel({
  repo,
  issueNumber,
  preview,
  allowed,
  reason,
  onPublish,
}: {
  repo: string;
  issueNumber: number;
  preview: string;
  allowed: boolean;
  reason: string | null;
  onPublish: () => void;
}) {
  const [checked, setChecked] = useState(false);
  return (
    <section className="border border-line bg-sheet p-4" aria-labelledby="publish-heading">
      <h2 id="publish-heading" className="mb-2 text-lg font-semibold">
        What will be published
      </h2>
      <p className="mb-2">
        Target {repo}#{issueNumber}
      </p>
      <pre className="mb-3 max-h-64 overflow-auto whitespace-pre-wrap border border-line p-3 font-sans text-sm">
        {preview}
      </pre>
      {reason ? <p id="publish-reason">{reason}</p> : null}
      {!checked && allowed ? <p>Check the review box before publishing.</p> : null}
      <label className="mb-3 flex items-start gap-2">
        <input id="publish-ack" type="checkbox" disabled={!allowed} checked={checked} onChange={(event) => setChecked(event.target.checked)} />
        <span>I have reviewed this comment and the target {repo}#{issueNumber}</span>
      </label>
      <button
        type="button"
        className="bg-mark px-3 py-2 text-white disabled:opacity-50"
        disabled={!allowed || !checked}
        onClick={onPublish}
      >
        Publish comment on {repo}#{issueNumber}
      </button>
    </section>
  );
}
