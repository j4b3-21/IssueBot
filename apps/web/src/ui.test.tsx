import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { App } from "./App";
import { BriefBlock, PageNotice, PublishPanel, SourceList } from "./components";
import { InvestigationsPage } from "./pages/Investigations";
import { SecretField } from "./pages/Settings";

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }),
  );
}

describe("authentication", () => {
  it("requires sign-in and does not show a stack trace", async () => {
    const user = userEvent.setup();
    let signedIn = false;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/auth/login") && init?.method === "POST") {
          signedIn = true;
          return jsonResponse({ status: "signed_in" });
        }
        if (url.endsWith("/auth/me")) {
          if (!signedIn) return jsonResponse({ error: "unauthenticated", message: "Sign in required." }, 401);
          return jsonResponse({ username: "admin", demo_mode: false });
        }
        if (url.endsWith("/overview")) {
          return jsonResponse({ counts: { failed: 0, running: 0, awaiting_approval: 0 }, recent: [], failed: [] });
        }
        return jsonResponse({ error: "unauthenticated", message: "Sign in required." }, 401);
      }),
    );
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Username"), "admin");
    await user.type(screen.getByLabelText("Password"), "test-password-strong");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { name: "Overview" })).toBeInTheDocument();
    expect(screen.queryByText(/Traceback/)).not.toBeInTheDocument();
  });
});

describe("evidence", () => {
  it("separates hypotheses from documented facts and skips unsafe links", () => {
    render(
      <>
        <BriefBlock kind="fact" text="The guide says to set the API key." />
        <BriefBlock kind="hypothesis" text="The key may be missing." />
        <SourceList
          sources={[
            { title: "Install", url: "https://docs.example.com/install", snippet: "Set the key.", linkable: true, retrieved_at: "2026-10-10T00:00:00Z" },
            { title: "Blocked", url: "javascript:alert(1)", snippet: "<script>alert(1)</script>", linkable: false, retrieved_at: "2026-10-10T00:00:00Z" },
          ]}
        />
      </>,
    );
    expect(screen.getByText("Documented fact")).toBeInTheDocument();
    expect(screen.getByText("Hypothesis")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /Install/ });
    expect(link).toHaveAttribute("href", "https://docs.example.com/install");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByText(/docs.example.com/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Blocked/ })).not.toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
  });
});

describe("investigation list", () => {
  it("shows an empty result and a failure without a stack trace", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => jsonResponse({ items: [], total: 0, limit: 20, offset: 0 })),
    );
    const { unmount } = render(
      <MemoryRouter>
        <InvestigationsPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("No investigations match this search.")).toBeInTheDocument();
    unmount();

    vi.stubGlobal(
      "fetch",
      vi.fn(() => jsonResponse({ error: "internal_error", message: "The list could not be loaded." }, 500)),
    );
    render(
      <MemoryRouter>
        <InvestigationsPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("The list could not be loaded.")).toBeInTheDocument();
    expect(screen.queryByText(/Traceback/)).not.toBeInTheDocument();
  });

  it("shows the offline message", () => {
    render(<PageNotice>The server did not respond.</PageNotice>);
    expect(screen.getByText("The server did not respond.")).toBeInTheDocument();
  });
});

describe("secrets and publishing", () => {
  it("does not display a saved secret", () => {
    render(<SecretField label="DocsGPT API key" name="docsgpt_api_key" configured />);
    expect(screen.getByText(/Configured/)).toBeInTheDocument();
    expect(screen.queryByDisplayValue("super-secret-key-value")).not.toBeInTheDocument();
    expect((screen.getByLabelText("DocsGPT API key") as HTMLInputElement).value).toBe("");
  });

  it("keeps publish disabled until the review box is checked", async () => {
    const user = userEvent.setup();
    const onPublish = vi.fn();
    render(
      <PublishPanel
        repo="acme/widget"
        issueNumber={7}
        preview="Hello maintainers"
        allowed
        reason={null}
        onPublish={onPublish}
      />,
    );
    const button = screen.getByRole("button", { name: "Publish comment on acme/widget#7" });
    expect(button).toBeDisabled();
    await user.click(screen.getByRole("checkbox"));
    expect(button).toBeEnabled();
    await user.click(button);
    expect(onPublish).toHaveBeenCalledOnce();
  });
});
