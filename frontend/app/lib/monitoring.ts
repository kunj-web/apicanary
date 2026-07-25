export interface Monitor {
  id: string;
  name: string;
  url: string;
  method: string;
  headers: Record<string, string> | null;
  body: Record<string, unknown> | null;
  expected_status: number;
  check_interval: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Check {
  id: string;
  monitor_id: string;
  status: number;
  response_time: number | null;
  status_code: number | null;
  error_message: string | null;
  checked_at: string;
}

export interface Incident {
  id: string;
  monitor_id: string;
  monitor_name: string;
  started_at: string;
  resolved_at: string | null;
  duration_minutes: number | null;
  status: string;
  created_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface Uptime {
  monitor_id: string;
  window_hours: number;
  from_time: string;
  to_time: string;
  uptime_percentage: number | null;
  total_checks: number;
  successful_checks: number;
  failed_checks: number;
}

export interface ResponseTimePoint {
  checked_at: string;
  response_time: number;
  status: number;
  status_code: number | null;
}

export interface ResponseTime {
  monitor_id: string;
  window_hours: number;
  average_ms: number | null;
  minimum_ms: number | null;
  maximum_ms: number | null;
  p95_ms: number | null;
  points: ResponseTimePoint[];
}

export interface LatestStatus {
  monitor_id: string;
  monitor_status: string;
  latest_check: Check | null;
}

export async function apiErrorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  const payload = await response.json().catch(() => null);
  if (
    payload &&
    typeof payload === "object" &&
    "detail" in payload
  ) {
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail)) {
      const details: unknown[] = payload.detail;
      const messages = details
        .map((item: unknown) => {
          if (
            item &&
            typeof item === "object" &&
            "msg" in item &&
            typeof item.msg === "string"
          ) {
            return item.msg;
          }
          return null;
        })
        .filter(
          (message: string | null): message is string => message !== null,
        );
      if (messages.length > 0) return messages.join(". ");
    }
  }
  return fallback;
}

export function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatDuration(minutes: number | null): string {
  if (minutes === null) return "Ongoing";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return remainder ? `${hours}h ${remainder}m` : `${hours}h`;
}

export function checkLabel(status: number): string {
  if (status === 1) return "Up";
  if (status === 0) return "Down";
  return "Error";
}
