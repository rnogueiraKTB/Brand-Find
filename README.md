# Brand Find

A Django application to search brands with live results and view brand details.

## Features

- Public live brand search (HTMX).
- Public brand details view with:
  - Brand
  - Inquire to
  - Notes
  - Last changed on
  - Info received from
- Admin back office for registered staff users to create/update/delete records.
- Docker-ready for VPS deployment (Hostinger compatible).

## Tech Stack

- Django
- HTMX
- PostgreSQL (production via Docker)
- Gunicorn
- WhiteNoise

## Local Development (without Docker)

1. Create a virtual environment and activate it.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run migrations:

```bash
python manage.py migrate
```

4. Create a superuser:

```bash
python manage.py createsuperuser
```

5. Start the server:

```bash
python manage.py runserver
```

## Docker Deployment (Hostinger VPS)

1. Copy `.env.example` to `.env` and set secure values.
2. Build and start containers:

```bash
docker compose up --build -d
```

3. Create a superuser:

```bash
docker compose exec web python manage.py createsuperuser
```

4. Open:
   - App: `http://YOUR_SERVER_IP:8000/`
   - Admin: `http://YOUR_SERVER_IP:8000/admin/`

## Updating in Production

After pulling code changes:

```bash
docker compose up --build -d
```

Migrations and static collection run automatically at container startup.

## Health Check

- `GET /healthz` returns `ok` when the app is running.
