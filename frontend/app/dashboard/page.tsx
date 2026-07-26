"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  apiFetch,
  authenticatedFetch,
  clearLegacyToken,
} from "@/app/lib/api";
import {
  apiErrorMessage,
  formatDate,
  formatDuration,
  type Incident,
  type Monitor,
  type PaginatedResponse,
} from "@/app/lib/monitoring";

interface Alert {
  id: string;
  monitor_id: string;
  alert_type: string;
  recipient: string;
  threshold_failures: number;
  is_active: boolean;
}

function AlertsPanel({
  monitors,
}: {
  monitors: Monitor[];
}) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    monitor_id: "",
    alert_type: "email",
    recipient: "",
    threshold_failures: 1,
  });

  const fetchAlerts = useCallback(async (): Promise<Alert[]> => {
    const res = await authenticatedFetch("/api/alerts");
    if (!res.ok) {
      throw new Error(await apiErrorMessage(res, "Could not load alerts"));
    }
    return res.json();
  }, []);

  useEffect(() => {
    let active = true;
    void fetchAlerts()
      .then((nextAlerts) => {
        if (active) {
          setAlerts(nextAlerts);
          setError(null);
        }
      })
      .catch((fetchError) => {
        if (active) {
          setError(
            fetchError instanceof Error
              ? fetchError.message
              : "Could not load alerts",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [fetchAlerts]);

  const createAlert = async (e: React.SyntheticEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const res = await authenticatedFetch("/api/alerts", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        throw new Error(await apiErrorMessage(res, "Could not create alert"));
      }
      setShowForm(false);
      setForm({
        monitor_id: "",
        alert_type: "email",
        recipient: "",
        threshold_failures: 1,
      });
      const nextAlerts = await fetchAlerts();
      setAlerts(nextAlerts);
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Could not create alert",
      );
    } finally {
      setSaving(false);
    }
  };

  const deleteAlert = async (id: string) => {
    setSaving(true);
    setError(null);
    try {
      const response = await authenticatedFetch(`/api/alerts/${id}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(
          await apiErrorMessage(response, "Could not delete alert"),
        );
      }
      setAlerts(await fetchAlerts());
    } catch (deleteError) {
      setError(
        deleteError instanceof Error
          ? deleteError.message
          : "Could not delete alert",
      );
    } finally {
      setSaving(false);
    }
  };

  const getMonitorName = (id: string) =>
    monitors.find((m) => m.id === id)?.name || "Unknown Monitor";

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-base font-semibold text-gray-900">
            Email Alerts
          </h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Get notified when a monitor goes down
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="bg-black text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-800 flex items-center gap-2"
        >
          <span>+</span> Add Alert
        </button>
      </div>

      {error && (
        <div
          role="alert"
          className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {error}
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center py-20 text-sm text-gray-500">
          Loading alerts…
        </div>
      )}

      {!loading && alerts.length === 0 && !showForm && (
        <div className="flex items-center justify-center py-20">
          <div className="text-center">
            <div className="text-5xl mb-4">🔔</div>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">
              No alerts yet
            </h2>
            <p className="text-gray-400 text-sm mb-6">
              Add an alert to get notified when your API goes down
            </p>
            <button
              onClick={() => setShowForm(true)}
              className="bg-black text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-gray-800"
            >
              + Add your first alert
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {alerts.map((alert) => (
          <div
            key={alert.id}
            className="bg-white rounded-2xl border border-gray-100 p-5 hover:shadow-md transition-all group"
          >
            <div className="flex justify-between items-start mb-3">
              <div className="flex items-center gap-2">
                <span className="text-lg">📧</span>
                <span className="text-sm font-semibold text-gray-900">
                  Email Alert
                </span>
              </div>
              <span
                className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                  alert.is_active
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-gray-100 text-gray-500"
                }`}
              >
                {alert.is_active ? "Active" : "Inactive"}
              </span>
            </div>
            <p className="text-xs text-gray-500 mb-1">
              Monitor:{" "}
              <span className="font-medium text-gray-700">
                {getMonitorName(alert.monitor_id)}
              </span>
            </p>
            <p className="text-xs text-gray-500 mb-1">
              Notify:{" "}
              <span className="font-medium text-gray-700">
                {alert.recipient}
              </span>
            </p>
            <p className="text-xs text-gray-500 mb-4">
              Trigger after:{" "}
              <span className="font-medium text-gray-700">
                {alert.threshold_failures} failure(s)
              </span>
            </p>
            <div className="flex justify-end">
              <button
                onClick={() => deleteAlert(alert.id)}
                disabled={saving}
                className="text-xs text-gray-300 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 px-4">
          <div className="bg-white rounded-2xl p-8 w-full max-w-md shadow-2xl">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-lg font-bold text-gray-900">
                Add Email Alert
              </h2>
              <button
                onClick={() => setShowForm(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>
            <form onSubmit={createAlert} className="flex flex-col gap-4">
              {error && (
                <div
                  role="alert"
                  className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
                >
                  {error}
                </div>
              )}
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">
                  Monitor
                </label>
                <select
                  value={form.monitor_id}
                  onChange={(e) =>
                    setForm({ ...form, monitor_id: e.target.value })
                  }
                  className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-blue-500"
                  required
                >
                  <option value="">Select a monitor</option>
                  {monitors.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">
                  Email Address
                </label>
                <input
                  type="email"
                  placeholder="you@example.com"
                  value={form.recipient}
                  onChange={(e) =>
                    setForm({ ...form, recipient: e.target.value })
                  }
                  className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-blue-500"
                  required
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">
                  Trigger after how many failures?
                </label>
                <select
                  value={form.threshold_failures}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      threshold_failures: Number(e.target.value),
                    })
                  }
                  className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-blue-500"
                >
                  <option value={1}>1 failure (immediate)</option>
                  <option value={2}>2 failures</option>
                  <option value={3}>3 failures</option>
                </select>
              </div>
              <div className="flex gap-3 mt-2">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="flex-1 border border-gray-200 text-gray-700 py-2.5 rounded-lg text-sm font-medium hover:border-gray-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 bg-black text-white py-2.5 rounded-lg text-sm font-medium hover:bg-gray-800"
                >
                  {saving ? "Saving…" : "Save Alert"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function IncidentsPanel() {
  const router = useRouter();
  const [data, setData] = useState<PaginatedResponse<Incident>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
    total_pages: 0,
  });
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<"all" | "ongoing" | "resolved">(
    "all",
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadIncidents = useCallback(async () => {
    await Promise.resolve();
    setLoading(true);
    setError(null);
    try {
      const statusQuery = filter === "all" ? "" : `&status=${filter}`;
      const response = await authenticatedFetch(
        `/api/incidents?page=${page}&page_size=20${statusQuery}`,
      );
      if (response.status === 401) {
        router.replace("/login");
        return;
      }
      if (!response.ok) {
        throw new Error(
          await apiErrorMessage(response, "Could not load incidents"),
        );
      }
      setData(await response.json());
    } catch (fetchError) {
      setError(
        fetchError instanceof Error
          ? fetchError.message
          : "Could not load incidents",
      );
    } finally {
      setLoading(false);
    }
  }, [filter, page, router]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadIncidents();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadIncidents]);

  return (
    <div>
      <div className="mb-6 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-base font-semibold text-gray-900">
            Incidents
          </h2>
          <p className="mt-0.5 text-xs text-gray-400">
            Downtime across all of your monitors
          </p>
        </div>
        <select
          value={filter}
          onChange={(event) => {
            setFilter(
              event.target.value as "all" | "ongoing" | "resolved",
            );
            setPage(1);
          }}
          className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none focus:border-blue-500"
          aria-label="Filter incidents"
        >
          <option value="all">All incidents</option>
          <option value="ongoing">Ongoing</option>
          <option value="resolved">Resolved</option>
        </select>
      </div>

      {loading ? (
        <div className="flex min-h-64 items-center justify-center rounded-2xl border border-gray-100 bg-white text-sm text-gray-500">
          Loading incidents…
        </div>
      ) : error ? (
        <div
          role="alert"
          className="flex min-h-64 flex-col items-center justify-center gap-3 rounded-2xl border border-red-100 bg-red-50 p-6 text-center text-sm text-red-700"
        >
          <p>{error}</p>
          <button
            type="button"
            onClick={() => void loadIncidents()}
            className="font-semibold underline"
          >
            Try again
          </button>
        </div>
      ) : data.items.length === 0 ? (
        <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-gray-100 bg-white p-6 text-center">
          <h3 className="font-semibold text-gray-900">
            {filter === "all"
              ? "No incidents recorded"
              : `No ${filter} incidents`}
          </h3>
          <p className="mt-2 text-sm text-gray-500">
            Downtime events will appear here when a monitor fails.
          </p>
        </div>
      ) : (
        <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full min-w-175 text-left text-sm">
              <thead className="border-b border-gray-100 text-xs uppercase text-gray-400">
                <tr>
                  <th className="pb-3 font-medium">Monitor</th>
                  <th className="pb-3 font-medium">Status</th>
                  <th className="pb-3 font-medium">Started</th>
                  <th className="pb-3 font-medium">Resolved</th>
                  <th className="pb-3 font-medium">Duration</th>
                  <th className="pb-3 font-medium" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.items.map((incident) => (
                  <tr key={incident.id}>
                    <td className="py-4 font-medium text-gray-900">
                      {incident.monitor_name}
                    </td>
                    <td className="py-4">
                      <span
                        className={`rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${
                          incident.status === "ongoing"
                            ? "bg-red-100 text-red-700"
                            : "bg-emerald-100 text-emerald-700"
                        }`}
                      >
                        {incident.status}
                      </span>
                    </td>
                    <td className="whitespace-nowrap py-4 text-gray-600">
                      {formatDate(incident.started_at)}
                    </td>
                    <td className="whitespace-nowrap py-4 text-gray-500">
                      {formatDate(incident.resolved_at)}
                    </td>
                    <td className="py-4 text-gray-600">
                      {formatDuration(incident.duration_minutes)}
                    </td>
                    <td className="py-4 text-right">
                      <Link
                        href={`/dashboard/monitors/${incident.monitor_id}`}
                        className="text-xs font-semibold text-blue-600 hover:text-blue-800"
                      >
                        View monitor
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.total_pages > 1 && (
            <div className="mt-4 flex items-center justify-between border-t border-gray-100 pt-4">
              <span className="text-xs text-gray-500">
                Page {data.page} of {data.total_pages}
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setPage((current) => current - 1)}
                  disabled={data.page <= 1}
                  className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-700 disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  type="button"
                  onClick={() => setPage((current) => current + 1)}
                  disabled={data.page >= data.total_pages}
                  className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-700 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Dashboard() {
  const router = useRouter();
  const [monitors, setMonitors] = useState<Monitor[]>([]);
  const [loading, setLoading] = useState(true);
  const [monitorError, setMonitorError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeNav, setActiveNav] = useState("monitors");
  const [busyMonitorId, setBusyMonitorId] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);
  const [form, setForm] = useState({
    name: "",
    url: "",
    method: "GET",
    expected_status: 200,
    check_interval: 5,
  });

  const fetchMonitors = useCallback(async (): Promise<Monitor[] | null> => {
    const res = await authenticatedFetch("/api/monitors");
    if (res.status === 401) {
      router.push("/login");
      return null;
    }
    if (!res.ok) {
      throw new Error(
        await apiErrorMessage(res, "Failed to load monitors"),
      );
    }
    return res.json();
  }, [router]);

  useEffect(() => {
    let active = true;
    void fetchMonitors()
      .then((nextMonitors) => {
        if (active && nextMonitors) {
          setMonitors(nextMonitors);
          setMonitorError(null);
        }
      })
      .catch((fetchError) => {
        if (active) {
          setMonitorError(
            fetchError instanceof Error
              ? fetchError.message
              : "Failed to load monitors",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [fetchMonitors]);

  const refreshMonitors = useCallback(async () => {
    try {
      const nextMonitors = await fetchMonitors();
      if (nextMonitors) {
        setMonitors(nextMonitors);
        setMonitorError(null);
      }
    } catch (refreshError) {
      setMonitorError(
        refreshError instanceof Error
          ? refreshError.message
          : "Failed to refresh monitors",
      );
    }
  }, [fetchMonitors]);

  const createMonitor = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setActionFeedback(null);
    try {
      const res = await authenticatedFetch("/api/monitors", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        throw new Error(
          await apiErrorMessage(res, "Could not create monitor"),
        );
      }
      setShowForm(false);
      setForm({
        name: "",
        url: "",
        method: "GET",
        expected_status: 200,
        check_interval: 5,
      });
      await refreshMonitors();
      setActionFeedback({
        type: "success",
        message: "Monitor created.",
      });
    } catch (createError) {
      setActionFeedback({
        type: "error",
        message:
          createError instanceof Error
            ? createError.message
            : "Could not create monitor",
      });
    } finally {
      setCreating(false);
    }
  };

  const deleteMonitor = async (id: string) => {
    const monitor = monitors.find((item) => item.id === id);
    if (
      !window.confirm(
        `Delete ${monitor?.name ?? "this monitor"} and all of its history?`,
      )
    ) {
      return;
    }
    setBusyMonitorId(id);
    setActionFeedback(null);
    try {
      const response = await authenticatedFetch(`/api/monitors/${id}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(
          await apiErrorMessage(response, "Could not delete monitor"),
        );
      }
      await refreshMonitors();
      setActionFeedback({
        type: "success",
        message: "Monitor deleted.",
      });
    } catch (deleteError) {
      setActionFeedback({
        type: "error",
        message:
          deleteError instanceof Error
            ? deleteError.message
            : "Could not delete monitor",
      });
    } finally {
      setBusyMonitorId(null);
    }
  };

  const runMonitorAction = async (
    monitor: Monitor,
    action: "test" | "pause" | "resume",
  ) => {
    setBusyMonitorId(monitor.id);
    setActionFeedback(null);

    try {
      const res = await authenticatedFetch(
        `/api/monitors/${monitor.id}/${action}`,
        {
          method: "POST",
        },
      );
      const data = await res.json().catch(() => ({}));

      if (res.status === 401) {
        router.push("/login");
        return;
      }
      if (!res.ok) {
        throw new Error(data.detail || `Could not ${action} monitor`);
      }

      if (action !== "test") {
        await refreshMonitors();
      }
      setActionFeedback({
        type: "success",
        message:
          action === "test"
            ? `${monitor.name}: manual check queued`
            : `${monitor.name}: monitoring ${action === "pause" ? "paused" : "resumed"}`,
      });
    } catch (error) {
      setActionFeedback({
        type: "error",
        message:
          error instanceof Error ? error.message : "Monitor action failed",
      });
    } finally {
      setBusyMonitorId(null);
    }
  };

  const statusColor = (status: string) => {
    if (status === "active") return "bg-emerald-100 text-emerald-700";
    if (status === "down") return "bg-red-100 text-red-700";
    if (status === "paused") return "bg-yellow-100 text-yellow-700";
    return "bg-gray-100 text-gray-500";
  };

  const statusDot = (status: string) => {
    if (status === "active") return "bg-emerald-500";
    if (status === "down") return "bg-red-500";
    if (status === "paused") return "bg-yellow-500";
    return "bg-gray-400";
  };

  const navItems = [
    { id: "monitors", label: "Monitors", icon: "📡" },
    { id: "incidents", label: "Incidents", icon: "🚨" },
    { id: "alerts", label: "Alerts", icon: "🔔" },
    { id: "settings", label: "Settings", icon: "⚙️" },
  ];

  const upCount = monitors.filter((m) => m.status === "active").length;
  const downCount = monitors.filter((m) => m.status === "down").length;
  const totalCount = monitors.length;

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar overlay for mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-20 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
        fixed top-0 left-0 h-full w-64 bg-white border-r border-gray-100 z-30
        flex flex-col transition-transform duration-300
        ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
        md:translate-x-0 md:static md:z-auto
      `}
      >
        {/* Logo */}
        <div className="px-6 py-5 border-b border-gray-100 flex items-center justify-between">
          <Link href="/" className="text-lg font-bold text-gray-900">
            🐦 APICanary
          </Link>
          <button
            className="md:hidden text-gray-400 hover:text-gray-600"
            onClick={() => setSidebarOpen(false)}
          >
            ✕
          </button>
        </div>

        {/* Stats */}
        <div className="mx-4 my-4 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-4 border border-blue-100">
          <p className="text-xs text-blue-600 font-medium mb-1">Overview</p>
          <div className="flex justify-between mt-2">
            <div className="text-center">
              <p className="text-2xl font-bold text-gray-900">{totalCount}</p>
              <p className="text-xs text-gray-500">Total</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-emerald-600">{upCount}</p>
              <p className="text-xs text-gray-500">Active</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-red-500">
                {downCount}
              </p>
              <p className="text-xs text-gray-500">Down</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-2">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => {
                setActiveNav(item.id);
                setSidebarOpen(false);
              }}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium mb-1 transition-colors
                ${
                  activeNav === item.id
                    ? "bg-gray-900 text-white"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
              {item.id === "monitors" && totalCount > 0 && (
                <span
                  className={`ml-auto text-xs px-2 py-0.5 rounded-full font-medium
                  ${activeNav === item.id ? "bg-white/20 text-white" : "bg-gray-100 text-gray-600"}`}
                >
                  {totalCount}
                </span>
              )}
            </button>
          ))}
        </nav>

        {/* Logout */}
        <div className="px-3 py-4 border-t border-gray-100">
          <button
            onClick={async () => {
              await apiFetch("/api/auth/logout", { method: "POST" });
              clearLegacyToken();
              router.push("/");
            }}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-gray-600 hover:bg-red-50 hover:text-red-600 transition-colors"
          >
            <span>🚪</span>
            <span>Logout</span>
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between sticky top-0 z-10">
          <div className="flex items-center gap-4">
            <button
              className="md:hidden text-gray-500 hover:text-gray-900"
              onClick={() => setSidebarOpen(true)}
            >
              ☰
            </button>
            <div>
              <h1 className="text-base font-semibold text-gray-900 capitalize">
                {activeNav}
              </h1>
              <p className="text-xs text-gray-400">
                {activeNav === "monitors"
                  ? `${totalCount} monitors, ${upCount} active`
                  : activeNav === "incidents"
                    ? "Downtime and recovery history"
                    : activeNav === "alerts"
                      ? "Notification rules"
                      : "Account preferences"}
              </p>
            </div>
          </div>
          {activeNav === "monitors" && (
            <button
              onClick={() => setShowForm(true)}
              className="bg-black text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-800 flex items-center gap-2"
            >
              <span>+</span>
              <span className="hidden sm:inline">Add Monitor</span>
            </button>
          )}
        </header>

        {/* Page content */}
        <main className="flex-1 p-6">
          {activeNav === "monitors" && (
            <>
              {actionFeedback && (
                <div
                  className={`mb-4 rounded-lg border px-4 py-3 text-sm ${
                    actionFeedback.type === "success"
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : "border-red-200 bg-red-50 text-red-700"
                  }`}
                  role="status"
                >
                  {actionFeedback.message}
                </div>
              )}

              {monitorError && (
                <div
                  role="alert"
                  className="mb-4 flex items-center justify-between gap-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
                >
                  <span>{monitorError}</span>
                  <button
                    type="button"
                    onClick={() => void refreshMonitors()}
                    className="font-semibold underline"
                  >
                    Retry
                  </button>
                </div>
              )}

              {loading && (
                <div className="flex items-center justify-center py-20 text-gray-400">
                  <div className="text-center">
                    <div className="text-4xl mb-3">⏳</div>
                    <p>Loading monitors...</p>
                  </div>
                </div>
              )}

              {!loading && !monitorError && monitors.length === 0 && (
                <div className="flex items-center justify-center py-20">
                  <div className="text-center max-w-sm">
                    <div className="text-6xl mb-4">📡</div>
                    <h2 className="text-lg font-semibold text-gray-900 mb-2">
                      No monitors yet
                    </h2>
                    <p className="text-gray-500 text-sm mb-6">
                      Add your first API endpoint to start monitoring it 24/7
                    </p>
                    <button
                      onClick={() => setShowForm(true)}
                      className="bg-black text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-gray-800"
                    >
                      + Add your first monitor
                    </button>
                  </div>
                </div>
              )}

              {!loading && monitors.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {monitors.map((monitor) => (
                    <div
                      key={monitor.id}
                      className="bg-white rounded-2xl border border-gray-100 p-5 hover:shadow-md transition-all group"
                    >
                      <div className="flex justify-between items-start mb-4">
                        <div className="flex items-center gap-3">
                          <div
                            className={`w-3 h-3 rounded-full ${statusDot(monitor.status)} animate-pulse`}
                          />
                          <div>
                            <h3 className="font-semibold text-gray-900 text-sm">
                              <Link
                                href={`/dashboard/monitors/${monitor.id}`}
                                className="hover:text-blue-600"
                              >
                                {monitor.name}
                              </Link>
                            </h3>
                            <span className="text-xs text-gray-400">
                              {monitor.method}
                            </span>
                          </div>
                        </div>
                        <span
                          className={`text-xs px-2.5 py-1 rounded-full font-medium ${statusColor(monitor.status)}`}
                        >
                          {monitor.status}
                        </span>
                      </div>

                      <p className="text-xs text-gray-400 break-all mb-4 bg-gray-50 rounded-lg px-3 py-2 font-mono">
                        {monitor.url}
                      </p>

                      <div className="flex justify-between items-center gap-3">
                        <div className="flex items-center gap-4 text-xs text-gray-400">
                          <span>🕐 Every {monitor.check_interval}m</span>
                          <span>✓ {monitor.expected_status}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Link
                            href={`/dashboard/monitors/${monitor.id}`}
                            className="text-xs font-semibold text-gray-700 hover:text-black"
                          >
                            View
                          </Link>
                          <button
                            onClick={() => runMonitorAction(monitor, "test")}
                            disabled={busyMonitorId === monitor.id}
                            className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-40"
                          >
                            Test
                          </button>
                          <button
                            onClick={() =>
                              runMonitorAction(
                                monitor,
                                monitor.status === "paused"
                                  ? "resume"
                                  : "pause",
                              )
                            }
                            disabled={busyMonitorId === monitor.id}
                            className="text-xs text-amber-600 hover:text-amber-800 disabled:opacity-40"
                          >
                            {monitor.status === "paused" ? "Resume" : "Pause"}
                          </button>
                          <button
                            onClick={() => deleteMonitor(monitor.id)}
                            disabled={busyMonitorId === monitor.id}
                            className="text-xs text-gray-400 hover:text-red-500 transition-colors disabled:opacity-40"
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {activeNav === "alerts" && (
            <AlertsPanel monitors={monitors} />
          )}

          {activeNav === "incidents" && <IncidentsPanel />}

          {activeNav === "settings" && (
            <div className="flex items-center justify-center py-20">
              <div className="text-center">
                <div className="text-5xl mb-4">🚧</div>
                <h2 className="text-lg font-semibold text-gray-900 mb-2 capitalize">
                  {activeNav}
                </h2>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Add Monitor Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 px-4">
          <div className="bg-white rounded-2xl p-8 w-full max-w-md shadow-2xl">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-lg font-bold text-gray-900">
                Add New Monitor
              </h2>
              <button
                onClick={() => setShowForm(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>
            <form onSubmit={createMonitor} className="flex flex-col gap-4">
              {actionFeedback?.type === "error" && (
                <div
                  role="alert"
                  className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
                >
                  {actionFeedback.message}
                </div>
              )}
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">
                  Monitor Name
                </label>
                <input
                  type="text"
                  placeholder="e.g. Login API"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-blue-500"
                  required
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">
                  URL
                </label>
                <input
                  type="url"
                  placeholder="https://api.example.com/health"
                  value={form.url}
                  onChange={(e) => setForm({ ...form, url: e.target.value })}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-blue-500"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">
                    Method
                  </label>
                  <select
                    value={form.method}
                    onChange={(e) =>
                      setForm({ ...form, method: e.target.value })
                    }
                    className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-blue-500"
                  >
                    <option>GET</option>
                    <option>POST</option>
                    <option>PUT</option>
                    <option>PATCH</option>
                    <option>DELETE</option>
                    <option>HEAD</option>
                    <option>OPTIONS</option>
                  </select>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">
                    Check every
                  </label>
                  <select
                    value={form.check_interval}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        check_interval: Number(e.target.value),
                      })
                    }
                    className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-blue-500"
                  >
                    <option value={1}>1 min</option>
                    <option value={5}>5 min</option>
                    <option value={10}>10 min</option>
                    <option value={30}>30 min</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">
                  Expected Status Code
                </label>
                <input
                  type="number"
                  min={100}
                  max={599}
                  value={form.expected_status}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      expected_status: Number(e.target.value),
                    })
                  }
                  className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-blue-500"
                  required
                />
              </div>
              <div className="flex gap-3 mt-2">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="flex-1 border border-gray-200 text-gray-700 py-2.5 rounded-lg text-sm font-medium hover:border-gray-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="flex-1 bg-black text-white py-2.5 rounded-lg text-sm font-medium hover:bg-gray-800 disabled:opacity-50"
                >
                  {creating ? "Creating…" : "Start Monitoring"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
