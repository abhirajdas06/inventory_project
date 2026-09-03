-- Run as the PostgreSQL database owner, outside an explicit transaction.
-- These indexes accelerate contains searches used by list pages and universal search.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX CONCURRENTLY IF NOT EXISTS core_product_name_trgm_idx ON core_product USING gin (name gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS core_product_serial_trgm_idx ON core_product USING gin (serial_no gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS core_product_part_trgm_idx ON core_product USING gin (part_no gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS categories_spare_part_trgm_idx ON categories_spare USING gin (part_no gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS categories_spare_location_trgm_idx ON categories_spare USING gin (location gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS categories_card_part_trgm_idx ON categories_card USING gin (part_no gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS categories_card_location_trgm_idx ON categories_card USING gin (location gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS categories_cpu_part_trgm_idx ON categories_cpu USING gin (part_no gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS categories_cpu_location_trgm_idx ON categories_cpu USING gin (location gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS categories_controller_part_trgm_idx ON categories_controller USING gin (part_no gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS categories_controller_location_trgm_idx ON categories_controller USING gin (location gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS categories_memory_location_trgm_idx ON categories_memory USING gin (location gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS categories_sfp_part_trgm_idx ON categories_sfp USING gin (part_no gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS categories_sfp_location_trgm_idx ON categories_sfp USING gin (location gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS categories_railkit_part_trgm_idx ON categories_railkit USING gin (part_no gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS categories_railkit_location_trgm_idx ON categories_railkit USING gin (location gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS categories_harddisk_part_trgm_idx ON categories_harddisk USING gin (part_no gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS categories_harddisk_location_trgm_idx ON categories_harddisk USING gin (location gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS categories_networkingspare_part_trgm_idx ON categories_networkingspare USING gin (part_no gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS categories_networkingspare_location_trgm_idx ON categories_networkingspare USING gin (location gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS servers_server_service_tag_trgm_idx ON servers_server USING gin (service_tag gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS servers_server_machine_no_trgm_idx ON servers_server USING gin (machine_no gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS servers_server_part_trgm_idx ON servers_server USING gin (part_no gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS servers_server_location_trgm_idx ON servers_server USING gin (location gin_trgm_ops);

ANALYZE core_product;
ANALYZE inventory_inventorytransaction;
ANALYZE categories_spare;
ANALYZE categories_card;
ANALYZE categories_cpu;
ANALYZE categories_controller;
ANALYZE categories_memory;
ANALYZE categories_sfp;
ANALYZE categories_railkit;
ANALYZE categories_harddisk;
ANALYZE categories_networkingspare;
ANALYZE servers_server;
