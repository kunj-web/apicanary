import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  apiFetch,
  authenticatedFetch,
  migrateLegacySession,
} from "@/app/lib/api";

describe("API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("sends cookies and the CSRF verification header on mutations", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 204 }));

    await apiFetch("/api/monitors", { method: "POST" });

    const [, request] = fetchMock.mock.calls[0];
    expect(request?.credentials).toBe("include");
    expect(new Headers(request?.headers).get("X-Requested-With")).toBe(
      "APICanary",
    );
  });

  it("migrates a legacy bearer token once and removes it", async () => {
    localStorage.setItem("token", "legacy-token");
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 200 }));

    await expect(migrateLegacySession()).resolves.toBe(true);

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, request] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/auth/session");
    expect(new Headers(request?.headers).get("Authorization")).toBe(
      "Bearer legacy-token",
    );
    expect(localStorage.getItem("token")).toBeNull();
  });

  it("retries an unauthorized request after successful migration", async () => {
    localStorage.setItem("token", "legacy-token");
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        Response.json({ detail: "Not authenticated" }, { status: 401 }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(Response.json([{ id: "monitor-1" }]));

    const response = await authenticatedFetch("/api/monitors");

    expect(response.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});
