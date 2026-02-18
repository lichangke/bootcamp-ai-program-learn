import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/App";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("TicketListPage", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/tags")) {
        return Promise.resolve(jsonResponse({ data: [] }));
      }
      if (url.includes("/tickets")) {
        return Promise.resolve(
          jsonResponse({
            data: [],
            meta: { page: 1, page_size: 10, total: 0 },
          }),
        );
      }
      return Promise.resolve(jsonResponse({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    global.fetch = originalFetch;
  });

  it("shows empty-state message when no tickets", async () => {
    render(<App />);
    expect(await screen.findByText("No tickets yet. Create one.")).toBeInTheDocument();
  });

  it("renders ticket title when data is available", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/tags")) {
        return Promise.resolve(
          jsonResponse({
            data: [{ id: 1, name: "backend", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }],
          }),
        );
      }
      if (url.includes("/tickets")) {
        return Promise.resolve(
          jsonResponse({
            data: [
              {
                id: 1,
                title: "Implement board",
                description: "Main ticket",
                status: "open",
                tag_ids: [1],
                created_at: "2026-01-01T00:00:00Z",
                updated_at: "2026-01-01T00:00:00Z",
                completed_at: null,
              },
            ],
            meta: { page: 1, page_size: 10, total: 1 },
          }),
        );
      }
      return Promise.resolve(jsonResponse({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("Implement board")).toBeInTheDocument();
    });
  });
});
