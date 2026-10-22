# Quizcraft — Django REST Framework quiz app

A runnable quiz application with a responsive browser interface, token authentication, instructor permissions, server-side grading, and private attempt history. SQLite is included as the development database; no external services are needed.

## Run locally

Requires Python 3.12 or newer. Tested with Python 3.14.

**Windows quick start:** extract the ZIP, open the `quiz-app` folder, and double-click **start.bat**. The launcher creates a local virtual environment, installs dependencies, migrates the database, and adds the sample quiz. The first run needs internet access. Keep the command window open, then visit **http://127.0.0.1:8000/**.

You can also run `python start.py` from this folder. If port 8000 is occupied, use `python start.py --port 8001`, then visit `http://127.0.0.1:8001/`.

For manual setup:

```powershell
cd quiz-app
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py seed_demo
.venv\Scripts\python.exe manage.py runserver
```

Open **http://127.0.0.1:8000/** and create an account. The sample quizzes are ready to take, including **Python Practice: Core Concepts & Problem Solving**, a published quiz with 15 questions and four choices per question. On macOS/Linux, use `.venv/bin/python` instead of `.venv\Scripts\python.exe`.

### Enable quiz authoring

Register an account in the app, then run:

```powershell
.venv\Scripts\python.exe manage.py make_instructor YOUR_USERNAME
```

Log out and sign in again to update the navigation. Use **Create quiz** to add questions, select each correct answer, and save as a draft or publish. Find saved drafts using **My quizzes**. Published quizzes cannot be changed or deleted; create a new quiz for revisions.

For administrative user management:

```powershell
.venv\Scripts\python.exe manage.py createsuperuser
```

Open **http://127.0.0.1:8000/admin/**. Staff can manage any instructor's draft through the API. The admin quiz and attempt pages are read-only so authoring validation cannot be bypassed there. The seed command creates an inactive author with an unusable password, not a demo login.

## Authentication and authorization

| Action | Learner | Instructor | Staff |
|---|---|---|---|
| Browse and take published quizzes | Yes | Yes | Yes |
| View own results | Yes | Yes | Yes |
| Create quizzes | No | Yes | Yes |
| See/edit/delete drafts | No | Own only | All |
| Read answer keys before submission | No | Own only | All |
| Read another person's attempt through the API | No | No | No |

- Public registration always creates a learner. Roles, ownership, and grades cannot be assigned by the registering/submitting client.
- Passwords use Django's hashing and validation. Login errors do not distinguish unknown usernames from wrong passwords.
- API requests use `Authorization: Token <token>`. API endpoints do not use cookie authentication, so cookies cannot authorize an API request. Django admin uses its separate CSRF-protected session login.
- The browser stores its token **only in memory**. Refreshing or closing the page requires signing in again; no token is placed in local storage or a URL.
- DRF tokens do not automatically expire. Logout deletes the token and invalidates it for all clients sharing it. A later login issues a new token. Use HTTPS outside local development.
- Authentication endpoints share a limit of 20 requests/hour per client IP. General limits are 100 anonymous or 1,000 authenticated requests/hour. Development throttles use an in-process cache; configure a shared cache and infrastructure rate limits for multiple production workers.
- Practice quizzes allow retakes and reveal the correct answers after a valid submission. This app is designed for learning, not secure examinations.

## API

All URLs use trailing slashes. Everything except registration and login requires a token. The DRF browsable API is available at `/api/`; use an API client to supply the token header.

| Method | URL | Purpose |
|---|---|---|
| POST | `/api/auth/register/` | Register with username, email, password; returns token and user |
| POST | `/api/auth/login/` | Login with username/password; returns token and user |
| POST | `/api/auth/logout/` | Revoke current token |
| GET | `/api/auth/me/` | Current profile and role |
| GET, POST | `/api/quizzes/` | List visible quizzes / create a quiz |
| GET, PUT, PATCH, DELETE | `/api/quizzes/{id}/` | Retrieve or manage quiz |
| POST | `/api/quizzes/{id}/submit/` | Validate and grade an attempt |
| GET | `/api/attempts/` | Own paginated attempt history |
| GET | `/api/attempts/{id}/` | Own result and answer review |

List responses have `count`, `next`, `previous`, and `results`. Quiz filters: `?search=python`, `?category=Development`, `?mine=true`, `?page=2`.

### PowerShell API example

```powershell
$account = Invoke-RestMethod http://127.0.0.1:8000/api/auth/register/ -Method Post -ContentType 'application/json' -Body '{"username":"alex","email":"alex@example.com","password":"Use-a-unique-password-492!"}'
$headers = @{ Authorization = "Token $($account.token)" }
$quizzes = Invoke-RestMethod http://127.0.0.1:8000/api/quizzes/ -Headers $headers
$quizzes.results
```

To create a quiz as an instructor, POST:

```json
{
  "title": "HTTP basics",
  "description": "A quick warm-up.",
  "category": "Web development",
  "is_published": false,
  "questions": [
    {
      "text": "Which status means created?",
      "choices": [
        {"text": "201", "is_correct": true},
        {"text": "404", "is_correct": false}
      ]
    }
  ]
}
```

Each quiz requires 1–50 questions, each with 2–6 distinct choices and exactly one correct answer. Questions and choices are saved atomically. A PUT replaces the full question collection; a PATCH can omit it. Use a PATCH with `{"is_published": true}` to publish a completed draft.

To submit, use question and choice IDs returned by GET `/api/quizzes/{id}/`:

```json
{
  "answers": [
    {"question_id": 1, "choice_id": 2},
    {"question_id": 2, "choice_id": 5}
  ]
}
```

Every quiz question must appear exactly once. Choices from another question, missing answers, duplicate questions, and foreign question IDs are rejected without creating an attempt. The response includes score, total, percentage, and an answer-review snapshot.

## Tests

```powershell
.venv\Scripts\python.exe manage.py test
.venv\Scripts\python.exe manage.py check
```

Tests cover authentication, token revocation, role escalation, draft privacy, ownership, staff access, answer-key protection, server-side scoring, malformed submissions, private history, publication locking, and throttling.

Local verification: all 22 API tests passed, and Django's system check reported no issues. `requirements-lock.txt` records the exact versions used; install it instead of `requirements.txt` to reproduce this environment. The browser preview was blocked by the app's permission gate, so visual verification has not been completed.

## Structure

```text
config/                Django settings and URL routing
quizzes/models.py      Quiz → Question → Choice; Attempt snapshots
quizzes/serializers.py Validation and API representations
quizzes/permissions.py Role and ownership checks
quizzes/views.py       Auth, authoring, grading, private results
quizzes/tests.py       API integration tests
templates/index.html  Browser app shell
static/               Responsive CSS and vanilla JavaScript client
```

## Deployment configuration

This repository runs in local development mode by default. Set `DJANGO_DEBUG=false`, a strong `DJANGO_SECRET_KEY`, and comma-separated `DJANGO_ALLOWED_HOSTS` for deployment. Production mode requires HTTPS and enables secure cookies and HSTS. Configure your host's database, static serving (`manage.py collectstatic`), shared cache, backups, and WSGI server before deployment. SQLite is intended for local/small single-instance use; use PostgreSQL when concurrent authoring and submission require row-level locking. No email verification or password-reset email flow is included.

Implementation references: [DRF authentication](https://www.django-rest-framework.org/api-guide/authentication/), [DRF permissions](https://www.django-rest-framework.org/api-guide/permissions/).

## Resume bullet

Built a Django REST Framework quiz application with token authentication, instructor and learner authorization, validated nested quiz authoring, server-side scoring, and private attempt history; verified critical workflows with automated API tests.
