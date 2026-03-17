#!/usr/bin/env bash
#
# setup-odi-testdb.sh — Stand up a local Oracle DB with a real ODI repository
#
# Pulls gvenzl/oracle-free Docker image, downloads the dev_odi_repo.dmp from
# oracle/big-data-lite, imports it, and verifies SNP_ tables are queryable.
#
# Usage:
#   ./scripts/setup-odi-testdb.sh          # full setup
#   ./scripts/setup-odi-testdb.sh teardown  # remove container + data
#
# Prerequisites: docker
#
# Image: gvenzl/oracle-free — pre-built Oracle 23c Free Docker images by
# Gerald Venzl, Oracle Developer Advocate. Official community images recommended
# by Oracle. https://hub.docker.com/r/gvenzl/oracle-free
#
set -euo pipefail

CONTAINER_NAME="crawl-odi-testdb"
ORACLE_PASSWORD="crawl123"
ODI_SCHEMA="odi_repo"
ODI_PASSWORD="odi123"
PDB="XEPDB1"
# Oracle 23c Free is too new for older ODI dumps — use XE 21c for compatibility
IMAGE="gvenzl/oracle-xe:21-slim-faststart"
DUMP_URL="https://github.com/oracle/big-data-lite/raw/master/movie/moviework/odi/dev_odi_repo.dmp"
DUMP_DIR="$(cd "$(dirname "$0")/.." && pwd)/tests/fixtures/odi/big-data-lite"
DUMP_FILE="dev_odi_repo.dmp"

# --- Teardown mode ---
if [[ "${1:-}" == "teardown" ]]; then
    echo "Tearing down ${CONTAINER_NAME}..."
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true
    echo "Done. Dump file kept at ${DUMP_DIR}/${DUMP_FILE}"
    exit 0
fi

# --- Preflight checks ---
if ! command -v docker &>/dev/null; then
    echo "Error: docker is required. Install it first."
    exit 1
fi

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Container '${CONTAINER_NAME}' already exists."
    echo "  To reconnect:  docker exec -it ${CONTAINER_NAME} sqlplus ${ODI_SCHEMA}/${ODI_PASSWORD}@${PDB}"
    echo "  To tear down:  $0 teardown"
    exit 0
fi

# --- Download the dump if not already present ---
mkdir -p "${DUMP_DIR}"
if [[ ! -f "${DUMP_DIR}/${DUMP_FILE}" ]]; then
    echo "Downloading ODI repository dump (24 MB)..."
    curl -L -o "${DUMP_DIR}/${DUMP_FILE}" "${DUMP_URL}"
else
    echo "Dump file already exists at ${DUMP_DIR}/${DUMP_FILE}"
fi

# --- Pull the image ---
echo "Pulling ${IMAGE}..."
docker pull "${IMAGE}"

# --- Start the container ---
echo "Starting Oracle XE 21c container..."
docker run -d \
    --name "${CONTAINER_NAME}" \
    --shm-size=1g \
    -p 1521:1521 \
    -e ORACLE_PASSWORD="${ORACLE_PASSWORD}" \
    -v "${DUMP_DIR}":/opt/oracle/dumpfiles \
    "${IMAGE}"

# --- Wait for DB ready ---
echo "Waiting for database to start..."
for i in $(seq 1 60); do
    if docker logs "${CONTAINER_NAME}" 2>&1 | grep -q "DATABASE IS READY TO USE"; then
        echo "Database is ready! (${i}s)"
        break
    fi
    if [[ $i -eq 60 ]]; then
        echo "Error: Database did not start within 60 seconds."
        echo "Check logs: docker logs ${CONTAINER_NAME}"
        exit 1
    fi
    sleep 1
done

# --- Create directory object and target schema ---
echo "Creating import directory and ODI schema..."
docker exec -i "${CONTAINER_NAME}" sqlplus -s "sys/${ORACLE_PASSWORD}@${PDB} as sysdba" <<SQL
CREATE OR REPLACE DIRECTORY dmpdir AS '/opt/oracle/dumpfiles';
CREATE USER ${ODI_SCHEMA} IDENTIFIED BY "${ODI_PASSWORD}"
    DEFAULT TABLESPACE USERS QUOTA UNLIMITED ON USERS;
GRANT CONNECT, RESOURCE, IMP_FULL_DATABASE TO ${ODI_SCHEMA};
EXIT;
SQL

# --- Import the dump ---
echo "Importing ODI repository dump (this may take a minute)..."
# Grant read on the dump directory to odi_repo user
docker exec -i "${CONTAINER_NAME}" sqlplus -s "sys/${ORACLE_PASSWORD}@${PDB} as sysdba" <<SQL
GRANT READ, WRITE ON DIRECTORY dmpdir TO ${ODI_SCHEMA};
EXIT;
SQL

# Import using the odi_repo user (avoid 'as sysdba' quoting issues with impdp)
# remap_schema handles the schema name change from the original dump
ORIG_SCHEMA="DEV_ODI_REPO"
echo "Remapping schema: ${ORIG_SCHEMA} -> ${ODI_SCHEMA}"
# Create a writable log directory inside the container
docker exec -i "${CONTAINER_NAME}" bash -c "mkdir -p /tmp/dplog && chmod 777 /tmp/dplog"
docker exec -i "${CONTAINER_NAME}" sqlplus -s "sys/${ORACLE_PASSWORD}@${PDB} as sysdba" <<SQL
CREATE OR REPLACE DIRECTORY logdir AS '/tmp/dplog';
GRANT READ, WRITE ON DIRECTORY logdir TO ${ODI_SCHEMA};
EXIT;
SQL

docker exec -i "${CONTAINER_NAME}" impdp "${ODI_SCHEMA}/${ODI_PASSWORD}@${PDB}" \
    directory=dmpdir \
    dumpfile="${DUMP_FILE}" \
    logfile=logdir:import.log \
    remap_schema="${ORIG_SCHEMA}:${ODI_SCHEMA}" \
    remap_tablespace=DEV_ODI_USER:USERS \
    table_exists_action=replace \
    2>&1 | tail -30

# --- Verify ---
echo ""
echo "=== Verifying SNP_ tables ==="
docker exec -i "${CONTAINER_NAME}" sqlplus -s "${ODI_SCHEMA}/${ODI_PASSWORD}@${PDB}" <<'SQL'
SET PAGESIZE 100
SET LINESIZE 120

PROMPT
PROMPT === SNP_ Tables Found ===
SELECT table_name, num_rows
FROM user_tables
WHERE table_name LIKE 'SNP_%'
ORDER BY table_name;

PROMPT
PROMPT === Key Table Counts ===
SELECT 'SNP_MAPPING (12c mappings)' AS object_type, COUNT(*) AS cnt FROM snp_mapping
UNION ALL
SELECT 'SNP_POP (11g interfaces)', COUNT(*) FROM snp_pop
UNION ALL
SELECT 'SNP_MAP_COMP (12c components)', COUNT(*) FROM snp_map_comp
UNION ALL
SELECT 'SNP_TABLE (datastores)', COUNT(*) FROM snp_table
UNION ALL
SELECT 'SNP_TRT (knowledge modules)', COUNT(*) FROM snp_trt
UNION ALL
SELECT 'SNP_SESSION (execution history)', COUNT(*) FROM snp_session
UNION ALL
SELECT 'SNP_PROJECT (projects)', COUNT(*) FROM snp_project
UNION ALL
SELECT 'SNP_FOLDER (folders)', COUNT(*) FROM snp_folder;

EXIT;
SQL

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Connect:   docker exec -it ${CONTAINER_NAME} sqlplus ${ODI_SCHEMA}/${ODI_PASSWORD}@${PDB}"
echo "Crawl:     crawl scan --source odi://localhost:1521/${PDB}"
echo "Teardown:  $0 teardown"
