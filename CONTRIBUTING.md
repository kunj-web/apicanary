# Contributing to APICanary

Thank you for your interest in contributing to APICanary! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful, inclusive, and professional. We're all learning and building together.

## Getting Started

### 1. Fork and Clone

```bash
# Fork the repo on GitHub, then clone your fork
git clone https://github.com/yourusername/apicanary
cd apicanary
git remote add upstream https://github.com/originalrepo/apicanary
```

### 2. Create a Branch

Always create a feature branch from `dev`:

```bash
git checkout dev
git pull upstream dev
git checkout -b feature/your-feature-name
```

Branch naming conventions:
- `feature/` — new feature (e.g., `feature/slack-alerts`)
- `bugfix/` — bug fix (e.g., `bugfix/dashboard-crash`)
- `docs/` — documentation (e.g., `docs/api-guide`)
- `refactor/` — code cleanup (e.g., `refactor/auth-module`)

### 3. Make Changes

- Follow the code style of the project
- Write clean, readable code
- Add comments for complex logic
- Keep commits atomic and logical

### 4. Test Your Changes

**Frontend:**
```bash
cd frontend
npm run lint
npm run type-check
npm run test
```

**Backend:**
```bash
cd backend
python -m pytest
black --check .
flake8 .
```

### 5. Commit and Push

```bash
git add .
git commit -m "feat: add Slack alert support"
git push origin feature/your-feature-name
```

**Commit message format:**
- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation
- `refactor:` — code cleanup
- `test:` — tests
- `chore:` — maintenance

Example: `fix: prevent duplicate API checks`

### 6. Open a Pull Request

- Push to your fork and open a PR against the `dev` branch
- Describe what you changed and why
- Link any related issues
- Make sure all checks pass

## Code Standards

### Frontend (TypeScript + React)

```typescript
// Use TypeScript types
interface Monitor {
  id: string;
  name: string;
  url: string;
  status: "up" | "down" | "slow";
}

// Use functional components with hooks
export function MonitorCard({ monitor }: { monitor: Monitor }) {
  const [loading, setLoading] = useState(false);

  return (
    <div className="monitor-card">
      {/* Component code */}
    </div>
  );
}
```

### Backend (Python + FastAPI)

```python
# Use type hints
from typing import List
from fastapi import FastAPI, HTTPException
from sqlalchemy.orm import Session

# Clear, descriptive names
@app.post("/monitors")
async def create_monitor(
    monitor_data: MonitorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> MonitorResponse:
    """Create a new API monitor for the user."""
    # Implementation
    pass
```

## PR Checklist

Before submitting your PR:

- [ ] Branch is based on latest `dev`
- [ ] Code follows project style
- [ ] Tests pass locally
- [ ] No console errors or warnings
- [ ] Commit messages are clear
- [ ] PR description explains changes
- [ ] Related issues are linked

## Review Process

1. Maintainer reviews your PR
2. You address feedback
3. Maintainer approves and merges
4. Your contribution is live! 🎉

## Need Help?

- Check existing [issues](https://github.com/yourusername/apicanary/issues)
- Read the [docs](./docs/)
- Open a [discussion](https://github.com/yourusername/apicanary/discussions)

## What We're Looking For

- Bug fixes with test cases
- New features with documentation
- Performance improvements
- Better error messages
- Improved documentation
- Accessibility improvements

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Thank you for making APICanary better!** 🙌