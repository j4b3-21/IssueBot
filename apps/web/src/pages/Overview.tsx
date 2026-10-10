import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api } from "../api";
import { PageNotice, StatusBadge } from "../components";
import type { InvestigationSummary } from "../types";

interface Overview {
  counts: Record<string, number>;
  recent: InvestigationSummary[];
  failed: InvestigationSummary[];
}

export function OverviewPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Overview>("/api/v1/overview")
      .then(setData)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "The overview could not be loaded."));
  }, []);

  if (error) return <PageNotice>{error}</PageNotice>;
  if (!data) return <p>Loading investigations.</p>;

  return (
    <>
      <h1 tabIndex={-1} className="mb-4 text-2xl font-semibold">
        Overview
      </h1>
      <div className="mb-6 grid gap-3 sm:grid-cols-3">
        <Count label="Needs attention" value={data.counts.failed || 0} />
        <Count label="Running" value={data.counts.running || 0} />
        <Count label="Awaiting approval" value={data.counts.awaiting_approval || 0} />
      </div>
      <h2 className="mb-2 text-lg font-semibold">Recent investigations</h2>
      {data.recent.length === 0 ? (
        <PageNotice>No investigations yet. Allow a repository in Settings, then open a GitHub issue. In demo mode, load a sample issue from Settings.</PageNotice>
      ) : (
        <InvestigationRows items={data.recent} />
      )}
      <h2 className="mt-6 mb-2 text-lg font-semibold">Failed jobs</h2>
      {data.failed.length === 0 ? <p>No failed jobs.</p> : <InvestigationRows items={data.failed} />}
    </>
  );
}

function Count({ label, value }: { label: string; value: number }) {
  return (
    <div className="border border-line bg-sheet px-4 py-3">
      <p className="text-2xl font-semibold">{value}</p>
      <p>{label}</p>
    </div>
  );
}

function InvestigationRows({ items }: { items: InvestigationSummary[] }) {
  return (
    <ul className="divide-y divide-line border border-line bg-sheet">
      {items.map((item) => (
        <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
          <Link to={`/investigations/${item.id}`}>
            {item.repo_full_name}#{item.issue_number} {item.issue_title}
          </Link>
          <StatusBadge status={item.display_status} />
        </li>
      ))}
    </ul>
  );
}
