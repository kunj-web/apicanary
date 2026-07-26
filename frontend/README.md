# APICanary

API monitoring and alerting platform that helps developers track uptime, response times, and service health from a single dashboard.

## Features

* User authentication
* API monitor management
* Automated health checks
* Incident tracking
* Email alerts
* Monitoring dashboard
* Historical check data

## Tech Stack

### Frontend

* Next.js
* TypeScript
* Tailwind CSS

### Backend

* FastAPI
* PostgreSQL
* SQLAlchemy
* Celery
* Redis

## Getting Started

Install dependencies:

```bash
npm ci
```

Start the development server:

```bash
npm run dev
```

Open `http://localhost:3000` in your browser.

## Project Structure

```text
app/             # App Router pages, components, and API utilities
tests/unit/      # Vitest and Testing Library tests
tests/e2e/       # Playwright browser journeys
```

## Available Scripts

```bash
npm run dev      # Start development server
npm run build    # Create production build
npm start        # Start production server
npm run lint     # Run linting
npm run type-check
npm test         # Run frontend unit tests
npm run test:e2e # Run Playwright (backend required)
```

## Status

APICanary is under active development. See the root
[README](../README.md) for implemented features, environment setup, security
requirements, and roadmap items.
