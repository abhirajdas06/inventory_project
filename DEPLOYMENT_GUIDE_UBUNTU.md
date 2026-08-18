# Inventory Project Deployment Guide

This guide follows the same Ubuntu + PostgreSQL pattern as your current setup script, but in a cleaner deployment format.

## 1. Server prerequisites

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev build-essential libpq-dev nginx curl git
```

## 2. Get the code and create a virtual environment

```bash
git clone <your-repo-url> inventory_project
cd inventory_project
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 3. PostgreSQL setup

```bash
sudo apt install -y postgresql postgresql-contrib
sudo -u postgres psql
```

Inside `psql`:

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

Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key
DEBUG=False
DB_NAME=inventory_db
DB_USER=inventory_user
DB_PASSWORD=strong-password-here
DB_HOST=127.0.0.1
DB_PORT=5432
```

## 5. Django setup

```bash
source venv/bin/activate
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

## 6. Gunicorn systemd service

Create `/etc/systemd/system/inventory.service`:

```ini
[Unit]
Description=Inventory Project Gunicorn
Requires=inventory.socket
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/home/ubuntu/inventory_project
ExecStart=/home/ubuntu/inventory_project/venv/bin/gunicorn \
    --access-logfile - \
    --workers 3 \
    --bind unix:/run/inventory.sock \
    inventory_project.wsgi:application

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/inventory.socket`:

```ini
[Unit]
Description=inventory gunicorn socket

[Socket]
ListenStream=/run/inventory.sock

[Install]
WantedBy=sockets.target
```

Then enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl start inventory.socket
sudo systemctl enable inventory.socket
sudo systemctl start inventory.service
sudo systemctl enable inventory.service
```

## 7. Nginx configuration

Create `/etc/nginx/sites-available/inventory`:

```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    location /static/ {
        alias /home/ubuntu/inventory_project/static/;
    }

    location /media/ {
        alias /home/ubuntu/inventory_project/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/inventory.sock;
    }
}
```

Enable it:

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

## 9. Daily Excel export at midnight

The project includes a management command that exports:

- live inventory workbook
- stocked-out inventory workbook

Use cron to run it every day at 12:00 AM:

```bash
crontab -e
```

Add:

```cron
0 0 * * * /home/ubuntu/inventory_project/venv/bin/python /home/ubuntu/inventory_project/manage.py export_daily_inventory --output-dir /home/ubuntu/inventory_project/media >> /home/ubuntu/inventory_project/export.log 2>&1
```

The files will be written under:

```text
/home/ubuntu/inventory_project/media/exports/YYYY-MM-DD/
```

## 10. Useful service commands

```bash
sudo systemctl status inventory.service
sudo systemctl restart inventory.service
sudo journalctl -u inventory.service -f
sudo journalctl -u nginx -f
```

## 11. Final checks

```bash
python manage.py check
python manage.py test
```

