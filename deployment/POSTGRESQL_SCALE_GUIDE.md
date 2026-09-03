# Large Inventory Deployment Guide

This application now paginates every high-volume live list at 50 records per page. The browser must never render the full inventory. List and universal-search text matching should be backed by PostgreSQL trigram indexes.

## 1. Deploy the application update

```bash
cd /path/to/inventory_project
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart inventory-gunicorn
```

Use a maintenance window for the index build below. The index statements are concurrent, so normal reads and writes can continue, but the first build can take time with a large database.

## 2. Create search indexes

Run this as the PostgreSQL database owner. Do not wrap it in `BEGIN` or use `psql --single-transaction`, because `CREATE INDEX CONCURRENTLY` cannot run in a transaction.

```bash
psql -h 127.0.0.1 -U inventory_user -d inventory_db \
  -f deployment/postgresql_search_indexes.sql
```

Verify the result:

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public' AND indexname LIKE '%trgm%'
ORDER BY indexname;
```

## 3. PostgreSQL 14 tuning for this server

Ubuntu 22.04 normally ships PostgreSQL 14. Put the following in `/etc/postgresql/14/main/conf.d/inventory-performance.conf`; change `14/main` if your installed version or cluster differs.

```conf
max_connections = 120
shared_buffers = 48GB
effective_cache_size = 140GB
work_mem = 32MB
maintenance_work_mem = 4GB
effective_io_concurrency = 200
random_page_cost = 1.1
default_statistics_target = 200
max_worker_processes = 40
max_parallel_workers = 32
max_parallel_workers_per_gather = 8
min_wal_size = 4GB
max_wal_size = 16GB
checkpoint_completion_target = 0.9
log_min_duration_statement = 1000
```

Validate and restart:

```bash
sudo -u postgres psql -c "SELECT pg_reload_conf();"
sudo systemctl restart postgresql
sudo -u postgres psql -d inventory_db -c "VACUUM (ANALYZE);"
```

`work_mem` is per sort/hash operation, so do not increase it blindly. The suggested 32MB works safely with the Gunicorn settings below and 188GiB RAM.

## 4. Connection and application process settings

Use PgBouncer between Gunicorn and PostgreSQL for a high number of web requests. Start with transaction pooling and a pool of 80 database connections.

Gunicorn should use a moderate worker count, not all 88 CPU threads:

```ini
# /etc/systemd/system/inventory-gunicorn.service
ExecStart=/path/to/.venv/bin/gunicorn inventory_project.wsgi:application \
  --workers 24 --threads 2 --worker-class gthread \
  --max-requests 4000 --max-requests-jitter 400 \
  --timeout 90 --graceful-timeout 30 \
  --bind unix:/run/inventory/gunicorn.sock
```

Run Nginx in front of Gunicorn. Keep `proxy_read_timeout 90s`; longer timeouts only hide slow database queries, while the indexes and bounded queries above fix the cause.

## 5. Ongoing maintenance and monitoring

```bash
# Largest tables and indexes
sudo -u postgres psql -d inventory_db -c "SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) AS total_size FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 20;"

# Slowest statements, after enabling pg_stat_statements
sudo -u postgres psql -d inventory_db -c "SELECT calls, mean_exec_time, rows, query FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 20;"
```

Confirm autovacuum stays enabled. After a very large import, run `VACUUM (ANALYZE)` for the affected tables during a low-traffic period. Keep at least 20GB free disk space for PostgreSQL temporary files, backups, and index maintenance.

## 6. Functional behavior after this update

- Live category lists, Controller, Server, Networking Spare, Sold, and Faulty lists use 50-row database pages.
- List search is server-side. DataTables no longer pretends to search records that are not currently in the browser.
- Universal search requires three characters, cancels obsolete keystroke requests, returns a capped result set, and batches membership lookup.
- Server and Controller component aggregation runs only when a component search is requested.
