"use client";
import { useEffect, useState } from "react";
import { apiFetch, migrateLegacySession } from "@/app/lib/api";

export default function Home() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    let active = true;
    const checkSession = async () => {
      let response = await apiFetch("/api/auth/me");
      if (response.status === 401 && (await migrateLegacySession())) {
        response = await apiFetch("/api/auth/me");
      }
      return response.ok;
    };

    void checkSession()
      .then((isLoggedIn) => {
        if (active) setIsLoggedIn(isLoggedIn);
      })
      .catch(() => {
        if (active) setIsLoggedIn(false);
      })
      .finally(() => {
        if (active) setChecked(true);
      });
    return () => {
      active = false;
    };
  }, []);

  if (!checked) return null;

  return (
    <main className="min-h-screen bg-white">
      {/* Navbar */}
      <nav className="flex items-center justify-between px-8 py-4 border-b border-gray-100">
        <div className="text-xl font-bold text-gray-900">🐦 APICanary</div>
        <div className="flex items-center gap-6">
          <a
            href="#features"
            className="text-gray-600 hover:text-gray-900 text-sm"
          >
            Features
          </a>
          <a
            href="#how-it-works"
            className="text-gray-600 hover:text-gray-900 text-sm"
          >
            How it works
          </a>
          {isLoggedIn ? (
            <a
              href="/dashboard"
              className="bg-black text-white px-4 py-2 rounded-lg text-sm hover:bg-gray-800"
            >
              Go to Dashboard
            </a>
          ) : (
            <>
              <a
                href="/login"
                className="text-gray-600 hover:text-gray-900 text-sm"
              >
                Login
              </a>
              <a
                href="/signup"
                className="bg-black text-white px-4 py-2 rounded-lg text-sm hover:bg-gray-800"
              >
                Start Free
              </a>
            </>
          )}
        </div>
      </nav>

      {/* Hero */}
      <section className="flex flex-col items-center text-center px-8 py-24">
        <h1 className="text-5xl font-bold text-gray-900 max-w-3xl leading-tight">
          Know when your API breaks
          <span className="text-blue-600"> before your users do</span>
        </h1>
        <p className="mt-6 text-xl text-gray-500 max-w-2xl">
          APICanary watches your endpoints 24/7, tracks response times, and
          alerts you instantly when something breaks — via Telegram, Email, or
          Slack.
        </p>
        <div className="mt-10 flex gap-4">
          <a
            href={isLoggedIn ? "/dashboard" : "/signup"}
            className="bg-black text-white px-8 py-3 rounded-lg text-base font-medium hover:bg-gray-800"
          >
            {isLoggedIn ? "Go to Dashboard" : "Start Monitoring Free"}
          </a>
          <a
            href="#how-it-works"
            className="border border-gray-300 text-gray-700 px-8 py-3 rounded-lg text-base font-medium hover:border-gray-400"
          >
            See How It Works
          </a>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="bg-gray-50 px-8 py-20">
        <h2 className="text-3xl font-bold text-center text-gray-900 mb-16">
          How it works
        </h2>
        <div className="max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="text-center">
            <div className="text-4xl mb-4">1</div>
            <h3 className="font-semibold text-gray-900 mb-2">Add your API</h3>
            <p className="text-gray-500 text-sm">
              Paste your endpoint URL. Set method, headers, and check interval.
            </p>
          </div>
          <div className="text-center">
            <div className="text-4xl mb-4">2</div>
            <h3 className="font-semibold text-gray-900 mb-2">We monitor it</h3>
            <p className="text-gray-500 text-sm">
              APICanary checks your endpoint every few minutes automatically.
            </p>
          </div>
          <div className="text-center">
            <div className="text-4xl mb-4">3</div>
            <h3 className="font-semibold text-gray-900 mb-2">Get alerted</h3>
            <p className="text-gray-500 text-sm">
              Instant alert on Telegram or Email the moment something breaks.
            </p>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="px-8 py-20">
        <h2 className="text-3xl font-bold text-center text-gray-900 mb-16">
          Everything you need
        </h2>
        <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-8">
          {[
            {
              icon: "📡",
              title: "Live Uptime Dashboard",
              desc: "See all your APIs in one place. Green = up, red = down, yellow = slow.",
            },
            {
              icon: "⚡",
              title: "Instant Alerts",
              desc: "Get notified on Telegram or Email the moment your API fails.",
            },
            {
              icon: "📈",
              title: "Response Time Charts",
              desc: "Visual graphs showing performance over time.",
            },
            {
              icon: "📋",
              title: "Full Check History",
              desc: "30 days of detailed logs for every check.",
            },
            {
              icon: "🔒",
              title: "Auth Header Support",
              desc: "Securely store your API keys and authorization tokens.",
            },
            {
              icon: "📊",
              title: "Uptime Percentage",
              desc: "Track SLA compliance — 99.7% uptime this month.",
            },
          ].map((f) => (
            <div
              key={f.title}
              className="border border-gray-100 rounded-xl p-6 hover:shadow-sm transition-shadow"
            >
              <div className="text-3xl mb-3">{f.icon}</div>
              <h3 className="font-semibold text-gray-900 mb-2">{f.title}</h3>
              <p className="text-gray-500 text-sm">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="bg-black text-white px-8 py-20 text-center">
        <h2 className="text-3xl font-bold mb-4">
          Start monitoring your APIs today
        </h2>
        <p className="text-gray-400 mb-8">
          Free forever. No credit card required.
        </p>
      </section>

      {/* Footer */}
      <footer className="px-8 py-8 border-t border-gray-100 text-center text-sm text-gray-400">
        © 2024 APICanary. Built for developers.
      </footer>
    </main>
  );
}
