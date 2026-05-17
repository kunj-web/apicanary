"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface Monitor {
  id: string;
  name: string;
  url: string;
  method: string;
  status: string;
  check_interval: number;
  expected_status: number;
}

export default function Dashboard() {
  const router = useRouter();
  const [monitors, setMonitors] = useState<Monitor[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeNav, setActiveNav] = useState("monitors");
  const [form, setForm] = useState({
    name: "",
    url: "",
    method: "GET",
    expected_status: 200,
    check_interval: 5,
  });

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  useEffect(() => {
    if (!token) { router.push("/login"); return; }
    fetchMonitors();
  }, []);

  const fetchMonitors = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/monitors", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) { router.push("/login"); return; }
      setMonitors(await res.json());
    } catch { console.error("Failed"); }
    finally { setLoading(false); }
  };

  const createMonitor = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await fetch("http://localhost:8000/api/monitors", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(form),
    });
    if (res.ok) {
      setShowForm(false);
      setForm({ name: "", url: "", method: "GET", expected_status: 200, check_interval: 5 });
      fetchMonitors();
    }
  };

  const deleteMonitor = async (id: string) => {
    await fetch(`http://localhost:8000/api/monitors/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    fetchMonitors();
  };

  const statusColor = (status: string) => {
    if (status === "active") return "bg-emerald-100 text-emerald-700";
    if (status === "paused") return "bg-yellow-100 text-yellow-700";
    return "bg-gray-100 text-gray-500";
  };

  const statusDot = (status: string) => {
    if (status === "active") return "bg-emerald-500";
    if (status === "paused") return "bg-yellow-500";
    return "bg-gray-400";
  };

  const navItems = [
    { id: "monitors", label: "Monitors", icon: "📡" },
    { id: "incidents", label: "Incidents", icon: "🚨" },
    { id: "alerts", label: "Alerts", icon: "🔔" },
    { id: "settings", label: "Settings", icon: "⚙️" },
  ];

  const upCount = monitors.filter(m => m.status === "active").length;
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
      <aside className={`
        fixed top-0 left-0 h-full w-64 bg-white border-r border-gray-100 z-30
        flex flex-col transition-transform duration-300
        ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
        md:translate-x-0 md:static md:z-auto
      `}>
        {/* Logo */}
        <div className="px-6 py-5 border-b border-gray-100 flex items-center justify-between">
          <a href="/" className="text-lg font-bold text-gray-900">🐦 APICanary</a>
          <button className="md:hidden text-gray-400 hover:text-gray-600" onClick={() => setSidebarOpen(false)}>✕</button>
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
              <p className="text-2xl font-bold text-red-500">{totalCount - upCount}</p>
              <p className="text-xs text-gray-500">Down</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-2">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => { setActiveNav(item.id); setSidebarOpen(false); }}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium mb-1 transition-colors
                ${activeNav === item.id
                  ? "bg-gray-900 text-white"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
              {item.id === "monitors" && totalCount > 0 && (
                <span className={`ml-auto text-xs px-2 py-0.5 rounded-full font-medium
                  ${activeNav === item.id ? "bg-white/20 text-white" : "bg-gray-100 text-gray-600"}`}>
                  {totalCount}
                </span>
              )}
            </button>
          ))}
        </nav>

        {/* Logout */}
        <div className="px-3 py-4 border-t border-gray-100">
          <button
            onClick={() => { localStorage.removeItem("token"); router.push("/"); }}
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
              <h1 className="text-base font-semibold text-gray-900 capitalize">{activeNav}</h1>
              <p className="text-xs text-gray-400">
                {activeNav === "monitors" ? `${totalCount} monitors, ${upCount} active` : "Coming soon"}
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
              {loading && (
                <div className="flex items-center justify-center py-20 text-gray-400">
                  <div className="text-center">
                    <div className="text-4xl mb-3">⏳</div>
                    <p>Loading monitors...</p>
                  </div>
                </div>
              )}

              {!loading && monitors.length === 0 && (
                <div className="flex items-center justify-center py-20">
                  <div className="text-center max-w-sm">
                    <div className="text-6xl mb-4">📡</div>
                    <h2 className="text-lg font-semibold text-gray-900 mb-2">No monitors yet</h2>
                    <p className="text-gray-500 text-sm mb-6">Add your first API endpoint to start monitoring it 24/7</p>
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
                    <div key={monitor.id} className="bg-white rounded-2xl border border-gray-100 p-5 hover:shadow-md transition-all group">
                      <div className="flex justify-between items-start mb-4">
                        <div className="flex items-center gap-3">
                          <div className={`w-3 h-3 rounded-full ${statusDot(monitor.status)} animate-pulse`} />
                          <div>
                            <h3 className="font-semibold text-gray-900 text-sm">{monitor.name}</h3>
                            <span className="text-xs text-gray-400">{monitor.method}</span>
                          </div>
                        </div>
                        <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${statusColor(monitor.status)}`}>
                          {monitor.status}
                        </span>
                      </div>

                      <p className="text-xs text-gray-400 break-all mb-4 bg-gray-50 rounded-lg px-3 py-2 font-mono">
                        {monitor.url}
                      </p>

                      <div className="flex justify-between items-center">
                        <div className="flex items-center gap-4 text-xs text-gray-400">
                          <span>🕐 Every {monitor.check_interval}m</span>
                          <span>✓ {monitor.expected_status}</span>
                        </div>
                        <button
                          onClick={() => deleteMonitor(monitor.id)}
                          className="text-xs text-gray-300 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {activeNav !== "monitors" && (
            <div className="flex items-center justify-center py-20">
              <div className="text-center">
                <div className="text-5xl mb-4">🚧</div>
                <h2 className="text-lg font-semibold text-gray-900 mb-2 capitalize">{activeNav}</h2>
                <p className="text-gray-400 text-sm">Coming soon</p>
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
              <h2 className="text-lg font-bold text-gray-900">Add New Monitor</h2>
              <button onClick={() => setShowForm(false)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>
            <form onSubmit={createMonitor} className="flex flex-col gap-4">
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Monitor Name</label>
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
                <label className="text-sm font-medium text-gray-700 block mb-1">URL</label>
                <input
                  type="text"
                  placeholder="https://api.example.com/health"
                  value={form.url}
                  onChange={(e) => setForm({ ...form, url: e.target.value })}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-blue-500"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">Method</label>
                  <select
                    value={form.method}
                    onChange={(e) => setForm({ ...form, method: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-blue-500"
                  >
                    <option>GET</option>
                    <option>POST</option>
                    <option>PUT</option>
                    <option>DELETE</option>
                  </select>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">Check every</label>
                  <select
                    value={form.check_interval}
                    onChange={(e) => setForm({ ...form, check_interval: Number(e.target.value) })}
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
                <label className="text-sm font-medium text-gray-700 block mb-1">Expected Status Code</label>
                <input
                  type="number"
                  value={form.expected_status}
                  onChange={(e) => setForm({ ...form, expected_status: Number(e.target.value) })}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-blue-500"
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
                  className="flex-1 bg-black text-white py-2.5 rounded-lg text-sm font-medium hover:bg-gray-800"
                >
                  Start Monitoring
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}