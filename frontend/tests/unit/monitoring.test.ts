import { describe, expect, it } from "vitest";
import {
  apiErrorMessage,
  checkLabel,
  formatDuration,
} from "@/app/lib/monitoring";

describe("monitoring formatters", () => {
  it("labels persisted check states", () => {
    expect(checkLabel(1)).toBe("Up");
    expect(checkLabel(0)).toBe("Down");
    expect(checkLabel(-1)).toBe("Error");
  });

  it("formats incident durations", () => {
    expect(formatDuration(null)).toBe("Ongoing");
    expect(formatDuration(12)).toBe("12m");
    expect(formatDuration(60)).toBe("1h");
    expect(formatDuration(125)).toBe("2h 5m");
  });
});

describe("API error messages", () => {
  it("uses a string detail from the backend", async () => {
    const response = Response.json(
      { detail: "Monitor not found" },
      { status: 404 },
    );

    await expect(
      apiErrorMessage(response, "Request failed"),
    ).resolves.toBe("Monitor not found");
  });

  it("combines validation messages and keeps a safe fallback", async () => {
    const validation = Response.json(
      {
        detail: [
          { msg: "URL is invalid" },
          { msg: "Status must be at least 100" },
        ],
      },
      { status: 422 },
    );
    const nonJson = new Response("upstream unavailable", { status: 502 });

    await expect(
      apiErrorMessage(validation, "Request failed"),
    ).resolves.toBe("URL is invalid. Status must be at least 100");
    await expect(
      apiErrorMessage(nonJson, "Request failed"),
    ).resolves.toBe("Request failed");
  });
});
