# Server Updates — Performance & This Release

Server context: Ubuntu, project at **/home/abc/inventory_project**, venv at
**/home/abc/inventory_project/venv**, PostgreSQL `inventory_db`, Gunicorn behind
Nginx on `/run/inventory.sock`, timezone Asia/Kolkata. Do **not** change these
paths or touch the production `.env` secrets.

---

## 0. Move the site to inventory.zacoinfotech.com (one time)

The app now defaults to **inventory.zacoinfotech.com**. Because the server's
`.env` overrides that default, three things on the server must change.

**a) DNS** (at the zacoinfotech.com DNS provider): add an `A` record
`inventory` → this server's public IP. Wait until it resolves:

```bash
dig +short inventory.zacoinfotech.com      # must print the server IP
```

**b) `.env`** (`/home/abc/inventory_project/.env`) — edit only these lines,
leave the secrets alone:

```env
SITE_DOMAIN=inventory.zacoinfotech.com
ALLOWED_HOSTS=inventory.zacoinfotech.com,inventory.zacocomputer.com,127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=https://inventory.zacoinfotech.com,https://inventory.zacocomputer.com
```

(Keeping the old name in both lines lets the old address keep working while
people switch; remove it later.)

**c) Nginx + HTTPS** — in `/etc/nginx/sites-available/inventory` change
`server_name` to `inventory.zacoinfotech.com`, then get a certificate:

```bash
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d inventory.zacoinfotech.com
```

Optional — send everyone on the old address to the new one (add as a
separate `server` block; keep the old certificate so HTTPS still works):

```nginx
server {
    listen 443 ssl;
    server_name inventory.zacocomputer.com;
    ssl_certificate     /etc/letsencrypt/live/inventory.zacocomputer.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/inventory.zacocomputer.com/privkey.pem;
    return 301 https://inventory.zacoinfotech.com$request_uri;
}
server {
    listen 80;
    server_name inventory.zacocomputer.com;
    return 301 https://inventory.zacoinfotech.com$request_uri;
}
```

Then `sudo systemctl restart inventory.service` and log in at
`https://inventory.zacoinfotech.com` (logins on the old address do not carry
over — everyone signs in once on the new one).

---

## 1. Deploy this release (required)

This release adds a DB field + **new indexes** (big list-view speedup) and a new
migration, so migrate and restart:

```bash
cd /home/abc/inventory_project
source venv/bin/activate

git pull
pip install -r requirements.txt
python manage.py migrate                 # adds indexes + attended_attachment
python manage.py collectstatic --noinput
python manage.py check

sudo systemctl restart inventory.service
# timer/socket unchanged — do NOT touch inventory.socket or the daily-report timer
```

> The new indexes are created with `CREATE INDEX` on `inventory_inventorytransaction`
> and `inventory_inventoryfreezerecord`. On a large table this can take a little
> time and briefly lock; run the migrate during low traffic. (If you want zero
> lock, build them `CONCURRENTLY` by hand first, then `migrate --fake` — optional.)

### What changed in the app for performance
- Added composite indexes for the "latest transaction per product" lookups that
  every list/report runs (`(product, -created_at)`, `(product, transaction_type,
  -created_at)`, `(transaction_type, stock_status)`) and `(product, -frozen_at)`
  on freeze records.
- Removed a per-row modal that was being duplicated **once per table row** in the
  Card and Memory lists (thousands of hidden modals → huge DOM). Lists now render
  a single shared modal.

---

## 2. PostgreSQL tuning (recommended for thousands of rows)

Edit `/etc/postgresql/*/main/postgresql.conf` (values for a small VPS with ~2–4 GB
RAM — scale up if the box is bigger):

```conf
shared_buffers = 512MB           # ~25% of RAM
effective_cache_size = 1536MB    # ~75% of RAM
work_mem = 16MB
maintenance_work_mem = 128MB
random_page_cost = 1.1           # SSD
effective_io_concurrency = 200   # SSD
```

Apply and refresh planner stats:

```bash
sudo systemctl restart postgresql
sudo -u postgres psql -d inventory_db -c "VACUUM ANALYZE;"
```

Keep stats fresh with a weekly cron (as the `postgres` user):

```cron
0 2 * * 0 psql -d inventory_db -c "VACUUM ANALYZE;" >/dev/null 2>&1
```

Sanity-check a hot query uses the new index (should say *Index Scan*, not *Seq Scan*):

```bash
sudo -u postgres psql -d inventory_db -c \
"EXPLAIN ANALYZE SELECT * FROM inventory_inventorytransaction WHERE product_id = 1 ORDER BY created_at DESC LIMIT 1;"
```

---

## 3. Gunicorn tuning

Edit `/etc/systemd/system/inventory.service` `ExecStart` (inspect first with
`cat`, keep the unix socket bind and User/Group=www-data):

```ini
ExecStart=/home/abc/inventory_project/venv/bin/gunicorn \
    --workers 5 \            # (2 × CPU cores) + 1
    --threads 2 \
    --timeout 60 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --bind unix:/run/inventory.sock \
    inventory_project.wsgi:application
```

`--max-requests` recycles workers periodically to cap memory growth from large
Excel exports/imports. Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart inventory.service
sudo journalctl -u inventory.service -n 50 --no-pager
```

---

## 4. Nginx (static + upload size)

Static is served by WhiteNoise, but let Nginx cache it and allow big Excel
uploads. In `/etc/nginx/sites-available/inventory` (inspect first):

```nginx
client_max_body_size 25M;

location /static/ {
    alias /home/abc/inventory_project/staticfiles/;
    access_log off;
    expires 30d;
    add_header Cache-Control "public";
}
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## 5. Media permissions (unchanged policy)

```bash
sudo chown -R abc:www-data /home/abc/inventory_project/media
sudo find /home/abc/inventory_project/media -type d -exec chmod 2775 {} \;
sudo find /home/abc/inventory_project/media -type f -exec chmod 664 {} \;
```

---

## 6. Verify

```bash
cd /home/abc/inventory_project && source venv/bin/activate
python manage.py check --deploy
systemctl is-active inventory.service postgresql nginx
systemctl list-timers inventory-daily-report.timer
```

Open `https://inventory.zacoinfotech.com`, load a large category list and confirm
it renders quickly; the "matching records" count and DataTables paging should be
responsive.

---

## 7. Note on very large lists (future work)

Current list pages render every in-stock row and paginate in the browser
(DataTables client-side). With the indexes + modal fix this is fine for a few
thousand rows. If a single category grows past ~10k live rows, switch that list to
**server-side pagination** (DataTables `serverSide: true` backed by a JSON
endpoint) so only one page of rows is queried and sent at a time. This is an
application change (not a server config) — flag it when you approach that scale.
