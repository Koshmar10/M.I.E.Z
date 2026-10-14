# M.I.E.Z

**M.I.E.Z** is an all-in-one business management platform for small and medium companies. It brings **HR, Sales, Inventory, and IT** operations under a single roof — with role-based dashboards, no-code workflow automation, structured reporting, and a built-in **AI assistant** that understands each user's role and the live state of the business.

Every screen and every API endpoint is **role-aware**: users only see and act on the data their role allows.

---

## Table of contents

- [Modules & capabilities](#modules--capabilities)
  - [HR Management](#hr-management)
  - [Sales & Orders](#sales--orders)
  - [Inventory](#inventory)
  - [IT Support](#it-support)
  - [Workflow Automation](#workflow-automation)
  - [Reports](#reports)
  - [Notifications](#notifications)
  - [Account & Settings](#account--settings)
- [The MIEZ Assistant](#the-miez-assistant)
- [Roles](#roles)
- [Tech at a glance](#tech-at-a-glance)

---

## Modules & capabilities

### HR Management
End-to-end workforce management for HR and the CEO.

- **Employees** — searchable, filterable, paginated directory (by name, department, active status). Create employees, view and edit profiles, and see headcount/active/full-time **stats** broken down by department.
- **Departments** — list departments; the CEO can create and remove them.
- **Attendance** — a weekly grid of every employee's status (present / remote / leave / absent) for any chosen week.
- **Leave requests** — create requests on behalf of employees, filter by status, and **approve or reject** them; approvals are stamped with who actioned them.
- **Contracts** — list and inspect employment contracts with an automatically computed status (**Active / Expiring / Expired**) based on the end date.
- **Payroll** — per-month payroll summary (gross, bonus, deductions, net) with paid/pending counts and optional bonus/deduction what-if overrides.
- **HR dashboard** — KPIs for total/active/new-hire headcount, pending leave, retention, and the latest HR digest.
- **Upcoming events** — a forward-looking feed of contract expiries, new-hire onboardings, and payroll-processing dates, with warning flags for items due within 7 days.
- **CEO HR summary** — cross-department headcount, utilisation, and a six-week attendance-rate trend.
- **AI HR digest** — generate a weekly digest of workforce insights (attendance anomalies, leave patterns, payroll anomalies, expiring contracts); critical findings notify HR managers automatically.

### Sales & Orders
Revenue operations for Sales reps and the CEO.

- **Orders** — create and track orders across channels, search/filter by status and channel, and move orders through a guarded lifecycle (**Processing → Shipped → Delivered**, or **Cancelled**) with invalid transitions blocked.
- **Customers** — customer list ranked by lifetime value and order count, plus per-customer detail.
- **Invoices** — list with paid / pending / overdue totals, view detail, and mark invoices as paid. An invoice is **auto-created when a new order is placed**.
- **Product catalogue** — browse sellable products with search and category filters.
- **Dashboards & analytics** — live KPIs (orders & revenue today vs. yesterday, pending orders, weekly returns), daily order counts, top products, channel split, and a year-over-year revenue trend.

### Inventory
Stock control for the Inventory Manager and the CEO.

- **Products & stock** — search by name/SKU, filter by category and stock status (**OK / Low / Out**), with per-product shortfall against the minimum.
- **Stock movements** — record **inbound** deliveries, **outbound** shipments, **adjustments**, and **write-offs**; browse the full movement history filtered by type, product, and date range.
- **Suppliers** — maintain supplier records and contact details.
- **Dashboard** — total products, low-stock and out-of-stock counts, and deliveries expected today.
- **Stock flow** — a Sankey-style visualisation of how stock moves from suppliers through the warehouse to sales, adjustments, and returns over a chosen window.

### IT Support
A lightweight internal helpdesk for IT technicians and the CEO.

- **Tickets** — **any user** can raise a ticket; IT and the CEO triage, prioritise, assign, and move tickets from open to resolved. Filter by status, category, assignee, or "assigned to me".
- **Assets** — full IT asset register (create, view, update, delete) with assignment to employees.
- **Dashboards & analytics** — open / in-progress / resolved counts, critical-open tickets, SLA attainment, a six-week opened-vs-closed trend, and per-technician resolution stats.
- **System status** — at-a-glance health and uptime of monitored systems.

### Workflow Automation
Build business automations without writing code. Each workflow pairs a **trigger** with one or more **actions**, can be toggled active/inactive, and logs every run for full auditability (the CEO can review the execution log).

**Triggers**
- Stock Below Minimum
- New Order Received
- Order Exceeds Threshold (configurable RON amount)
- New IT Ticket
- Contract Expires (configurable days ahead)
- Daily At Time / Weekly At Time (scheduled)

**Actions**
- **Email CEO** — sends a real email to all CEOs (and a demo recipient) via the configured SMTP backend, plus an in-app notification
- **Email Supplier** — emails the relevant supplier's contact address
- **Send Confirmation Email** — emails a specific user/recipient
- Notify Manager · Post to Channel · Assign to Team Lead · Generate Report · Update Dashboard · Log to Audit Trail

> Email actions send through SMTP when configured (`SMTP_HOST`, etc.); when SMTP isn't set up they degrade gracefully and record the intent in the run log instead of failing.

### Reports
Generate structured reports on demand across **Sales, Finance, Inventory, HR, and IT**. Reports are generated by the AI agent from real app data, then stored as files you can **view or download** at any time. Access is **scoped by category to your role** — e.g. only HR and the CEO can open HR reports.

### Notifications
A per-user notification centre (INFO / WARNING / ERROR) surfaced in the top bar, with unread counts, mark-one-read, and mark-all-read. Workflows, the HR digest, and other system events push notifications here.

### Account & Settings
A themed account page showing your profile, role, and department, with personal-information and password-management forms.

---

## The MIEZ Assistant

Every user gets a conversational AI assistant embedded in the app. It is **aware of who is asking** (name, role, department, current page) and is **strictly scoped to that user's permissions** — it can only call the tools their role allows, and each tool re-checks the role server-side.

**How it works**
- **Role-scoped tools** — the assistant is given only the tools the current role may use; it cannot read or change anything the user couldn't access in the UI.
- **Multilingual** — replies in the same language you write in (**Romanian or English**).
- **Conversational sessions** — chats are saved as sessions with full history, so context carries across messages.
- **Rate limited** — up to 20 messages per user per minute.
- **Action-oriented** — beyond answering questions it can take actions (raise a ticket, file a leave request, queue a report) within your permissions.

### What the assistant can do

| Capability | What it does | Available to |
|---|---|---|
| **Dashboard summary** | Pull live KPIs for a module (sales / hr / it / inventory) | All roles (per their own module) |
| **Create ticket** | Raise an IT support ticket | All roles |
| **Query orders** | Look up orders by status, channel, customer | CEO, Sales |
| **Query inventory** | Find products by stock status, category, below-minimum | CEO, Inventory |
| **Query tickets** | Search tickets by status, priority, assignee | CEO, IT |
| **Query employees** | Look up staff by department, role, active status | CEO, HR |
| **Query contracts** | Find contracts expiring within N days | CEO, HR |
| **Query leave requests** | List leave by week, status, or department | CEO, HR |
| **Create leave request** | File a leave request for an employee | HR |
| **Query attendance** | Attendance summary by department for a week | CEO, HR |
| **Query payroll** | Monthly payroll totals (gross / net / unpaid) | CEO, HR |
| **Attendance trend** | Multi-week attendance with low-attendance & repeated-absence flags | CEO, HR |
| **Leave patterns** | Surface leave-timing observations (e.g. Mon/Fri clusters) | CEO, HR |
| **Headcount vs. workload** | Compare active headcount to workload per department | CEO, HR |
| **Expiring contracts** | Contracts ending soon, flagged with open tickets / pending leave | CEO, HR |
| **Payroll anomalies** | Detect bonus spikes, zero deductions, missing entries | CEO, HR |
| **Generate report** | Queue a Sales/Finance/Inventory/HR/IT report from live data | CEO & department managers |

> The **CEO** can use every capability above. Other roles see only the rows their permissions grant.

### Automated HR Insights Agent
Separate from the chat assistant, a scheduled **HR Insights Agent** runs weekly (and can be triggered manually by the CEO/HR). It gathers attendance, leave, payroll, and contract signals, writes them into an HR digest report, and notifies HR managers of any critical findings.

---

## Roles

M.I.E.Z is built around five roles, each with a tailored view of the platform and a correspondingly scoped assistant:

| Role | Focus | Assistant can help with |
|---|---|---|
| **CEO** | Cross-department KPIs, HR summary, revenue overview, everything | All modules |
| **HR Manager** | Workforce, attendance, leave, payroll, contracts | Employees, leave, attendance, payroll, contracts, HR insights, reports |
| **Sales Rep** | Orders, customers, invoices, sales performance | Sales dashboard, orders |
| **Inventory Manager** | Products, stock, suppliers, movements | Inventory dashboard, stock queries |
| **IT Technician** | Support tickets, system status | IT dashboard, ticket queries |

---

## Tech at a glance

- **Backend** — Python 3.13, Django 5.2 + Django REST Framework, Django session auth, PostgreSQL
- **Frontend** — React + Vite + TypeScript
- **AI** — Anthropic Claude (the assistant and report/HR agents)
- **Automation** — signal- and schedule-driven workflow engine with SMTP email
- **Infrastructure** — Docker Compose, AWS EC2, GitHub Actions CI/CD

---

## Development

**Prerequisites:** Docker, [uv](https://docs.astral.sh/uv/) (Python package manager), Node.js 20+.

```bash
# Run the app (Postgres, backend on :8000, frontend on :5173)
docker compose up --build
docker exec miez-backend-1 python manage.py migrate
docker exec miez-backend-1 python manage.py seed_db   # demo data; every user's password is "password123"

# Local tooling — also installs the git hooks
(cd backend && uv sync)         # creates backend/.venv with Python 3.13
(cd frontend && npm install)    # installs lefthook hooks into .git/hooks

# Run every check the pre-push hook and CI run
npm --prefix frontend run check
```

Git hooks (lefthook) format staged files on commit and run lint, type checks, the migration check and tests on push. CI runs the same checks on every pull request. See `CLAUDE.md` for the rules.
