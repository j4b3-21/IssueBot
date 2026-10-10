import { useEffect, useState } from "react";
import { ApiError, api } from "../api";
import { PageNotice } from "../components";
import type { HealthView } from "../types";

export function HealthPage() {
  const [health, setHealth] = useState<HealthView | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<HealthView>("/api/v1/health")
      .then(setHealth)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Health could not be loaded."));
  }, []);

  if (error) return <PageNotice>{error}</PageNotice>;
  if (!health) return <p>Loading health.</p>;

  return (
    <>
      <h1 tabIndex={-1} className="mb-4 text-2xl font-semibold">
        Health
      </h1>
      <dl className="grid max-w-md grid-cols-2 gap-2 border border-line bg-sheet p-4">
        <dt>API</dt>
        <dd>{health.api}</dd>
        <dt>Database</dt>
        <dd>{health.database}</dd>
        <dt>Worker</dt>
        <dd>{health.worker}</dd>
        <dt>DocsGPT</dt>
        <dd>{health.docsgpt}</dd>
        <dt>GitHub</dt>
        <dd>{health.github}</dd>
        <dt>Publishing</dt>
        <dd>{health.publish_enabled ? "Enabled" : "Off"}</dd>
      </dl>
    </>
  );
}
