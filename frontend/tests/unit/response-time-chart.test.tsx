import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ResponseTimeChart from "@/app/components/response-time-chart";

describe("ResponseTimeChart", () => {
  it("shows a useful empty state", () => {
    render(<ResponseTimeChart points={[]} />);

    expect(
      screen.getByText(/data will appear after the first check/i),
    ).toBeTruthy();
  });

  it("renders accessible timing data and failed points", () => {
    const { container } = render(
      <ResponseTimeChart
        points={[
          {
            checked_at: "2026-07-25T08:00:00Z",
            response_time: 120,
            status: 1,
            status_code: 200,
          },
          {
            checked_at: "2026-07-25T08:05:00Z",
            response_time: 450,
            status: 0,
            status_code: 503,
          },
        ]}
      />,
    );

    expect(
      screen.getByRole("img", {
        name: "Response times from 120 to 450 milliseconds",
      }),
    ).toBeTruthy();
    expect(container.querySelectorAll("circle")).toHaveLength(2);
    expect(container.querySelector('circle[fill="#ef4444"]')).toBeTruthy();
  });
});
