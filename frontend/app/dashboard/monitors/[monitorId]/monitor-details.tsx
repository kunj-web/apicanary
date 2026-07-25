"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import ResponseTimeChart from "@/app/components/response-time-chart";
import { authenticatedFetch } from "@/app/lib/api";
import {
  apiErrorMessage,
  checkLabel,
  formatDate,
  formatDuration,
  type Check,
  type Incident,
  type LatestStatus,
  type Monitor,
  type PaginatedResponse,
  type ResponseTime,
  type Uptime,
} from "@/app/lib/monitoring";

const EMPTY_PAGE = {
  items: [],
  total: 0,
  page: 1,
  page_size: 10,
  total_pages: 0,
};

interface MonitorForm {
  name: string;
  url: string;
  method: string;
  expected_status: number;
  check_interval: number;
}

function Pagination({
  page,
  totalPages,
  onChange,
}: {
  page: number;
  totalPages: number;
  onChange: (page: number) => void;
}) {
  if (totalPages <= 1) return null;
  return (
    <div className="mt-4 flex items-center justify-between border-t border-gray-100 pt-4">
      <span className="text-xs text-gray-500">
        Page {page} of {totalPages}
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onChange(page - 1)}
          disabled={page <= 1}
          className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-40"
        >
          Previous
        </button>
        <button
          type="button"
          onClick={() => onChange(page + 1)}
          disabled={page >= totalPages}
          className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-40"
        >
          Next
        </button>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const style =
    status === "active" || status === "up"
      ? "bg-emerald-100 text-emerald-700"
      : status === "down" || status === "error"
        ? "bg-red-100 text-red-700"
        : status === "paused"
          ? "bg-amber-100 text-amber-700"
          : "bg-gray-100 text-gray-600";
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${style}`}
    >
      {status.replace("_", " ")}
    </span>
  );
}

export default function MonitorDetails({
  monitorId,
}: {
  monitorId: string;
}) {
  const router = useRouter();
  const [monitor, setMonitor] = useState<Monitor | null>(null);
  const [uptime, setUptime] = useState<Uptime | null>(null);
  const [responseTime, setResponseTime] = useState<ResponseTime | null>(null);
  const [latestStatus, setLatestStatus] = useState<LatestStatus | null>(null);
  const [checks, setChecks] =
    useState<PaginatedResponse<Check>>(EMPTY_PAGE);
  const [incidents, setIncidents] =
    useState<PaginatedResponse<Incident>>(EMPTY_PAGE);
  const [hours, setHours] = useState(24);
  const [checkPage, setCheckPage] = useState(1);
  const [incidentPage, setIncidentPage] = useState(1);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [checksLoading, setChecksLoading] = useState(true);
  const [incidentsLoading, setIncidentsLoading] = useState(true);
  const [overviewError, setOverviewError] = useState<string | null>(null);
  const [checksError, setChecksError] = useState<string | null>(null);
  const [incidentsError, setIncidentsError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);
  const [showEdit, setShowEdit] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [form, setForm] = useState<MonitorForm>({
    name: "",
    url: "",
    method: "GET",
    expected_status: 200,
    check_interval: 5,
  });

  const redirectIfUnauthorized = useCallback(
    (response: Response) => {
      if (response.status === 401) {
        router.replace("/login");
        return true;
      }
      return false;
    },
    [router],
  );

  const loadOverview = useCallback(
    async (showLoading = true) => {
      await Promise.resolve();
      if (showLoading) setOverviewLoading(true);
      setOverviewError(null);
      try {
        const [monitorResponse, uptimeResponse, timingResponse, statusResponse] =
          await Promise.all([
            authenticatedFetch(`/api/monitors/${monitorId}`),
            authenticatedFetch(
              `/api/monitors/${monitorId}/uptime?hours=${hours}`,
            ),
            authenticatedFetch(
              `/api/monitors/${monitorId}/response-time?hours=${hours}&max_points=120`,
            ),
            authenticatedFetch(`/api/monitors/${monitorId}/status`),
          ]);
        const responses = [
          monitorResponse,
          uptimeResponse,
          timingResponse,
          statusResponse,
        ];
        if (responses.some(redirectIfUnauthorized)) return;
        const failed = responses.find((response) => !response.ok);
        if (failed) {
          throw new Error(
            await apiErrorMessage(failed, "Could not load monitor details"),
          );
        }
        const [nextMonitor, nextUptime, nextTiming, nextStatus] =
          await Promise.all([
            monitorResponse.json() as Promise<Monitor>,
            uptimeResponse.json() as Promise<Uptime>,
            timingResponse.json() as Promise<ResponseTime>,
            statusResponse.json() as Promise<LatestStatus>,
          ]);
        setMonitor(nextMonitor);
        setUptime(nextUptime);
        setResponseTime(nextTiming);
        setLatestStatus(nextStatus);
      } catch (error) {
        setOverviewError(
          error instanceof Error
            ? error.message
            : "Could not load monitor details",
        );
      } finally {
        if (showLoading) setOverviewLoading(false);
      }
    },
    [hours, monitorId, redirectIfUnauthorized],
  );

  const loadChecks = useCallback(async () => {
    await Promise.resolve();
    setChecksLoading(true);
    setChecksError(null);
    try {
      const response = await authenticatedFetch(
        `/api/monitors/${monitorId}/checks?page=${checkPage}&page_size=10`,
      );
      if (redirectIfUnauthorized(response)) return;
      if (!response.ok) {
        throw new Error(
          await apiErrorMessage(response, "Could not load check history"),
        );
      }
      setChecks(await response.json());
    } catch (error) {
      setChecksError(
        error instanceof Error
          ? error.message
          : "Could not load check history",
      );
    } finally {
      setChecksLoading(false);
    }
  }, [checkPage, monitorId, redirectIfUnauthorized]);

  const loadIncidents = useCallback(async () => {
    await Promise.resolve();
    setIncidentsLoading(true);
    setIncidentsError(null);
    try {
      const response = await authenticatedFetch(
        `/api/monitors/${monitorId}/incidents?page=${incidentPage}&page_size=10`,
      );
      if (redirectIfUnauthorized(response)) return;
      if (!response.ok) {
        throw new Error(
          await apiErrorMessage(response, "Could not load incidents"),
        );
      }
      setIncidents(await response.json());
    } catch (error) {
      setIncidentsError(
        error instanceof Error ? error.message : "Could not load incidents",
      );
    } finally {
      setIncidentsLoading(false);
    }
  }, [incidentPage, monitorId, redirectIfUnauthorized]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadOverview();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadOverview]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadChecks();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadChecks]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadIncidents();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadIncidents]);

  const openEdit = () => {
    if (!monitor) return;
    setForm({
      name: monitor.name,
      url: monitor.url,
      method: monitor.method,
      expected_status: monitor.expected_status,
      check_interval: monitor.check_interval,
    });
    setFormError(null);
    setShowEdit(true);
  };

  const saveMonitor = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!monitor) return;
    setBusyAction("edit");
    setFormError(null);
    try {
      const response = await authenticatedFetch(
        `/api/monitors/${monitor.id}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ...form,
            headers: monitor.headers,
            body: monitor.body,
          }),
        },
      );
      if (redirectIfUnauthorized(response)) return;
      if (!response.ok) {
        throw new Error(
          await apiErrorMessage(response, "Could not update monitor"),
        );
      }
      setMonitor(await response.json());
      setShowEdit(false);
      setFeedback({
        type: "success",
        message: "Monitor settings updated.",
      });
      await loadOverview(false);
    } catch (error) {
      setFormError(
        error instanceof Error ? error.message : "Could not update monitor",
      );
    } finally {
      setBusyAction(null);
    }
  };

  const runAction = async (action: "test" | "pause" | "resume") => {
    if (!monitor) return;
    setBusyAction(action);
    setFeedback(null);
    try {
      const response = await authenticatedFetch(
        `/api/monitors/${monitor.id}/${action}`,
        { method: "POST" },
      );
      if (redirectIfUnauthorized(response)) return;
      if (!response.ok) {
        throw new Error(
          await apiErrorMessage(response, `Could not ${action} monitor`),
        );
      }
      setFeedback({
        type: "success",
        message:
          action === "test"
            ? "Manual check queued. Refresh shortly to see its result."
            : `Monitoring ${action === "pause" ? "paused" : "resumed"}.`,
      });
      if (action !== "test") await loadOverview(false);
    } catch (error) {
      setFeedback({
        type: "error",
        message:
          error instanceof Error ? error.message : "Monitor action failed",
      });
    } finally {
      setBusyAction(null);
    }
  };

  const latestLabel = latestStatus?.latest_check
    ? checkLabel(latestStatus.latest_check.status)
    : monitor?.status === "paused"
      ? "Paused"
      : "Awaiting first check";

  if (overviewLoading && !monitor) {
    return <LoadingState />;
  }

  if (overviewError && !monitor) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gray-50 p-6">
        <div className="w-full max-w-md rounded-2xl border border-red-100 bg-white p-8 text-center shadow-sm">
          <h1 className="text-lg font-semibold text-gray-900">
            Monitor unavailable
          </h1>
          <p className="mt-2 text-sm text-red-600">{overviewError}</p>
          <div className="mt-6 flex justify-center gap-3">
            <Link
              href="/dashboard"
              className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700"
            >
              Back
            </Link>
            <button
              type="button"
              onClick={() => void loadOverview()}
              className="rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white"
            >
              Retry
            </button>
          </div>
        </div>
      </main>
    );
  }

  if (!monitor) return null;

  return (
    <main className="min-h-screen bg-gray-50 pb-12">
      <header className="border-b border-gray-100 bg-white">
        <div className="mx-auto max-w-7xl px-5 py-5">
          <Link
            href="/dashboard"
            className="text-sm font-medium text-gray-500 hover:text-gray-900"
          >
            ← All monitors
          </Link>
          <div className="mt-4 flex flex-col justify-between gap-4 md:flex-row md:items-center">
            <div className="min-w-0">
              <div className="flex items-center gap-3">
                <h1 className="truncate text-2xl font-bold text-gray-900">
                  {monitor.name}
                </h1>
                <StatusBadge status={monitor.status} />
              </div>
              <p className="mt-1 break-all font-mono text-xs text-gray-500">
                {monitor.method} {monitor.url}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={openEdit}
                disabled={busyAction !== null}
                className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                Edit
              </button>
              <button
                type="button"
                onClick={() => void runAction("test")}
                disabled={busyAction !== null}
                className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50"
              >
                {busyAction === "test" ? "Queuing…" : "Run test"}
              </button>
              <button
                type="button"
                onClick={() =>
                  void runAction(
                    monitor.status === "paused" ? "resume" : "pause",
                  )
                }
                disabled={busyAction !== null}
                className="rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
              >
                {busyAction === "pause" || busyAction === "resume"
                  ? "Saving…"
                  : monitor.status === "paused"
                    ? "Resume"
                    : "Pause"}
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl space-y-6 px-5 py-6">
        {feedback && (
          <div
            role="status"
            className={`rounded-xl border px-4 py-3 text-sm ${
              feedback.type === "success"
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-red-200 bg-red-50 text-red-700"
            }`}
          >
            {feedback.message}
          </div>
        )}
        {overviewError && (
          <div
            role="alert"
            className="flex items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            <span>{overviewError}</span>
            <button
              type="button"
              onClick={() => void loadOverview()}
              className="font-semibold underline"
            >
              Retry
            </button>
          </div>
        )}

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Latest status"
            value={latestLabel}
            detail={
              latestStatus?.latest_check
                ? formatDate(latestStatus.latest_check.checked_at)
                : "No checks recorded"
            }
          />
          <MetricCard
            label={`Uptime · ${hours === 24 ? "24h" : hours === 168 ? "7d" : "30d"}`}
            value={
              uptime?.uptime_percentage === null ||
              uptime?.uptime_percentage === undefined
                ? "—"
                : `${uptime.uptime_percentage.toFixed(2)}%`
            }
            detail={`${uptime?.successful_checks ?? 0} of ${uptime?.total_checks ?? 0} checks passed`}
          />
          <MetricCard
            label="Average response"
            value={
              responseTime?.average_ms === null ||
              responseTime?.average_ms === undefined
                ? "—"
                : `${responseTime.average_ms.toFixed(0)} ms`
            }
            detail={
              responseTime?.p95_ms === null ||
              responseTime?.p95_ms === undefined
                ? "No timing data"
                : `95th percentile ${responseTime.p95_ms} ms`
            }
          />
          <MetricCard
            label="Configuration"
            value={`Every ${monitor.check_interval}m`}
            detail={`Expected HTTP ${monitor.expected_status}`}
          />
        </section>

        <section className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm sm:p-6">
          <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
            <div>
              <h2 className="font-semibold text-gray-900">Response time</h2>
              <p className="mt-1 text-xs text-gray-500">
                Successful and failed requests in milliseconds
              </p>
            </div>
            <select
              value={hours}
              onChange={(event) => setHours(Number(event.target.value))}
              className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none focus:border-blue-500"
              aria-label="Chart time range"
            >
              <option value={24}>Last 24 hours</option>
              <option value={168}>Last 7 days</option>
              <option value={720}>Last 30 days</option>
            </select>
          </div>
          {overviewLoading ? (
            <div className="h-60 animate-pulse rounded-xl bg-gray-100" />
          ) : (
            <ResponseTimeChart points={responseTime?.points ?? []} />
          )}
          <div className="mt-5 grid grid-cols-3 gap-3 border-t border-gray-100 pt-4 text-center">
            <SmallMetric label="Minimum" value={responseTime?.minimum_ms} />
            <SmallMetric label="P95" value={responseTime?.p95_ms} />
            <SmallMetric label="Maximum" value={responseTime?.maximum_ms} />
          </div>
        </section>

        <section className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm sm:p-6">
          <div className="mb-5 flex items-start justify-between">
            <div>
              <h2 className="font-semibold text-gray-900">Check history</h2>
              <p className="mt-1 text-xs text-gray-500">
                {checks.total} recorded checks, newest first
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                void loadChecks();
                void loadOverview(false);
              }}
              disabled={checksLoading}
              className="text-xs font-semibold text-blue-600 hover:text-blue-800 disabled:opacity-40"
            >
              Refresh
            </button>
          </div>
          {checksLoading ? (
            <TableLoading label="Loading check history…" />
          ) : checksError ? (
            <InlineError message={checksError} retry={loadChecks} />
          ) : checks.items.length === 0 ? (
            <EmptyState
              title="No checks yet"
              message="Run a manual test or wait for the monitor's first scheduled check."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-150 text-left text-sm">
                <thead className="border-b border-gray-100 text-xs uppercase text-gray-400">
                  <tr>
                    <th className="pb-3 font-medium">Result</th>
                    <th className="pb-3 font-medium">HTTP status</th>
                    <th className="pb-3 font-medium">Response time</th>
                    <th className="pb-3 font-medium">Checked</th>
                    <th className="pb-3 font-medium">Message</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {checks.items.map((check) => (
                    <tr key={check.id}>
                      <td className="py-3">
                        <StatusBadge
                          status={checkLabel(check.status).toLowerCase()}
                        />
                      </td>
                      <td className="py-3 text-gray-700">
                        {check.status_code ?? "—"}
                      </td>
                      <td className="py-3 text-gray-700">
                        {check.response_time === null
                          ? "—"
                          : `${check.response_time} ms`}
                      </td>
                      <td className="whitespace-nowrap py-3 text-gray-500">
                        {formatDate(check.checked_at)}
                      </td>
                      <td className="max-w-70 truncate py-3 text-gray-500">
                        {check.error_message ?? "Expected response received"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <Pagination
            page={checks.page}
            totalPages={checks.total_pages}
            onChange={setCheckPage}
          />
        </section>

        <section className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm sm:p-6">
          <div className="mb-5">
            <h2 className="font-semibold text-gray-900">Incidents</h2>
            <p className="mt-1 text-xs text-gray-500">
              Downtime periods detected for this monitor
            </p>
          </div>
          {incidentsLoading ? (
            <TableLoading label="Loading incidents…" />
          ) : incidentsError ? (
            <InlineError message={incidentsError} retry={loadIncidents} />
          ) : incidents.items.length === 0 ? (
            <EmptyState
              title="No incidents"
              message="No downtime incidents have been recorded."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-150 text-left text-sm">
                <thead className="border-b border-gray-100 text-xs uppercase text-gray-400">
                  <tr>
                    <th className="pb-3 font-medium">Status</th>
                    <th className="pb-3 font-medium">Started</th>
                    <th className="pb-3 font-medium">Resolved</th>
                    <th className="pb-3 font-medium">Duration</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {incidents.items.map((incident) => (
                    <tr key={incident.id}>
                      <td className="py-3">
                        <StatusBadge status={incident.status} />
                      </td>
                      <td className="whitespace-nowrap py-3 text-gray-700">
                        {formatDate(incident.started_at)}
                      </td>
                      <td className="whitespace-nowrap py-3 text-gray-500">
                        {formatDate(incident.resolved_at)}
                      </td>
                      <td className="py-3 text-gray-700">
                        {formatDuration(incident.duration_minutes)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <Pagination
            page={incidents.page}
            totalPages={incidents.total_pages}
            onChange={setIncidentPage}
          />
        </section>
      </div>

      {showEdit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div
            className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl sm:p-8"
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-monitor-title"
          >
            <div className="mb-6 flex items-center justify-between">
              <h2
                id="edit-monitor-title"
                className="text-lg font-bold text-gray-900"
              >
                Edit monitor
              </h2>
              <button
                type="button"
                onClick={() => setShowEdit(false)}
                className="text-gray-400 hover:text-gray-700"
                aria-label="Close edit monitor"
              >
                ×
              </button>
            </div>
            <form onSubmit={saveMonitor} className="space-y-4">
              {formError && (
                <div
                  role="alert"
                  className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
                >
                  {formError}
                </div>
              )}
              <FormField label="Name">
                <input
                  value={form.name}
                  onChange={(event) =>
                    setForm({ ...form, name: event.target.value })
                  }
                  required
                  maxLength={255}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm outline-none focus:border-blue-500"
                />
              </FormField>
              <FormField label="URL">
                <input
                  type="url"
                  value={form.url}
                  onChange={(event) =>
                    setForm({ ...form, url: event.target.value })
                  }
                  required
                  className="w-full rounded-lg border border-gray-200 px-3 py-2.5 font-mono text-sm outline-none focus:border-blue-500"
                />
              </FormField>
              <div className="grid grid-cols-2 gap-4">
                <FormField label="Method">
                  <select
                    value={form.method}
                    onChange={(event) =>
                      setForm({ ...form, method: event.target.value })
                    }
                    className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm outline-none focus:border-blue-500"
                  >
                    {[
                      "GET",
                      "POST",
                      "PUT",
                      "PATCH",
                      "DELETE",
                      "HEAD",
                      "OPTIONS",
                    ].map((method) => (
                      <option key={method}>{method}</option>
                    ))}
                  </select>
                </FormField>
                <FormField label="Check interval">
                  <input
                    type="number"
                    min={1}
                    max={1440}
                    value={form.check_interval}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        check_interval: Number(event.target.value),
                      })
                    }
                    required
                    className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm outline-none focus:border-blue-500"
                  />
                </FormField>
              </div>
              <FormField label="Expected HTTP status">
                <input
                  type="number"
                  min={100}
                  max={599}
                  value={form.expected_status}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      expected_status: Number(event.target.value),
                    })
                  }
                  required
                  className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm outline-none focus:border-blue-500"
                />
              </FormField>
              <p className="text-xs leading-5 text-gray-500">
                Existing request headers and body are preserved. Sensitive
                header values remain encrypted and are never shown here.
              </p>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowEdit(false)}
                  className="flex-1 rounded-lg border border-gray-200 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={busyAction === "edit"}
                  className="flex-1 rounded-lg bg-gray-900 py-2.5 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
                >
                  {busyAction === "edit" ? "Saving…" : "Save changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}

function LoadingState() {
  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-7xl animate-pulse space-y-6">
        <div className="h-24 rounded-2xl bg-white" />
        <div className="grid gap-4 md:grid-cols-4">
          {[0, 1, 2, 3].map((item) => (
            <div key={item} className="h-28 rounded-2xl bg-white" />
          ))}
        </div>
        <div className="h-80 rounded-2xl bg-white" />
      </div>
    </main>
  );
}

function MetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
        {label}
      </p>
      <p className="mt-3 text-2xl font-bold text-gray-900">{value}</p>
      <p className="mt-1 truncate text-xs text-gray-500">{detail}</p>
    </div>
  );
}

function SmallMetric({
  label,
  value,
}: {
  label: string;
  value: number | null | undefined;
}) {
  return (
    <div>
      <p className="text-xs text-gray-400">{label}</p>
      <p className="mt-1 text-sm font-semibold text-gray-800">
        {value === null || value === undefined ? "—" : `${value} ms`}
      </p>
    </div>
  );
}

function TableLoading({ label }: { label: string }) {
  return (
    <div className="flex h-32 items-center justify-center text-sm text-gray-500">
      {label}
    </div>
  );
}

function InlineError({
  message,
  retry,
}: {
  message: string;
  retry: () => Promise<void>;
}) {
  return (
    <div
      role="alert"
      className="flex min-h-32 flex-col items-center justify-center gap-3 rounded-xl bg-red-50 p-5 text-center text-sm text-red-700"
    >
      <p>{message}</p>
      <button
        type="button"
        onClick={() => void retry()}
        className="font-semibold underline"
      >
        Try again
      </button>
    </div>
  );
}

function EmptyState({
  title,
  message,
}: {
  title: string;
  message: string;
}) {
  return (
    <div className="flex min-h-32 flex-col items-center justify-center rounded-xl bg-gray-50 p-5 text-center">
      <p className="text-sm font-semibold text-gray-800">{title}</p>
      <p className="mt-1 max-w-md text-xs text-gray-500">{message}</p>
    </div>
  );
}

function FormField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-gray-700">
        {label}
      </span>
      {children}
    </label>
  );
}
