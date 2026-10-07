# M.I.E.Z — AI Assistant Guidelines

## Stack

- **Backend**: Python 3.13, Django 5.2, Django REST Framework, PostgreSQL (via `dj-database-url`). Dependencies are managed with **uv** (`backend/pyproject.toml` + `backend/uv.lock`)
- **Frontend**: React + Vite, TypeScript (strict)
- **Auth**: Django sessions. Logging in sets an httpOnly `sessionid` cookie. Every POST/PUT/PATCH/DELETE must send the `csrftoken` cookie's value in an `X-CSRFToken` header. `GET /api/auth/me/` hands out the `csrftoken` cookie.
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
  services/      business rules (status transitions, decisions); used by views AND agent tools
  urls.py        all /api/ routes, grouped by domain
  agent/         the AI assistant (runner, tools, operations)
  management/commands/   CLI jobs (seed_db, run_workflows, run_hr_agent, …)
```

- New endpoint: put the view in the matching `views/<domain>.py`, its serializers in `serializers/<domain>.py`, and the route in `urls.py` under that domain's comment. Create a new domain module only for a genuinely new area.
- Views import serializers from their domain module (`from ..serializers.sales import OrderListSerializer`), and models from the package (`from ..models import Order`).
- A view module must not import from another view module. Shared logic goes into a helper module, not into a view file.
- **Business rules live in `api/services/<domain>.py`, never in views, serializers or agent tools.** Anything that changes the state of a business object (order status, ticket status, leave decisions, …) must call the service function. The UI and the AI assistant then always follow the same rules. Services raise `BusinessRuleError`, and views return it as HTTP 400 with `{'detail': str(exc)}`.

## Backend — Implementation Rules

### Use Django and DRF built-ins. Never reimplement what already exists.

| Need | Use this |
|------|----------|
| User model | Extend `AbstractUser` (already done in `api/models/user.py`) |
| Authentication | Django's `authenticate()` / `login()` / `logout()` (see `api/views/auth.py`); DRF `SessionAuthentication` via `core/authentication.py`, which only changes "not logged in" to 401. Never add tokens or custom cookie handling. |
| Password hashing | `user.set_password()` — never hash manually |
| Permission checks | `permission_classes = [IsAuthenticated, role_required(User.Role.CEO, User.Role.HR)]` (from `api/permissions.py`). Use per-method lists when methods differ: `role_required(get=[...], post=[...])`. Never write `if request.user.role ...: return 403` inside a view. |
| Object lookup with 404 | `get_object_or_404(Model, ...)` |
| Pagination | Use the classes in `api/pagination.py` (`StandardPagination`, `TenPerPagePagination`, `TwentyPerPagePagination`). Pass summary totals as keyword arguments to `get_paginated_response(data, total=...)`. Don't write new pagination classes. |
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
- Role-based access: declare it with `role_required(...)` in `permission_classes`, using `User.Role` choices. Don't hardcode role strings. Every 403 then returns the same message.
- Return DRF `Response` objects, not raw `JsonResponse`, so content negotiation and status codes work correctly.

### URLs

- All API routes are prefixed `/api/` — register new routes in `api/urls.py`, not in `core/urls.py`.

---

## Backend — Testing Rules

- **Tests are plain pytest functions with plain `assert`.** No `TestCase` classes, `setUp` or `self.assertX`.
- **Logged-in users come from fixtures** in `api/tests/conftest.py`: `ceo_client`, `hr_client`, `it_client`, `sales_client`, `inventory_client` (and the matching `*_user`), plus `api_client` for anonymous requests. Every test already has database access and an empty cache.
- **Test data is created inline with `baker.make(Model, field=...)`.** Only set the fields the test is about; model_bakery fills the rest. Use `_quantity=n` for several objects. Use `User.objects.create_user(...)` only when the test needs a real password (login).
- A fixture used by one file lives at the top of that file. It moves to `conftest.py` only once several files need it. Don't write helper modules or base classes.
- Same check, different inputs → one test with `@pytest.mark.parametrize`, not copy-pasted tests.
- **Never mock the database.** Tests run against a real SQLite DB (in CI via `DATABASE_URL=sqlite:///:memory:`). Mock only external services (the Anthropic client, background threads).
- Test layout mirrors the app: a test for `api/<folder>/<module>.py` goes in `api/tests/<folder>/test_<module>.py`. For example, `api/views/sales.py` → `api/tests/views/test_sales.py`, `api/agent/runner.py` → `api/tests/agent/test_runner.py`, `api/workflow_engine.py` → `api/tests/test_workflow_engine.py`. Management commands go in `api/tests/management/`, cross-cutting end-to-end flows in `api/tests/integration/`. Every test folder needs an `__init__.py`.
- Each test should test one behaviour. Name tests as `test_<action>_<expected_outcome>` (e.g. `test_login_with_invalid_password_returns_401`).
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
| `DJANGO_SECRET_KEY` | Django secret key — insecure default used locally only. Also signs sessions: changing it logs everyone out |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated address(es) the frontend is opened at, e.g. `http://203.0.113.10,https://miez.example.com`. Defaults to the Vite dev server. Without it, every login and change fails CSRF |
| `SECURE_COOKIES` | `True` once the site is served over HTTPS (session and CSRF cookies become HTTPS-only) |
| `DEBUG` | `True` locally, `False` on EC2 |
| `POSTGRES_DB` | Database name (used by docker-compose) |
| `POSTGRES_USER` | Database user |
| `POSTGRES_PASSWORD` | Database password |
