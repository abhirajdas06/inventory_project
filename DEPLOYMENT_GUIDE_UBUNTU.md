# Inventory Project — Deployment Guide (Ubuntu 22.04)

Target server: **Ubuntu 22.04**, **Python 3.10.12** (the default `python3` on 22.04),
PostgreSQL, Gunicorn behind Nginx, static files served by **WhiteNoise**.

> **Django version note.** Django 6.x requires Python 3.12+. On Python 3.10.12 this
> project runs on the **Django 5.2 LTS** series (pinned in `requirements.txt`). If you
> would rather run Django 6.x, install Python 3.12 first (e.g. via the `deadsnakes`
> PPA) and create the virtualenv with `python3.12`.

## 1. Server prerequisites

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev python3-pip build-essential \
    libpq-dev nginx curl git
# Make cron/systemd timers fire at local midnight:
sudo timedatectl set-timezone Asia/Kolkata
```

## 2. Get the code and create a virtual environment

```bash
cd /home/ubuntu
git clone <your-repo-url> inventory_project
cd inventory_project
python3 -m venv venv          # Python 3.10.12
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 3. PostgreSQL setup

```bash
sudo apt install -y postgresql postgresql-contrib
sudo -u postgres psql
```

```sql
CREATE DATABASE inventory_db;
CREATE USER inventory_user WITH PASSWORD 'strong-password-here';
ALTER ROLE inventory_user SET client_encoding TO 'utf8';
ALTER ROLE inventory_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE inventory_user SET timezone TO 'Asia/Kolkata';
GRANT ALL PRIVILEGES ON DATABASE inventory_db TO inventory_user;
\q
```

## 4. Environment variables

Create `.env` in the project root (see `.env.example`):

```env
SECRET_KEY=generate-a-strong-random-secret
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

DB_NAME=inventory_db
DB_USER=inventory_user
DB_PASSWORD=strong-password-here
DB_HOST=127.0.0.1
DB_PORT=5432

# Email (SMTP) for the automated midnight report
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-sender@gmail.com
EMAIL_HOST_PASSWORD=your-app-password        # Gmail: use an App Password
DEFAULT_FROM_EMAIL=InvenTrack Reports <your-sender@gmail.com>
DAILY_REPORT_RECIPIENTS=abhiraj@zacocomputer.com
```

> Gmail requires an **App Password** (Google Account → Security → 2‑Step
> Verification → App passwords), not your normal password. If `EMAIL_HOST_USER`
> is left blank the app uses the console backend (prints emails, sends nothing).

## 5. Django setup

```bash
source venv/bin/activate
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput      # WhiteNoise serves from staticfiles/
```

## 6. Gunicorn systemd service

`/etc/systemd/system/inventory.socket`:

```ini
[Unit]
Description=inventory gunicorn socket

[Socket]
ListenStream=/run/inventory.sock

[Install]
WantedBy=sockets.target
```

`/etc/systemd/system/inventory.service`:

```ini
[Unit]
Description=Inventory Project Gunicorn
Requires=inventory.socket
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/home/ubuntu/inventory_project
EnvironmentFile=/home/ubuntu/inventory_project/.env
ExecStart=/home/ubuntu/inventory_project/venv/bin/gunicorn \
    --access-logfile - \
    --workers 3 \
    --bind unix:/run/inventory.sock \
    inventory_project.wsgi:application

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now inventory.socket
sudo systemctl enable --now inventory.service
```

## 7. Nginx configuration

WhiteNoise already serves `/static/`, so Nginx only needs to proxy the app and
serve uploaded media. `/etc/nginx/sites-available/inventory`:

```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    client_max_body_size 25M;   # allow Excel uploads

    location /media/ {
        alias /home/ubuntu/inventory_project/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/inventory.sock;
    }
}
```

> Optional: for slightly faster static delivery you can let Nginx serve the
> collected files directly by adding
> `location /static/ { alias /home/ubuntu/inventory_project/staticfiles/; }`.
> It is not required — WhiteNoise handles static either way.

```bash
sudo ln -s /etc/nginx/sites-available/inventory /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 8. HTTPS

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

## 9. Midnight Excel export + email

The management command exports two workbooks (live + stocked-out, one sheet per
category plus a grouped Servers sheet) and **emails them** to
`DAILY_REPORT_RECIPIENTS` when run with `--email`:

```bash
# Test it once (writes files under media/exports/<date>/ AND emails them):
source venv/bin/activate
python manage.py export_daily_inventory --email \
    --output-dir /home/ubuntu/inventory_project/media
```

### Preferred: systemd timer (fires at local midnight)

`/etc/systemd/system/inventory-daily-report.service`:

```ini
[Unit]
Description=Daily inventory Excel export + email

[Service]
Type=oneshot
User=www-data
Group=www-data
WorkingDirectory=/home/ubuntu/inventory_project
EnvironmentFile=/home/ubuntu/inventory_project/.env
ExecStart=/home/ubuntu/inventory_project/venv/bin/python manage.py \
    export_daily_inventory --email --output-dir /home/ubuntu/inventory_project/media
```

`/etc/systemd/system/inventory-daily-report.timer`:

```ini
[Unit]
Description=Run the daily inventory report at midnight

[Timer]
OnCalendar=*-*-* 00:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now inventory-daily-report.timer
systemctl list-timers inventory-daily-report.timer   # verify next run
sudo systemctl start inventory-daily-report.service   # run once now to test
```

### Alternative: cron

```bash
crontab -e
```

```cron
0 0 * * * cd /home/ubuntu/inventory_project && /home/ubuntu/inventory_project/venv/bin/python manage.py export_daily_inventory --email --output-dir /home/ubuntu/inventory_project/media >> /home/ubuntu/inventory_project/export.log 2>&1
```

Files are also written to
`/home/ubuntu/inventory_project/media/exports/YYYY-MM-DD/` as a backup.

## 10. Useful commands

```bash
sudo systemctl status inventory.service
sudo systemctl restart inventory.service
sudo journalctl -u inventory.service -f
sudo journalctl -u inventory-daily-report.service -n 50
```

## 11. Final checks

```bash
python manage.py check --deploy
python manage.py test
```

## 12. Updating the app

```bash
cd /home/ubuntu/inventory_project
git pull
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart inventory.service
```
