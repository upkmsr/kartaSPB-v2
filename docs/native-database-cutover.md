# Native PostgreSQL production cutover

This runbook prepares the authorised replacement of the unstable cross-architecture
database runtime. It is not permission to execute the cutover. The existing container,
image, and `kartaspb-v2_postgres-data` volume remain rollback material. Never attach
that PGDATA volume to the new image; the transfer is logical dump and restore only.

## Production status

The authorised production cutover completed successfully on 2026-10-02. Production now
runs native arm64 PostgreSQL 17.5 and PostGIS 3.6.4 in project
`kartaspb-v2-native-r2`, with Alembic at `20261001_0010`. Restore, application/API, data
invariant, storage, and stability acceptance passed with zero ENOSPC, crash recovery,
restart, or OOM event. The former cross-architecture container is stopped and its
`kartaspb-v2_postgres-data` volume remains protected rollback material; cleanup still
requires separate explicit authorisation. The later single Street refresh is recorded
separately in [street-entities.md](street-entities.md).

## Preconditions

- repository `main`, CI, native rehearsal, and clean disposable Compose acceptance pass;
- the current production schema is `20261001_0010` and Street tables are empty;
- no OSM, canonical, category, facility, or Street refresh runs during the cutover;
- enough disk exists for one fresh dump and the new native volume;
- explicit production cutover authorisation has been recorded.

## Mandatory Docker VM capacity preflight

Host free space is not Docker VM free space. Measure the filesystem that contains
Docker data before quiescing production. For the current Colima runtime:

```bash
colima ssh -- df -B1 /mnt/lima-colima
colima ssh -- df -i /mnt/lima-colima
docker system df -v
```

Inventory volumes, writable container layers, images, and their attachments before any
cleanup. The old production volume, native cutover image, and host backup are protected.
Use only targeted cleanup of artifacts whose ownership and reproducibility have been
proved; never use a global volume prune.

Derive the gate from a recent full native restore of the current backup:

```text
required available bytes before restore =
  measured restored PGDATA
  + restore/WAL/temp allowance
  + required post-restore operational headroom
```

The old PGDATA is already part of VM used space and must remain present. The allowance
must cover at least the backup copy and observed transient restore growth; use a larger
allowance when peak usage was not measured. Operational headroom must support normal
WAL, temporary queries, logs, and a future migration. Do not proceed merely because
`initdb` fits.

Arithmetic is not sufficient after an ENOSPC incident. Before authorising a retry,
restore the exact accepted backup into a fresh disposable native volume, verify data and
logs, record post-restore free bytes and volume size, then remove only that disposable
environment. At cutover time, remeasure VM free space and stop if it has fallen below
the proved pre-restore requirement.

The 2026-10-02 remediation restored the current 316,203,335-byte backup into a fresh
2.641 GB volume in 201 seconds. VM free space changed from 6,041,944,064 bytes after
`initdb` and 5,725,728,768 bytes after the backup copy to 3,132,583,936 bytes after the
full restore. PostgreSQL stayed healthy with zero restart, recovery, OOM, or ENOSPC
markers. These measurements are evidence for this backup only; repeat the calculation
when the backup or dataset changes.

## Accepted native rehearsal

On 2026-10-02 the arm64 image ran PostgreSQL 17.5 and PostGIS 3.6.4. A verified
302 MiB logical backup restored in 181 seconds, upgraded from `20260929_0009` to
`20261001_0010`, and passed three consecutive relation-member unique-index builds and
three identical full canonical geometry checksums with normal parallel settings. The
two Street rehearsals produced `6843/36416` and then `0 created / 0 changed / 6843
unchanged`. Backend tests (`104`) and frontend tests (`68`), static checks, production
build, isolated runtime/API controls, and a clean empty Compose migration all passed.
The native PostgreSQL log contained no abnormal backend termination, recovery, restart,
or OOM marker.

Use the existing production `.env`; do not put credentials in this runbook. Set a
timestamped host path outside the repository:

```bash
export CUTOVER_NAME="kartaspb-cutover-$(date -u +%Y%m%dT%H%M%SZ)"
export CUTOVER_DUMP="/private/tmp/$CUTOVER_NAME.dump"
export NATIVE_PROJECT=kartaspb-v2-native
```

## Quiesce and make one final backup

Stop database clients before the backup so the old and new databases cannot diverge:

```bash
docker stop kartaspb-v2-backend-1
docker ps --format '{{.Names}}' | grep -E 'kartaspb-v2-(migration|ingest)' && exit 1 || true
docker exec kartaspb-v2-db-1 pg_isready -U kartaspb -d kartaspb
docker exec kartaspb-v2-db-1 psql -U kartaspb -d kartaspb -v ON_ERROR_STOP=1 \
  -c "SELECT count(*) AS remaining_application_connections FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND application_name<>'pg_dump'"
docker exec kartaspb-v2-db-1 pg_dump -U kartaspb -d kartaspb \
  --format=custom --file="/tmp/$CUTOVER_NAME.dump"
docker cp "kartaspb-v2-db-1:/tmp/$CUTOVER_NAME.dump" "$CUTOVER_DUMP"
ls -lh "$CUTOVER_DUMP"
shasum -a 256 "$CUTOVER_DUMP"
docker run --rm -v /private/tmp:/backup:ro kartaspb-v2-db:postgres17-postgis3.6 \
  pg_restore --list "/backup/$(basename "$CUTOVER_DUMP")"
```

The dump is attempted once. If `pg_dump` fails, triggers another recovery, or the old
server becomes unhealthy, stop. Do not retry and do not silently substitute the older
`20260929_0009` backup.

## Restore into a new native volume

The distinct project creates `kartaspb-v2-native_postgres-data`; the old volume is not
mounted. Port `15433` avoids the old database listener during restore.

```bash
POSTGRES_PORT=15433 docker compose -p "$NATIVE_PROJECT" up -d --build db
./scripts/check-db-architecture.sh kartaspb-v2-native-db-1
docker cp "$CUTOVER_DUMP" kartaspb-v2-native-db-1:/tmp/kartaspb-cutover.dump
docker exec kartaspb-v2-native-db-1 pg_restore -U kartaspb -d kartaspb \
  --exit-on-error --no-owner /tmp/kartaspb-cutover.dump
docker exec kartaspb-v2-native-db-1 psql -U kartaspb -d kartaspb -v ON_ERROR_STOP=1 \
  -c "SELECT version_num FROM alembic_version" \
  -c "SELECT count(*) AS street_entities FROM domain.street_entities" \
  -c "SELECT count(*) AS street_members FROM domain.street_entity_members" \
  -c "SELECT count(*) FILTER (WHERE lifecycle_status='active') AS canonical FROM catalog.objects" \
  -c "SELECT count(*) FILTER (WHERE lifecycle_status='active') AS active_assignments, count(*) AS total_assignments FROM catalog.object_categories" \
  -c "SELECT (SELECT count(*) FROM catalog.object_sources) AS source_bindings, (SELECT count(*) FROM domain.districts WHERE enabled) AS districts, (SELECT count(*) FROM domain.facility_entities WHERE lifecycle_status='active') AS facilities, (SELECT count(*) FROM domain.facility_entity_members WHERE lifecycle_status='active') AS facility_members"
```

Required values are revision `20261001_0010`, Street `0/0`, canonical `417331`, active
assignments `417332`, total assignments `417336`, source bindings `417331`, districts
`18`, facilities `15`, and facility members `30`.

## Switch application clients

Only after every restore invariant passes:

```bash
docker stop kartaspb-v2-frontend-1 kartaspb-v2-db-1
POSTGRES_PORT=15433 BACKEND_PORT=8000 FRONTEND_PORT=5173 \
  docker compose -p "$NATIVE_PROJECT" up -d migration backend frontend --wait
curl --fail http://localhost:8000/api/health/live
curl --fail http://localhost:8000/api/health/ready
docker inspect kartaspb-v2-native-db-1 --format \
  'restart={{.RestartCount}} oom={{.State.OOMKilled}} health={{.State.Health.Status}}'
docker logs kartaspb-v2-native-db-1
```

Do not run Street refresh. Keep database clients stopped from the beginning of the final
backup until the native backend is healthy. The measured native restore took 181 seconds;
allow additional time for the single final backup, image/container startup, verification,
and backend health. This is a downtime operation, not a zero-downtime migration.

## Rollback

If the native runtime or application acceptance fails, do not delete either volume:

```bash
docker stop kartaspb-v2-native-backend-1 kartaspb-v2-native-frontend-1
docker stop kartaspb-v2-native-db-1
docker start kartaspb-v2-db-1
docker exec kartaspb-v2-db-1 pg_isready -U kartaspb -d kartaspb
docker start kartaspb-v2-backend-1 kartaspb-v2-frontend-1
curl --fail http://localhost:8000/api/health/ready
```

Never allow both old and new backends to accept writes concurrently. Preserve the new
native volume after rollback for evidence and diagnosis.
