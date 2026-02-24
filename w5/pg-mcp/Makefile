# Rebuild fixture databases for pg-mcp
#
# Usage examples:
#   make rebuild-all
#   make rebuild-small
#   make rebuild-medium
#   make rebuild-large
#
# Override connection/database names if needed:
#   make rebuild-all PGHOST=127.0.0.1 PGPORT=5432 PGUSER=postgres
#   make rebuild-small BLOG_DB=my_blog_test

PGHOST ?= localhost
PGPORT ?= 5432
PGUSER ?= postgres
PGPASSWORD ?=

BLOG_DB ?= blog_small
ECOMMERCE_DB ?= ecommerce_medium
SAAS_DB ?= saas_crm_large

FIXTURE_DIR := fixtures
PSQL := psql -v ON_ERROR_STOP=1
CREATEDB := createdb
DROPDB := dropdb --if-exists

export PGHOST PGPORT PGUSER PGPASSWORD

.PHONY: help rebuild-all rebuild-small rebuild-medium rebuild-large drop-all drop-small drop-medium drop-large

help:
	@echo "Targets:"
	@echo "  rebuild-all      Drop/create and load all fixture databases"
	@echo "  rebuild-small    Rebuild $(BLOG_DB) from $(FIXTURE_DIR)/blog_small.sql"
	@echo "  rebuild-medium   Rebuild $(ECOMMERCE_DB) from $(FIXTURE_DIR)/ecommerce_medium.sql"
	@echo "  rebuild-large    Rebuild $(SAAS_DB) from $(FIXTURE_DIR)/saas_crm_large.sql"
	@echo "  drop-all         Drop all fixture databases"
	@echo ""
	@echo "Connection variables:"
	@echo "  PGHOST, PGPORT, PGUSER, PGPASSWORD"
	@echo "Database name overrides:"
	@echo "  BLOG_DB, ECOMMERCE_DB, SAAS_DB"

rebuild-all: rebuild-small rebuild-medium rebuild-large

rebuild-small:
	$(DROPDB) $(BLOG_DB)
	$(CREATEDB) $(BLOG_DB)
	$(PSQL) -d $(BLOG_DB) -f $(FIXTURE_DIR)/blog_small.sql
	@echo "Rebuilt database: $(BLOG_DB)"

rebuild-medium:
	$(DROPDB) $(ECOMMERCE_DB)
	$(CREATEDB) $(ECOMMERCE_DB)
	$(PSQL) -d $(ECOMMERCE_DB) -f $(FIXTURE_DIR)/ecommerce_medium.sql
	@echo "Rebuilt database: $(ECOMMERCE_DB)"

rebuild-large:
	$(DROPDB) $(SAAS_DB)
	$(CREATEDB) $(SAAS_DB)
	$(PSQL) -d $(SAAS_DB) -f $(FIXTURE_DIR)/saas_crm_large.sql
	@echo "Rebuilt database: $(SAAS_DB)"

drop-all: drop-small drop-medium drop-large

drop-small:
	$(DROPDB) $(BLOG_DB)
	@echo "Dropped database (if existed): $(BLOG_DB)"

drop-medium:
	$(DROPDB) $(ECOMMERCE_DB)
	@echo "Dropped database (if existed): $(ECOMMERCE_DB)"

drop-large:
	$(DROPDB) $(SAAS_DB)
	@echo "Dropped database (if existed): $(SAAS_DB)"
