# APICanary

Open-source API monitoring tool that watches your endpoints 24/7, tracks response times, and alerts you instantly when something breaks.

## 🎯 What is APICanary?

APICanary is a simple but powerful SaaS platform that monitors your API endpoints and notifies you the moment something goes wrong — via Telegram, Email, or Slack.

Instead of finding out from angry users that your API is down, APICanary checks your endpoints every few minutes and alerts you instantly.

## ✨ Features

- **Add any API endpoint** — GET, POST, PUT, DELETE requests with headers and auth
- **Live uptime dashboard** — see all your APIs in one place (green = up, red = down, yellow = slow)
- **Response time charts** — visual graphs showing performance over time
- **Full check history** — 30 days of detailed logs for every check
- **Instant alerts** — get notified on Telegram, Email, or Slack the moment an API fails
- **Uptime percentage** — track SLA compliance (e.g., 99.7% uptime this month)
- **Team workspaces** — invite teammates and share monitoring access
- **Public status page** — show your users your service status (like Stripe's status page)
- **Auth headers support** — securely store API keys and authorization tokens

## 🚀 Quick Start

### Prerequisites

- Node.js 18+
- Python 3.10+
- PostgreSQL 14+
- Redis
- Docker (optional)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/apicanary
cd apicanary

# Install frontend dependencies
cd frontend
npm install

# Install backend dependencies
cd ../backend
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your settings

# Run database migrations
alembic upgrade head

# Start the backend (in backend folder)
python main.py

# Start the frontend (in frontend folder)
npm run dev
```

Visit `http://localhost:3000` to start using APICanary.

## 📚 Documentation

- [Architecture](./docs/ARCHITECTURE.md) — how APICanary works under the hood
- [API Reference](./docs/API.md) — all backend endpoints
- [Deployment](./docs/DEPLOYMENT.md) — how to deploy to production
- [Contributing](./CONTRIBUTING.md) — how to contribute

## 🏗️ Tech Stack

**Frontend:**
- Next.js 14 + TypeScript
- React + TailwindCSS
- Recharts for graphs

**Backend:**
- Python 3.10 + FastAPI
- SQLAlchemy ORM
- Celery + Redis for background jobs
- PostgreSQL database

**Deployment:**
- Vercel (frontend)
- Railway (backend + database + Redis)

## 📄 Project Structure

```
apicanary/
├── frontend/              # Next.js React app
│   ├── app/             # App router pages
│   ├── components/      # React components
│   ├── lib/             # Utilities and helpers
│   └── public/          # Static assets
├── backend/               # Python FastAPI
│   ├── app/             # FastAPI application
│   ├── models/          # Database models
│   ├── schemas/         # Pydantic schemas
│   ├── services/        # Business logic
│   ├── tasks/           # Celery tasks
│   └── migrations/      # Alembic migrations
├── docs/                  # Documentation
├── docker-compose.yml     # Local development setup
└── README.md             # This file
```

## 🔐 Security

Current security controls include:

- JWT bearer authentication for API clients
- HttpOnly, SameSite browser session cookies with CSRF checks
- Encrypted and response-redacted sensitive monitor headers
- Runtime blocking of private, loopback, link-local, and reserved targets
- Strict monitor URL, HTTP method, alert type, and recipient validation

For production, set `ENVIRONMENT=production`, provide unique
`SECRET_KEY` and `MONITOR_ENCRYPTION_KEY` values of at least 32 characters,
and set `TRUSTED_ORIGINS` to the exact frontend origins. The frontend uses
the server-only `BACKEND_URL` setting to proxy `/api` requests; see the
included `.env.example` files.

## 📝 License

This project is licensed under the MIT License — see the [LICENSE](./LICENSE) file for details.

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

## 💬 Community

- **Issues & Bug Reports** — [GitHub Issues](https://github.com/yourusername/apicanary/issues)
- **Discussions** — [GitHub Discussions](https://github.com/yourusername/apicanary/discussions)

## 📧 Contact

Have questions? Open an issue or reach out on [Twitter](https://twitter.com/yourhandle).

## 🙏 Acknowledgments

Built with inspiration from Postman, Uptime Robot, and Better Uptime.

---

**Made with ❤️ for developers who want peace of mind.**
