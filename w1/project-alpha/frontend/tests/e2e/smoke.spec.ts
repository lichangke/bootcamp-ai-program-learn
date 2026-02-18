import { expect, test } from "@playwright/test";

type TicketStatus = "open" | "done";

interface TagState {
  id: number;
  name: string;
  created_at: string;
  updated_at: string;
}

interface TicketState {
  id: number;
  title: string;
  description: string | null;
  status: TicketStatus;
  tag_ids: number[];
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

function nowIso(): string {
  return new Date().toISOString();
}

test("day7 smoke: create tag -> create ticket -> filter/search -> complete/reopen -> delete", async ({ page }) => {
  let nextTagId = 1;
  let nextTicketId = 1;
  const tags: TagState[] = [];
  const tickets: TicketState[] = [];

  await page.route("**/api/tags**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const pathParts = url.pathname.split("/").filter(Boolean);
    const maybeTagId = Number(pathParts[pathParts.length - 1]);

    if (method === "GET") {
      await route.fulfill({ json: { data: tags } });
      return;
    }

    if (method === "POST") {
      const payload = (request.postDataJSON() ?? {}) as { name?: string };
      const tag: TagState = {
        id: nextTagId++,
        name: payload.name ?? "tag",
        created_at: nowIso(),
        updated_at: nowIso(),
      };
      tags.push(tag);
      await route.fulfill({ status: 201, json: { data: tag } });
      return;
    }

    if (method === "PUT") {
      const payload = (request.postDataJSON() ?? {}) as { name?: string };
      const target = tags.find((tag) => tag.id === maybeTagId);
      if (!target) {
        await route.fulfill({ status: 404, json: { error: { code: "TAG_NOT_FOUND", message: "Tag not found.", details: {} } } });
        return;
      }
      target.name = payload.name ?? target.name;
      target.updated_at = nowIso();
      await route.fulfill({ json: { data: target } });
      return;
    }

    if (method === "DELETE") {
      const index = tags.findIndex((tag) => tag.id === maybeTagId);
      if (index >= 0) {
        tags.splice(index, 1);
      }
      tickets.forEach((ticket) => {
        ticket.tag_ids = ticket.tag_ids.filter((tagId) => tagId !== maybeTagId);
      });
      await route.fulfill({ status: 204, body: "" });
      return;
    }

    await route.fallback();
  });

  await page.route("**/api/tickets**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const pathParts = url.pathname.split("/").filter(Boolean);
    const last = pathParts[pathParts.length - 1];
    const maybeTicketId = Number(pathParts[pathParts.length - 1]);

    if (method === "GET") {
      const tagId = url.searchParams.get("tag_id");
      const q = url.searchParams.get("q");
      const status = url.searchParams.get("status");
      const pageParam = Number(url.searchParams.get("page") ?? "1");
      const pageSizeParam = Number(url.searchParams.get("page_size") ?? "10");

      let filtered = [...tickets];
      if (tagId) {
        filtered = filtered.filter((ticket) => ticket.tag_ids.includes(Number(tagId)));
      }
      if (status === "open" || status === "done") {
        filtered = filtered.filter((ticket) => ticket.status === status);
      }
      if (q) {
        filtered = filtered.filter((ticket) => ticket.title.toLowerCase().includes(q.toLowerCase()));
      }

      const start = (pageParam - 1) * pageSizeParam;
      const pageData = filtered.slice(start, start + pageSizeParam);
      await route.fulfill({
        json: {
          data: pageData,
          meta: {
            page: pageParam,
            page_size: pageSizeParam,
            total: filtered.length,
          },
        },
      });
      return;
    }

    if (method === "POST") {
      const payload = (request.postDataJSON() ?? {}) as { title: string; description: string | null; tag_ids: number[] };
      const ticket: TicketState = {
        id: nextTicketId++,
        title: payload.title,
        description: payload.description,
        status: "open",
        tag_ids: payload.tag_ids,
        created_at: nowIso(),
        updated_at: nowIso(),
        completed_at: null,
      };
      tickets.unshift(ticket);
      await route.fulfill({ status: 201, json: { data: ticket } });
      return;
    }

    if (Number.isFinite(maybeTicketId) && method === "GET") {
      const ticket = tickets.find((item) => item.id === maybeTicketId);
      await route.fulfill(ticket ? { json: { data: ticket } } : { status: 404, json: { error: { code: "TICKET_NOT_FOUND", message: "Ticket not found.", details: {} } } });
      return;
    }

    if (method === "PUT") {
      const payload = (request.postDataJSON() ?? {}) as { title: string; description: string | null; tag_ids: number[] };
      const ticket = tickets.find((item) => item.id === maybeTicketId);
      if (!ticket) {
        await route.fulfill({ status: 404, json: { error: { code: "TICKET_NOT_FOUND", message: "Ticket not found.", details: {} } } });
        return;
      }
      ticket.title = payload.title;
      ticket.description = payload.description;
      ticket.tag_ids = payload.tag_ids;
      ticket.updated_at = nowIso();
      await route.fulfill({ json: { data: ticket } });
      return;
    }

    if (method === "PATCH" && last === "complete") {
      const ticketId = Number(pathParts[pathParts.length - 2]);
      const ticket = tickets.find((item) => item.id === ticketId);
      if (!ticket) {
        await route.fulfill({ status: 404, json: { error: { code: "TICKET_NOT_FOUND", message: "Ticket not found.", details: {} } } });
        return;
      }
      ticket.status = "done";
      ticket.completed_at = nowIso();
      ticket.updated_at = nowIso();
      await route.fulfill({ json: { data: ticket } });
      return;
    }

    if (method === "PATCH" && last === "reopen") {
      const ticketId = Number(pathParts[pathParts.length - 2]);
      const ticket = tickets.find((item) => item.id === ticketId);
      if (!ticket) {
        await route.fulfill({ status: 404, json: { error: { code: "TICKET_NOT_FOUND", message: "Ticket not found.", details: {} } } });
        return;
      }
      ticket.status = "open";
      ticket.completed_at = null;
      ticket.updated_at = nowIso();
      await route.fulfill({ json: { data: ticket } });
      return;
    }

    if (method === "DELETE") {
      const index = tickets.findIndex((item) => item.id === maybeTicketId);
      if (index === -1) {
        await route.fulfill({ status: 404, json: { error: { code: "TICKET_NOT_FOUND", message: "Ticket not found.", details: {} } } });
        return;
      }
      tickets.splice(index, 1);
      await route.fulfill({ status: 204, body: "" });
      return;
    }

    await route.fallback();
  });

  await page.goto("/");

  await page.getByRole("button", { name: "Tag Manager" }).click();
  await page.getByPlaceholder("New tag name").fill("backend");
  await page.getByRole("button", { name: "Add Tag" }).click();
  await page.getByRole("button", { name: "Close" }).click();

  await page.getByRole("button", { name: "New Ticket" }).click();
  await page.getByLabel("Title").fill("Build board UI");
  await page.getByLabel("Description").fill("finish day 5 flow");
  await page.getByRole("button", { name: "backend" }).click();
  await page.getByRole("button", { name: "Create Ticket" }).click();

  await expect(page.getByText("Build board UI")).toBeVisible();

  await page.getByRole("button", { name: "Complete" }).click();
  await expect(page.getByRole("button", { name: "Reopen" })).toBeVisible();

  await page.getByRole("combobox").nth(1).selectOption("done");
  await expect(page.getByText("Build board UI")).toBeVisible();

  await page.getByPlaceholder("Search by ticket title").fill("board");
  await expect(page.getByText("Build board UI")).toBeVisible();

  await page.getByRole("button", { name: "Reopen" }).click();
  await page.getByRole("combobox").nth(1).selectOption("open");
  await expect(page.getByText("Build board UI")).toBeVisible();
  await expect(page.getByRole("button", { name: "Complete" })).toBeVisible();

  page.on("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByText("No matching tickets for current filters.")).toBeVisible();
});
