import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Dashboard from "@/app/dashboard/page";

const router = {
  push: vi.fn(),
  replace: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));

describe("Dashboard monitor form", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    router.push.mockReset();
    router.replace.mockReset();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json([]));
  });

  it("accepts a normal name and requires a URL for the endpoint", () => {
    render(<Dashboard />);

    fireEvent.click(
      screen.getByRole("button", { name: /Add Monitor/ }),
    );

    expect(
      screen.getByPlaceholderText("e.g. Login API").getAttribute("type"),
    ).toBe("text");
    expect(
      screen
        .getByPlaceholderText("https://api.example.com/health")
        .getAttribute("type"),
    ).toBe("url");
  });

  it("saves a test alert and refreshes delivery history", async () => {
    let deliveryReads = 0;
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input, init) => {
        const url = String(input);
        if (url === "/api/monitors") return Response.json([]);
        if (url === "/api/alerts") {
          return Response.json([
            {
              id: "alert-1",
              monitor_id: "monitor-1",
              alert_type: "email",
              recipient: "owner@example.com",
              threshold_failures: 2,
              is_active: true,
            },
          ]);
        }
        if (url.startsWith("/api/alerts/deliveries")) {
          deliveryReads += 1;
          return Response.json({
            items:
              deliveryReads === 1
                ? []
                : [
                    {
                      id: "delivery-1",
                      alert_id: "alert-1",
                      monitor_id: "monitor-1",
                      event_type: "test",
                      channel: "email",
                      recipient: "owner@example.com",
                      status: "queued",
                      attempt_count: 0,
                      last_error: null,
                      next_attempt_at: null,
                      sent_at: null,
                      created_at: "2026-08-02T10:00:00Z",
                      updated_at: "2026-08-02T10:00:00Z",
                    },
                  ],
            total: deliveryReads === 1 ? 0 : 1,
            page: 1,
            page_size: 10,
            total_pages: deliveryReads === 1 ? 0 : 1,
          });
        }
        if (url === "/api/alerts/alert-1/test") {
          expect(init?.method).toBe("POST");
          return Response.json(
            {
              delivery_id: "delivery-1",
              status: "pending",
              message: "Test alert saved for delivery",
            },
            { status: 202 },
          );
        }
        return new Response(null, { status: 404 });
      });

    render(<Dashboard />);
    fireEvent.click(screen.getByRole("button", { name: /Alerts/ }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Send test" }),
    );

    expect((await screen.findByRole("status")).textContent).toContain(
      "Test alert saved for delivery",
    );
    expect(await screen.findByText("test")).toBeTruthy();
    await waitFor(() => expect(deliveryReads).toBe(2));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/alerts/alert-1/test",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
