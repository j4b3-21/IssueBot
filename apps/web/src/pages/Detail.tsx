import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, api } from "../api";
import { BriefBlock, ExternalLink, PageNotice, PublishPanel, SourceList, StatusBadge } from "../components";
import type { InvestigationDetail } from "../types";

export function DetailPage() {
  const { id } = useParams();
  const [item, setItem] = useState<InvestigationDetail | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  function load() {
    api<InvestigationDetail>(`/api/v1/investigations/${id}`)
      .then((next) => {
        setItem((current) => {
          if (current && current.display_status !== next.display_status) {
            setNotice(`Investigation ${next.display_status.replaceAll("_", " ")}`);
          }
          return next;
        });
        setError("");
      })
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "The investigation could not be loaded."));
  }

  useEffect(() => {
    load();
  }, [id]);

  useEffect(() => {
    if (!item || (item.status !== "queued" && item.status !== "running")) return;
    const timer = window.setInterval(load, 2000);
    return () => window.clearInterval(timer);
  }, [item?.status, id]);

  if (error) return <PageNotice>{error}</PageNotice>;
  if (!item) return <p>Loading investigation.</p>;
  const report = item.report;

  return (
    <>
      <p className="mb-2">
        <Link to="/investigations">Investigations</Link>
      </p>
      <h1 tabIndex={-1} className="mb-2 text-2xl font-semibold">
        {item.repo_full_name}#{item.issue_number} {item.issue_title}
      </h1>
      <p aria-live="polite" className="mb-3">
        <StatusBadge status={item.display_status} /> {notice}
      </p>
      {item.mock || item.actions.demo_mode ? <PageNotice>Demo data. Nothing is published to GitHub.</PageNotice> : null}
      {item.error_message ? <PageNotice>{item.error_message}</PageNotice> : null}
      <p className="my-3">
        <ExternalLink title="Open the GitHub issue" url={item.issue_url} />
      </p>
      <p className="brief mb-6">{item.issue_body}</p>
      {!report ? <p aria-busy="true">The investigation is still running.</p> : null}
      {report ? (
        <>
          <p className="mb-4">This is an AI-generated suggestion, not a confirmed diagnosis. {report.evidence_note}</p>
          <h2 className="text-lg font-semibold">Summary</h2>
          <p className="brief mb-4">{report.summary}</p>
          <h2 className="text-lg font-semibold">Documented facts</h2>
          {report.documented_facts.length === 0 ? <p>No documented fact was established.</p> : report.documented_facts.map((text) => <BriefBlock key={text} kind="fact" text={text} />)}
          <h2 className="mt-4 text-lg font-semibold">Historical evidence</h2>
          {report.historical_evidence.length === 0 ? (
            <p>No related issues were retrieved.</p>
          ) : (
            report.historical_evidence.map((entry) => <BriefBlock key={entry.url} kind="historical" text={entry.text} />)
          )}
          <h2 className="mt-4 text-lg font-semibold">Hypotheses</h2>
          {report.hypotheses.length === 0 ? <p>No hypothesis was recorded.</p> : report.hypotheses.map((text) => <BriefBlock key={text} kind="hypothesis" text={text} />)}
          <h2 className="mt-4 text-lg font-semibold">Unknowns</h2>
          {report.unknowns.map((text) => (
            <BriefBlock key={text} kind="unknown" text={text} />
          ))}
          <h2 className="mt-4 text-lg font-semibold">Sources</h2>
          <SourceList sources={report.sources} />
          <h2 className="mt-4 text-lg font-semibold">Related issues</h2>
          {report.related_issues.length === 0 ? (
            <p>No related issues were retrieved. This is not a duplicate verdict.</p>
          ) : (
            <ul>
              {report.related_issues.map((issue) => (
                <li key={issue.url}>
                  <ExternalLink title={`#${issue.number} ${issue.title}`} url={issue.url} />
                  <p>{issue.reason}</p>
                </li>
              ))}
            </ul>
          )}
          <h2 className="mt-4 text-lg font-semibold">Suggested next steps</h2>
          <ul>{report.next_steps.map((step) => <li key={step}>{step}</li>)}</ul>
          <h2 className="mt-4 text-lg font-semibold">Missing information</h2>
          {report.questions_for_reporter.length === 0 ? <p>No open question was recorded.</p> : <ul>{report.questions_for_reporter.map((item) => <li key={item}>{item}</li>)}</ul>}
          <h2 className="mt-4 text-lg font-semibold">Limitations</h2>
          <ul>{report.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
          <h2 className="mt-4 text-lg font-semibold">Timeline</h2>
          <ol className="space-y-1">
            {item.audit.map((event) => (
              <li key={`${event.action}-${event.created_at}`}>
                {event.created_at} {event.action} by {event.actor}
              </li>
            ))}
          </ol>
          {item.published_comment?.comment_url ? (
        <p className="mt-4">
          <ExternalLink title="Published GitHub comment" url={item.published_comment.comment_url} />
        </p>
      ) : null}
      {item.comment_preview ? (
            <div className="mt-6">
              <PublishPanel
                repo={item.repo_full_name}
                issueNumber={item.issue_number}
                preview={item.comment_preview.body}
                allowed={item.actions.publish_allowed}
                reason={item.actions.publish_block_reason}
                onPublish={() => {
                  void api(`/api/v1/investigations/${item.id}/publish-comment`, {
                    method: "POST",
                    body: JSON.stringify({
                      acknowledged: true,
                      content_sha256: item.comment_preview?.content_sha256,
                    }),
                  })
                    .then(() => {
                      setNotice("Comment published");
                      load();
                    })
                    .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "The comment was not published."));
                }}
              />
            </div>
          ) : null}
        </>
      ) : null}
      {item.actions.retry_allowed ? (
        <button
          className="mt-4 border border-line px-3 py-2"
          type="button"
          onClick={() => {
            const confirmed = window.confirm("Retry this investigation?");
            if (!confirmed) return;
            void api(`/api/v1/investigations/${item.id}/retry`, { method: "POST" }).then(load);
          }}
        >
          Retry investigation
        </button>
      ) : null}
    </>
  );
}
