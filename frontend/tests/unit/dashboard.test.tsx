import { fireEvent, render, screen } from "@testing-library/react";
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
});
