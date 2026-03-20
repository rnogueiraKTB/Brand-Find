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
- Logo in admin can be set via URL or uploaded image (only one source at a time).
- Admin CSV upload for bulk brand import.
- Docker-ready for VPS deployment (Hostinger compatible).

## Admin CSV Upload

In `/admin/brands/brandentry/`, use the `Upload CSV` button.

Expected columns:

`brand; inquire; last updated`

Optional column:

`notes`, `info from`, `logo` (URL)

If the `logo` header is missing, the importer reads logo URL from column `F` (6th column).

- Accepted separators: `;` or `,`
- Accepted dates for `last updated`: `YYYY-MM-DD`, `DD/MM/YYYY`, `DD-MM-YYYY`, `YYYY/MM/DD`

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

3. If your `.env` has a Docker database URL (`...@db:5432`), force SQLite for this shell session:

`cmd`:

```bat
set USE_SQLITE=True
```

`PowerShell`:

```powershell
$env:USE_SQLITE="True"
```

4. Run migrations:

```bash
python manage.py migrate
```

5. Create a superuser:

```bash
python manage.py createsuperuser
```

6. Start the server (default local address: `127.0.0.1:8002`):

```bash
python manage.py runserver
```

## Docker Deployment (Hostinger VPS)

1. Copy `.env.example` to `.env` and set secure values.
   Make sure `ALLOWED_HOSTS` includes every hostname or IP you will use in the browser, and `CSRF_TRUSTED_ORIGINS` includes every full origin used for form posts (for example `https://brands.ktb-apps.cloud` and/or `http://187.124.171.11:8002`).
2. Build and start containers:

```bash
docker compose up --build -d
```

If you change `.env` later, do not use only `docker compose restart`.
Recreate the container so Docker reloads the environment:

```bash
docker compose up -d --build --force-recreate web
```

3. Create a superuser:

```bash
docker compose exec web python manage.py createsuperuser
```

4. Open:
   - App: `http://YOUR_SERVER_IP:8002/`
   - Admin: `http://YOUR_SERVER_IP:8002/admin/`
   - If you are using the direct server IP over plain HTTP, keep `SECURE_SSL_REDIRECT=False`, `SESSION_COOKIE_SECURE=False`, and `CSRF_COOKIE_SECURE=False`.
5. Follow logs (optional):

```bash
docker compose logs -f web
```

Uploaded images are persisted in a Docker volume (`media_data`) so they are not lost when recreating containers.

## HTTPS (Nginx + Let's Encrypt)

These steps assume Ubuntu and the subdomain `brands.ktb-apps.cloud`.

1. Create a DNS `A` record for `brands.ktb-apps.cloud` pointing to your VPS IP.
2. Install Nginx + Certbot:

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

3. Create the ACME webroot:

```bash
sudo mkdir -p /var/www/letsencrypt
```

4. Enable the HTTP config (temporary):

```bash
sudo cp deploy/nginx/brands.ktb-apps.cloud.http.conf /etc/nginx/sites-available/brands.ktb-apps.cloud
sudo ln -sf /etc/nginx/sites-available/brands.ktb-apps.cloud /etc/nginx/sites-enabled/brands.ktb-apps.cloud
sudo nginx -t
sudo systemctl reload nginx
```

5. Issue the certificate:

```bash
sudo certbot certonly --webroot -w /var/www/letsencrypt -d brands.ktb-apps.cloud
```

6. Switch to the HTTPS config:

```bash
sudo cp deploy/nginx/brands.ktb-apps.cloud.conf /etc/nginx/sites-available/brands.ktb-apps.cloud
sudo nginx -t
sudo systemctl reload nginx
```

7. Make sure your app is reachable on `127.0.0.1:8002` (Docker maps `8002:8000`).
   Once HTTPS is enabled behind Nginx, set `SECURE_SSL_REDIRECT=True`, `SESSION_COOKIE_SECURE=True`, and `CSRF_COOKIE_SECURE=True`.

If your domain or port is different, update the files in `deploy/nginx/` before copying.

## Updating in Production

After pulling code changes:

```bash
docker compose up --build -d
```

If the change was only in `.env`, still recreate the `web` container so the new variables are applied:

```bash
docker compose up -d --build --force-recreate web
```

Migrations and static collection run automatically at container startup.

## Docker Troubleshooting

If you see `password authentication failed for user` in `web` logs, your existing PostgreSQL volume was initialized with different credentials.

To reset local Docker database state:

```bash
docker compose down -v
docker compose up --build -d
```

Warning: `down -v` deletes PostgreSQL data from Docker volumes.

## Health Check

- `GET /healthz` returns `ok` when the app is running.
