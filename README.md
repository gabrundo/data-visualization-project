# Fantacalcio Mantra analysis

Requirements: [prd/README.md](prd/README.md).
The local database uses PostgreSQL 18 in Docker Compose with persistent storage.

## Start

With Docker running and Docker Compose installed:

```bash
cp .env.example .env
# Edit .env and replace POSTGRES_PASSWORD with your own password.
docker compose up -d --wait
docker compose ps
```

Connect at `127.0.0.1:5432` using the database, username, and password in `.env`.
Change `POSTGRES_PORT` if the port is occupied. Other services added to this
Compose project can connect at `db:5432`. `.env` is ignored by Git.

Open a SQL shell:

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Use `\dt` to list tables and `\q` to exit. Source imports and Python database
integration are not implemented yet; the database starts with empty tables.

## Persistence

The named Docker volume `fantacalcio_postgres_data` retains data when the
container is recreated, including with:

```bash
docker compose down
docker compose up -d --wait
```

**`docker compose down -v` deletes the volume and its data.** A persistent volume
is not a backup.

[db/init/001_schema.sql](db/init/001_schema.sql) initializes an empty volume.
See [db/README.md](db/README.md) for the design and import conventions.
Initialization scripts run only on first startup: later schema changes need
explicit migrations, not volume deletion. Changing credentials in `.env` also
does not change credentials in an initialized database.

The volume mounts at `/var/lib/postgresql`, as required by the
[official PostgreSQL 18 image](https://hub.docker.com/_/postgres).
Keep the major version fixed; major upgrades require a database migration.

## Backup and restore

Create a backup before imports or schema changes, using a new filename each time:

```bash
mkdir -p backups
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backups/fantacalcio.dump
```

Restore into a new, empty database:

```bash
docker compose exec db sh -c 'createdb -U "$POSTGRES_USER" fantacalcio_restore'
docker compose exec -T db sh -c 'pg_restore --exit-on-error --no-owner -U "$POSTGRES_USER" -d fantacalcio_restore' < backups/fantacalcio.dump
```

Backups are ignored by Git. Keep a copy outside this machine for recovery from
disk loss. View startup errors with `docker compose logs db`.
