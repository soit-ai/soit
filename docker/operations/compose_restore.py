"""Restore SOIT Community canonical Compose data into an explicit target."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from compose_backup import (
    APPLICATION_SERVICES,
    DEFAULT_COMPOSE_FILE,
    BackupCommandError,
    _compose_command,
    _compose_environment,
    _mirror_objects,
    _run,
)


class RestoreCommandError(RuntimeError):
    """Raised when a restore target is unsafe or a recovery command fails."""


def main() -> int:
    args = _parse_args()
    try:
        report = restore_canonical_data(args)
    except (RestoreCommandError, BackupCommandError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def restore_canonical_data(args: argparse.Namespace) -> dict[str, Any]:
    """Restore PostgreSQL and object storage after exact target confirmation."""

    backup_root = args.backup_root.resolve()
    manifest_path = backup_root / "backup-manifest.json"
    if not manifest_path.is_file():
        raise RestoreCommandError(f"backup manifest does not exist: {manifest_path}")

    from scripts.verify_backup_manifest import (
        load_backup_manifest,
        validate_backup_manifest,
    )

    manifest = load_backup_manifest(manifest_path)
    validate_backup_manifest(manifest, backup_root=backup_root)

    child_env = _compose_environment()
    child_env["MINIO_BACKUP_ENDPOINT"] = args.minio_endpoint
    database_name = child_env.get("DATABASE_NAME", "soit")
    bucket_name = child_env.get("MINIO_BUCKET", "soit-artifacts")
    _confirm_target(
        actual_project=args.project_name,
        confirmed_project=args.confirm_project,
        actual_database=database_name,
        confirmed_database=args.confirm_database,
        actual_bucket=bucket_name,
        confirmed_bucket=args.confirm_bucket,
    )

    compose_file = args.compose_file.resolve()
    compose = _compose_command(compose_file, args.project_name)
    running = set(
        _run(
            [*compose, "ps", "--status", "running", "--services"],
            env=child_env,
            capture_output=True,
            label="inspect running Compose services",
        ).splitlines()
    )
    active_application_services = sorted(running & APPLICATION_SERVICES)
    if active_application_services:
        raise RestoreCommandError(
            "stop application services before restore: "
            + ", ".join(active_application_services)
        )
    for required in ("postgres", "minio"):
        if required not in running:
            raise RestoreCommandError(f"required Compose service is not running: {required}")

    dump_path = backup_root / "postgres.dump"
    container_dump = f"/tmp/{manifest['backup_id']}.dump"
    try:
        _run(
            [*compose, "cp", str(dump_path), f"postgres:{container_dump}"],
            env=child_env,
            label="copy PostgreSQL dump into target container",
        )
        _run(
            [
                *compose,
                "exec",
                "-T",
                "postgres",
                "sh",
                "-ec",
                'dropdb --username="$POSTGRES_USER" --if-exists --force "$POSTGRES_DB"; '
                'createdb --username="$POSTGRES_USER" "$POSTGRES_DB"; '
                f'pg_restore --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" '
                f'--exit-on-error --no-owner --no-acl "{container_dump}"',
            ],
            env=child_env,
            label="replace and restore target PostgreSQL database",
        )
    finally:
        _run(
            [*compose, "exec", "-T", "postgres", "rm", "-f", container_dump],
            env=child_env,
            label="remove temporary target dump",
            check=False,
        )

    object_root = backup_root / "object-storage"
    _mirror_objects(
        compose,
        source="/backup",
        destination="local/${MINIO_BUCKET:-soit-artifacts}",
        host_directory=object_root,
        env=child_env,
        remove_destination_extras=True,
        label="replace target object-storage bucket",
    )

    restored_revision = _run(
        [
            *compose,
            "exec",
            "-T",
            "postgres",
            "sh",
            "-ec",
            'psql --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" '
            '--tuples-only --no-align --command="SELECT version_num FROM alembic_version"',
        ],
        env=child_env,
        capture_output=True,
        label="read restored Alembic revision",
    ).strip()
    if restored_revision != manifest["alembic_revision"]:
        raise RestoreCommandError(
            "restored Alembic revision does not match backup manifest: "
            f"{restored_revision!r} != {manifest['alembic_revision']!r}"
        )

    with tempfile.TemporaryDirectory(prefix="soit-object-readback-") as temp_dir:
        readback_root = Path(temp_dir)
        _mirror_objects(
            compose,
            source="local/${MINIO_BUCKET:-soit-artifacts}",
            destination="/backup",
            host_directory=readback_root,
            env=child_env,
            remove_destination_extras=False,
            label="read back restored object-storage bucket",
        )
        _verify_object_readback(manifest, readback_root)

    return {
        "passed": True,
        "backup_id": manifest["backup_id"],
        "canonical_data_restored": True,
        "alembic_revision": restored_revision,
        "target": {
            "project": args.project_name,
            "database": database_name,
            "bucket": bucket_name,
        },
        "required_before_start": [
            "reconnect or rotate every secret value",
            "rebuild every active vector index",
            "validate retrieval query and citation readback",
            "run worker, outbox, and product smoke tests",
            "record restore-drill evidence and rollback result",
        ],
    }


def _confirm_target(
    *,
    actual_project: str,
    confirmed_project: str | None,
    actual_database: str,
    confirmed_database: str | None,
    actual_bucket: str,
    confirmed_bucket: str | None,
) -> None:
    expected = {
        "project": (actual_project, confirmed_project),
        "database": (actual_database, confirmed_database),
        "bucket": (actual_bucket, confirmed_bucket),
    }
    mismatches = [
        f"{label}={actual!r}"
        for label, (actual, confirmed) in expected.items()
        if not actual or confirmed != actual
    ]
    if mismatches:
        raise RestoreCommandError(
            "restore target confirmation failed; repeat exact values for "
            + ", ".join(mismatches)
        )


def _verify_object_readback(manifest: dict[str, Any], readback_root: Path) -> None:
    expected = {
        record["path"].removeprefix("object-storage/"): record
        for record in manifest["files"]
        if record["path"].startswith("object-storage/")
    }
    actual_paths = {
        path.relative_to(readback_root).as_posix()
        for path in readback_root.rglob("*")
        if path.is_file()
    }
    if actual_paths != set(expected):
        raise RestoreCommandError("restored object-storage file set differs from manifest")
    for relative_path, record in expected.items():
        path = readback_root / relative_path
        if path.stat().st_size != record["size_bytes"]:
            raise RestoreCommandError(
                f"restored object-storage size mismatch: {relative_path}"
            )
        if _sha256(path) != record["sha256"]:
            raise RestoreCommandError(
                f"restored object-storage checksum mismatch: {relative_path}"
            )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-root", type=Path, required=True)
    parser.add_argument("--compose-file", type=Path, default=DEFAULT_COMPOSE_FILE)
    parser.add_argument("--project-name", default=os.getenv("COMPOSE_PROJECT_NAME", "soit"))
    parser.add_argument(
        "--minio-endpoint",
        default=os.getenv("MINIO_BACKUP_ENDPOINT", "http://minio:9000"),
        help="MinIO endpoint reachable from the temporary mc container",
    )
    parser.add_argument("--confirm-project")
    parser.add_argument("--confirm-database")
    parser.add_argument("--confirm-bucket")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
