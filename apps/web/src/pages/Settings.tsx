import { FormEvent, useEffect, useState } from "react";
import { ApiError, api } from "../api";
import { PageNotice } from "../components";
import type { SettingsView } from "../types";

export function SettingsPage() {
  const [settings, setSettings] = useState<SettingsView | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  function load() {
    api<SettingsView>("/api/v1/settings")
      .then(setSettings)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Settings could not be loaded."));
  }

  useEffect(() => {
    load();
  }, []);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const repos = String(data.get("allowed_repos") || "")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    const body: Record<string, unknown> = {
      docsgpt_base_url: String(data.get("docsgpt_base_url") || ""),
      docsgpt_agent_id: String(data.get("docsgpt_agent_id") || ""),
      github_app_id: String(data.get("github_app_id") || ""),
      allowed_repos: repos,
      publish_enabled: data.get("publish_enabled") === "on",
    };
    const apiKey = String(data.get("docsgpt_api_key") || "");
    const webhook = String(data.get("github_webhook_secret") || "");
    const privateKey = String(data.get("github_private_key") || "");
    if (apiKey) body.docsgpt_api_key = apiKey;
    if (webhook) body.github_webhook_secret = webhook;
    if (privateKey) body.github_private_key = privateKey;
    try {
      const next = await api<SettingsView>("/api/v1/settings", { method: "PUT", body: JSON.stringify(body) });
      setSettings(next);
      setMessage("Saved. Secret values are not shown again.");
      setError("");
      form.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>("input[type=password], #github_private_key").forEach((field) => {
        field.value = "";
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Settings were not saved.");
    }
  }

  if (error && !settings) return <PageNotice>{error}</PageNotice>;
  if (!settings) return <p>Loading settings.</p>;

  return (
    <>
      <h1 tabIndex={-1} className="mb-4 text-2xl font-semibold">
        Settings
      </h1>
      {settings.demo_mode ? <PageNotice>Demo data. Nothing is published to GitHub.</PageNotice> : null}
      <p className="my-3">
        Webhook URL <code>{settings.webhook_url}</code>
      </p>
      <p className="mb-3">
        In the GitHub App, subscribe to Issues and Installation. Send a secret that matches the value saved here. The URL must be reachable by GitHub.
      </p>
      <h2 className="text-lg font-semibold">GitHub installations</h2>
      {settings.installations.length === 0 ? (
        <p className="mb-4">No installation has checked in.</p>
      ) : (
        <ul className="mb-4">
          {settings.installations.map((item) => (
            <li key={item.installation_id}>
              {item.account_login || "Unknown account"} ({item.status})
            </li>
          ))}
        </ul>
      )}
      <form className="space-y-3 border border-line bg-sheet p-4" onSubmit={save}>
        <Field label="DocsGPT base URL" name="docsgpt_base_url" defaultValue={settings.docsgpt_base_url} />
        <Field label="DocsGPT agent id" name="docsgpt_agent_id" defaultValue={settings.docsgpt_agent_id} />
        <SecretField label="DocsGPT API key" name="docsgpt_api_key" configured={settings.docsgpt_api_key_configured} />
        <Field label="GitHub App ID" name="github_app_id" defaultValue={settings.github_app_id} />
        <label className="block" htmlFor="github_private_key">
          GitHub private key
          <textarea id="github_private_key" name="github_private_key" className="mt-1 w-full border border-line px-2 py-1" autoComplete="off" />
          <span>{settings.github_private_key_configured ? "Configured" : "Not set"}. Leave blank to keep the saved key.</span>
        </label>
        <SecretField label="Webhook secret" name="github_webhook_secret" configured={settings.github_webhook_secret_configured} />
        <label className="block" htmlFor="allowed_repos">
          Allowed repositories
          <textarea id="allowed_repos" name="allowed_repos" defaultValue={settings.allowed_repos.join("\n")} className="mt-1 w-full border border-line px-2 py-1" />
        </label>
        <label className="flex items-center gap-2">
          <input name="publish_enabled" type="checkbox" defaultChecked={settings.publish_enabled} />
          Allow a signed-in maintainer to publish comments
        </label>
        <p>Private-network DocsGPT access is {settings.allow_private_docsgpt ? "enabled" : "off"} via the server environment.</p>
        {message ? <p>{message}</p> : null}
        {error ? <PageNotice>{error}</PageNotice> : null}
        <button className="bg-mark px-3 py-2 text-white" type="submit">
          Save changes
        </button>
      </form>
      <form
        className="mt-6 space-y-3 border border-line bg-sheet p-4"
        onSubmit={(event) => {
          event.preventDefault();
          const form = event.currentTarget;
          const data = new FormData(form);
          void api("/api/v1/account/password", {
            method: "POST",
            body: JSON.stringify({
              current_password: String(data.get("current_password") || ""),
              new_password: String(data.get("new_password") || ""),
            }),
          })
            .then(() => {
              setMessage("Password changed. Sign in again on other browsers.");
              setError("");
              form.reset();
            })
            .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "The password was not changed."));
        }}
      >
        <h2 className="text-lg font-semibold">Change password</h2>
        <Field label="Current password" name="current_password" defaultValue="" password />
        <Field label="New password" name="new_password" defaultValue="" password />
        <button className="border border-line px-3 py-2" type="submit">
          Change password
        </button>
      </form>
      <div className="mt-4 flex gap-2">
        <button type="button" onClick={() => void test("/api/v1/settings/test-docsgpt", setMessage, setError)}>
          Test DocsGPT
        </button>
        <button type="button" onClick={() => void test("/api/v1/settings/test-github", setMessage, setError)}>
          Test GitHub
        </button>
        {settings.demo_mode ? (
          <button
            type="button"
            onClick={() => {
              void api("/api/v1/demo/sample-issue", { method: "POST" })
                .then(() => setMessage("Sample issue queued. It is marked as demo data."))
                .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "The sample was not queued."));
            }}
          >
            Load a sample issue
          </button>
        ) : null}
      </div>
    </>
  );
}

function Field({
  label,
  name,
  defaultValue,
  password = false,
}: {
  label: string;
  name: string;
  defaultValue: string;
  password?: boolean;
}) {
  return (
    <label className="block" htmlFor={name}>
      {label}
      <input
        id={name}
        name={name}
        type={password ? "password" : "text"}
        autoComplete={password ? "new-password" : "off"}
        defaultValue={defaultValue}
        className="mt-1 w-full border border-line px-2 py-1"
      />
    </label>
  );
}

export function SecretField({ label, name, configured }: { label: string; name: string; configured: boolean }) {
  return (
    <div>
      <label className="block" htmlFor={name}>
        {label}
        <input id={name} name={name} type="password" autoComplete="new-password" aria-describedby={`${name}-status`} className="mt-1 w-full border border-line px-2 py-1" />
      </label>
      <p id={`${name}-status`}>{configured ? "Configured" : "Not set"}. Saved. The value is not shown again.</p>
    </div>
  );
}

async function test(path: string, setMessage: (value: string) => void, setError: (value: string) => void) {
  try {
    const result = await api<{ ok: boolean; message?: string }>(path, { method: "POST" });
    setMessage(result.message || (result.ok ? "Connection succeeded." : "Connection failed."));
    setError("");
  } catch (err) {
    setError(err instanceof ApiError ? err.message : "The connection test failed.");
  }
}
