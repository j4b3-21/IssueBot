import { FormEvent, useState } from "react";
import { ApiError, api } from "../api";

export function LoginPage({ onSignedIn }: { onSignedIn: (username: string, demo: boolean) => void }) {
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setError("");
    try {
      await api("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({
          username: String(data.get("username") || ""),
          password: String(data.get("password") || ""),
        }),
      });
      const me = await api<{ username: string; demo_mode: boolean }>("/api/v1/auth/me");
      onSignedIn(me.username, me.demo_mode);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign-in failed.");
    }
  }

  return (
    <form className="mx-auto max-w-md border border-line bg-sheet p-6" onSubmit={submit}>
      <h1 tabIndex={-1} className="mb-4 text-2xl font-semibold">
        Sign in
      </h1>
      <label className="mb-3 block" htmlFor="username">
        Username
        <input id="username" name="username" autoComplete="username" className="mt-1 w-full border border-line px-2 py-1" required />
      </label>
      <label className="mb-3 block" htmlFor="password">
        Password
        <input id="password" name="password" type="password" autoComplete="current-password" className="mt-1 w-full border border-line px-2 py-1" required />
      </label>
      {error ? (
        <p id="login-error" role="alert">
          {error}
        </p>
      ) : null}
      <button className="bg-mark px-3 py-2 text-white" type="submit">
        Sign in
      </button>
    </form>
  );
}
