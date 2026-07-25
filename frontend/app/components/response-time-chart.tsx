import type { ResponseTimePoint } from "@/app/lib/monitoring";

const WIDTH = 800;
const HEIGHT = 240;
const PADDING_X = 20;
const PADDING_Y = 24;

export default function ResponseTimeChart({
  points,
}: {
  points: ResponseTimePoint[];
}) {
  if (points.length === 0) {
    return (
      <div className="flex h-60 items-center justify-center rounded-xl bg-gray-50 text-sm text-gray-500">
        Response-time data will appear after the first check.
      </div>
    );
  }

  const values = points.map((point) => point.response_time);
  const maximum = Math.max(...values, 1);
  const minimum = Math.min(...values);
  const range = Math.max(maximum - minimum, 1);
  const chartWidth = WIDTH - PADDING_X * 2;
  const chartHeight = HEIGHT - PADDING_Y * 2;
  const coordinates = points.map((point, index) => {
    const x =
      PADDING_X +
      (points.length === 1
        ? chartWidth / 2
        : (index / (points.length - 1)) * chartWidth);
    const y =
      maximum === minimum
        ? PADDING_Y + chartHeight / 2
        : PADDING_Y +
          ((maximum - point.response_time) / range) * chartHeight;
    return { x, y, point };
  });
  const polyline = coordinates
    .map(({ x, y }) => `${x.toFixed(1)},${y.toFixed(1)}`)
    .join(" ");

  return (
    <div>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-60 w-full overflow-visible"
        role="img"
        aria-label={`Response times from ${minimum} to ${maximum} milliseconds`}
      >
        {[0, 0.25, 0.5, 0.75, 1].map((position) => {
          const y = PADDING_Y + position * chartHeight;
          return (
            <line
              key={position}
              x1={PADDING_X}
              x2={WIDTH - PADDING_X}
              y1={y}
              y2={y}
              stroke="#e5e7eb"
              strokeWidth="1"
            />
          );
        })}
        <polyline
          fill="none"
          stroke="#2563eb"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={polyline}
        />
        {coordinates.map(({ x, y, point }) => (
          <circle
            key={`${point.checked_at}-${point.response_time}`}
            cx={x}
            cy={y}
            r={points.length > 40 ? 2 : 4}
            fill={point.status === 1 ? "#2563eb" : "#ef4444"}
          >
            <title>
              {`${point.response_time} ms — ${new Date(point.checked_at).toLocaleString()}`}
            </title>
          </circle>
        ))}
      </svg>
      <div className="mt-2 flex justify-between text-xs text-gray-400">
        <span>{new Date(points[0].checked_at).toLocaleString()}</span>
        <span>
          {new Date(points[points.length - 1].checked_at).toLocaleString()}
        </span>
      </div>
    </div>
  );
}
