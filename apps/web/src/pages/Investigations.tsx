import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api } from "../api";
import { PageNotice, StatusBadge } from "../components";
import type { InvestigationSummary } from "../types";

export function InvestigationsPage() {
  const [items, setItems] = useState<InvestigationSummary[] | null>(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const limit = 20;

  function load(nextOffset: number, nextFilters: Record<string, string>) {
    const params = new URLSearchParams({ limit: String(limit), offset: String(nextOffset) });
    for (const [key, value] of Object.entries(nextFilters)) {
      if (value) params.set(key, value);
    }
    api<{ items: InvestigationSummary[]; total: number }>(`/api/v1/investigations?${params}`)
      .then((page) => {
        setItems(page.items);
        setTotal(page.total);
        setError("");
      })
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "The list could not be loaded."));
  }

  useEffect(() => {
    load(0, {});
  }, []);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const next = {
      q: String(data.get("q") || ""),
      repo: String(data.get("repo") || ""),
      status: String(data.get("status") || ""),
      issue_number: String(data.get("issue_number") || ""),
      created_from: String(data.get("created_from") || ""),
      created_to: String(data.get("created_to") || ""),
    };
    setFilters(next);
    setOffset(0);
    load(0, next);
  }

  const page = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(total / limit));

  return (
    <>
      <h1 tabIndex={-1} className="mb-4 text-2xl font-semibold">
        Investigations
      </h1>
      <form className="mb-4 grid gap-2 sm:grid-cols-3" onSubmit={onSubmit}>
        <label htmlFor="q">
          Search titles
          <input id="q" name="q" className="mt-1 w-full border border-line px-2 py-1" />
        </label>
        <label htmlFor="repo">
          Repository
          <input id="repo" name="repo" placeholder="owner/name" className="mt-1 w-full border border-line px-2 py-1" />
        </label>
        <label htmlFor="issue_number">
          Issue number
          <input id="issue_number" name="issue_number" inputMode="numeric" className="mt-1 w-full border border-line px-2 py-1" />
        </label>
        <label htmlFor="status">
          Status
          <select id="status" name="status" className="mt-1 w-full border border-line bg-sheet px-2 py-1">
            <option value="">Any</option>
            <option value="queued">Queued</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="awaiting_approval">Awaiting approval</option>
            <option value="comment_published">Comment published</option>
          </select>
        </label>
        <label htmlFor="created_from">
          Created from
          <input id="created_from" name="created_from" type="date" className="mt-1 w-full border border-line px-2 py-1" />
        </label>
        <label htmlFor="created_to">
          Created to
          <input id="created_to" name="created_to" type="date" className="mt-1 w-full border border-line px-2 py-1" />
        </label>
        <button className="self-end border border-line px-3 py-1" type="submit">
          Search
        </button>
      </form>
      {error ? <PageNotice>{error}</PageNotice> : null}
      {items === null ? <p>Loading investigations.</p> : null}
      {items && items.length === 0 ? <PageNotice>No investigations match this search.</PageNotice> : null}
      {items && items.length > 0 ? (
        <table className="responsive w-full border-collapse bg-sheet">
          <caption className="sr-only">Investigations</caption>
          <thead>
            <tr className="border-b border-line text-left">
              <th scope="col" className="p-2">Issue</th>
              <th scope="col" className="p-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-b border-line">
                <td className="p-2">
                  <Link to={`/investigations/${item.id}`}>
                    {item.repo_full_name}#{item.issue_number} {item.issue_title}
                  </Link>
                </td>
                <td className="p-2">
                  <StatusBadge status={item.display_status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      <p className="mt-3">
        Page {page} of {pages}
      </p>
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          disabled={offset === 0}
          onClick={() => {
            const next = Math.max(0, offset - limit);
            setOffset(next);
            load(next, filters);
          }}
        >
          Previous page
        </button>
        <button
          type="button"
          disabled={offset + limit >= total}
          onClick={() => {
            const next = offset + limit;
            setOffset(next);
            load(next, filters);
          }}
        >
          Next page
        </button>
      </div>
    </>
  );
}
