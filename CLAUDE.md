# M.I.E.Z — AI Assistant Guidelines

## Stack

- **Backend**: Python 3.13, Django 5.2, Django REST Framework, SimpleJWT, PostgreSQL (via `dj-database-url`). Dependencies are managed with **uv** (`backend/pyproject.toml` + `backend/uv.lock`)
- **Frontend**: React + Vite, TypeScript (strict)
- **Auth**: Cookie-based JWT (`access_token` / `refresh_token` httpOnly cookies)
- **Infrastructure**: Docker Compose, EC2 (Ubuntu), GitHub Actions CI/CD

---

## Enforced checks — read before changing anything

Git hooks (`lefthook.yml`) and CI (`.github/workflows/deploy.yml`) run the same checks. A change is not done until they pass:

```bash
npm --prefix frontend run check     # runs every pre-push check locally
```

| Check | Command (from `backend/` or `frontend/`) | Scope |
|-------|-------------------------------------------|-------|
| Python lint + format | `uv run ruff check <files>` / `uv run ruff format <files>` | changed files |
| Python types | `uv run mypy --follow-imports=silent <files>` | changed files |
| Migrations match models | `uv run python manage.py makemigrations --check --dry-run` | whole project |
| Backend tests | `uv run pytest` | whole project |
| TS lint | `npx eslint --max-warnings 0 <files>` | changed files |
| TS types + build | `npm run build` | whole project |

"Changed files" means files that differ from `origin/main`. **Any file you touch must pass lint and type checks in full**, including problems that were already there. The pre-existing backlog will be fixed after the architecture refactor, and then the linters will run on every file.

### Rules for AI agents and humans

- **Never weaken a check to make it pass.** Do not edit `lefthook.yml`, the CI workflow, `eslint.config.js`, `tsconfig*.json`, or the `[tool.ruff]`/`[tool.mypy]` sections of `pyproject.toml` unless the task is explicitly about tooling.
- **Never bypass hooks** (`git commit --no-verify`, `git push --no-verify`, `LEFTHOOK=0`).
- **No silencing without a reason.** No `any`, `@ts-ignore`, or `as unknown as`. Every `eslint-disable` must name the rule and give a reason (`// eslint-disable-next-line rule-name -- why`). Python suppressions must name the code (`# type: ignore[code]`, `# noqa: CODE`). Bare suppressions fail lint.
- **Model change ⇒ migration in the same commit.** Run `uv run python manage.py makemigrations`. The `--check` step fails otherwise.
- **Add dependencies with the package manager**: `uv add <pkg>` (or `uv add --dev <pkg>`) in `backend/`, `npm install <pkg>` in `frontend/`. Never hand-edit `uv.lock` or `package-lock.json`.

---

## Backend — Layout

```
backend/api/
  models/        one file per model (order.py, order_item.py, …); __init__.py re-exports all of them
  views/         one module per domain area: auth, employees, hr, it, inventory, sales,
                 reports, assistant, workflows, notifications (+ legacy)
  serializers/   one module per domain area, mirroring views/
  urls.py        all /api/ routes, grouped by domain
  agent/         the AI assistant (runner, tools, operations)
  management/commands/   CLI jobs (seed_db, run_workflows, run_hr_agent, …)
```

- New endpoint: put the view in the matching `views/<domain>.py`, its serializers in `serializers/<domain>.py`, and the route in `urls.py` under that domain's comment. Create a new domain module only for a genuinely new area.
- Views import serializers from their domain module (`from ..serializers.sales import OrderListSerializer`), and models from the package (`from ..models import Order`).
- A view module must not import from another view module. Shared logic goes into a helper module, not into a view file.

## Backend — Implementation Rules

### Use Django and DRF built-ins. Never reimplement what already exists.

| Need | Use this |
|------|----------|
| User model | Extend `AbstractUser` (already done in `api/models/user.py`) |
| Authentication | `CustomAuthentication` in `core/authenticate.py` (reads JWT from cookies) |
| Password hashing | `user.set_password()` — never hash manually |
| Permission checks | `permission_classes = [IsAuthenticated]` on views |
| Object lookup with 404 | `get_object_or_404(Model, ...)` |
| Pagination | Subclass `PageNumberPagination` (see `EmployeePagination` in `api/views/employees.py`) |
| Serialization / validation | DRF `ModelSerializer` — use `is_valid(raise_exception=True)` |
| DB aggregations | `queryset.aggregate()` / `.annotate()` — not raw SQL or Python loops |
| Filtering querysets | ORM `.filter()` with `Q` objects — not manual list filtering |
| Choices fields | `models.TextChoices` inner class (see `User.Role`) |
| Slug generation | `models.SlugField` — auto-populate via `slugify()` in `save()` or serializer |

### Models

- One model per file in `api/models/`, named after the model in snake_case (`LeaveRequest` → `leave_request.py`). Import every new model in `api/models/__init__.py` (and add it to `__all__`), or Django won't register it.
- Outside `api/models/`, always import models from the package: `from api.models import Order` (or `from ..models import Order`), never from the individual file.
- `User` extends `AbstractUser` — never create a separate profile model. Add fields directly to `User`.
- `AUTH_USER_MODEL = 'api.User'` — always use `get_user_model()` in code that references the user model, not a direct import.
- Every new model needs a migration: run `python manage.py makemigrations` after any model change.
- Use `select_related()` for FK fields and `prefetch_related()` for M2M to avoid N+1 queries.

### Views

- Use `APIView` (DRF) for all API endpoints — not Django's raw `JsonResponse` views (the `is_even` view is a legacy exception).
- Role-based access: check `request.user.role` against `User.Role` choices — do not hardcode role strings.
- Return DRF `Response` objects, not raw `JsonResponse`, so content negotiation and status codes work correctly.

### URLs

- All API routes are prefixed `/api/` — register new routes in `api/urls.py`, not in `core/urls.py`.

---

## Backend — Testing Rules

- Use Django's `TestCase` (not plain `unittest.TestCase`) — it wraps each test in a transaction and rolls back automatically.
- Use `APIClient` from `rest_framework.test` for endpoint tests — not the raw Django test `Client`.
- **Never mock the database.** Tests run against a real SQLite DB (configured in CI via `DATABASE_URL=sqlite:///:memory:`). Mocking the ORM hides real query bugs.
- Create test users with `User.objects.create_user(...)` — never `User.objects.create(...)` (skips password hashing).
- For authenticated endpoint tests, log in via the login endpoint and let the cookie be set, or force-authenticate with `client.force_authenticate(user=user)`.
- Test file location: `backend/api/tests/` as a package, or `backend/api/tests.py`. One file per domain area (e.g. `test_auth.py`, `test_employees.py`, `test_departments.py`).
- Each test method should test one behaviour. Name tests as `test_<action>_<expected_outcome>` (e.g. `test_login_with_invalid_password_returns_401`).
- Always test both the happy path and the main failure cases (missing fields, wrong role, unauthenticated).
- Run tests: `uv run pytest` from `backend/` (uses in-memory SQLite when `DATABASE_URL=sqlite:///:memory:`, as in CI). pytest also collects plain `pytest`-style test functions, so `manage.py test` is not a substitute.

---

## Deployment

- **Local dev**: `docker-compose.yaml` — includes live-reload volume mounts.
- **Production**: `docker-compose.prod.yml` — no volume mounts; `npm install` and Python packages (`uv sync --no-dev`, installed to `/opt/venv`) come from the built image.
- After any model change, migrations must be run on the target environment — they are not automatic.
  - Locally: `docker exec miez-backend-1 python manage.py migrate`
  - EC2: `docker exec <backend_container_id> python manage.py migrate`
- The CI/CD pipeline (`deploy.yml`) runs migrations automatically on every deploy to `main`.
- Never commit `.env` — local `.env` and EC2 `.env` are managed separately.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Full Postgres URL (`postgresql://user:pass@host:port/db`) |
| `DJANGO_SECRET_KEY` | Django secret key — insecure default used locally only |
| `DEBUG` | `True` locally, `False` on EC2 |
| `POSTGRES_DB` | Database name (used by docker-compose) |
| `POSTGRES_USER` | Database user |
| `POSTGRES_PASSWORD` | Database password |
