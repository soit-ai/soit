"""Create a consistent backup of the SOIT Community Compose canonical data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SERVER_ROOT = REPOSITORY_ROOT / "server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))
DEFAULT_COMPOSE_FILE = REPOSITORY_ROOT / "docker" / "docker-compose.yml"
APPLICATION_SERVICES = {
    "api",
    "web",
    "knowledge-ingest-worker",
    "outbox-dispatcher",
    "bootstrap",
    "migrate",
}


class BackupCommandError(RuntimeError):
    """Raised when a backup precondition or component command fails."""


def main() -> int:
    args = _parse_args()
    try:
        report = create_backup(args)
    except BackupCommandError as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def create_backup(args: argparse.Namespace) -> dict[str, Any]:
    """Create canonical backups and a verified manifest."""

    output_root = args.output.resolve()
    if output_root == REPOSITORY_ROOT or REPOSITORY_ROOT in output_root.parents:
        raise BackupCommandError("backup output must be outside the Git checkout")
    if output_root.exists() and any(output_root.iterdir()):
        raise BackupCommandError(f"backup output is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    compose_file = args.compose_file.resolve()
    if not compose_file.is_file():
        raise BackupCommandError(f"compose file does not exist: {compose_file}")
    child_env = _compose_environment()
    child_env["MINIO_BACKUP_ENDPOINT"] = args.minio_endpoint
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
        raise BackupCommandError(
            "stop application services before backup: "
            + ", ".join(active_application_services)
        )
    for required in ("postgres", "minio"):
        if required not in running:
            raise BackupCommandError(f"required Compose service is not running: {required}")

    started_at = datetime.now(tz=UTC)
    backup_id = args.backup_id or f"backup_{started_at.strftime('%Y%m%dT%H%M%SZ')}"
    container_dump = f"/tmp/{backup_id}.dump"
    dump_path = output_root / "postgres.dump"
    try:
        _run(
            [
                *compose,
                "exec",
                "-T",
                "postgres",
                "sh",
                "-ec",
                'pg_dump --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" '
                f'--format=custom --no-owner --no-acl --file="{container_dump}"',
            ],
            env=child_env,
            label="create PostgreSQL custom-format dump",
        )
        _run(
            [*compose, "cp", f"postgres:{container_dump}", str(dump_path)],
            env=child_env,
            label="copy PostgreSQL dump to backup directory",
        )
    finally:
        _run(
            [*compose, "exec", "-T", "postgres", "rm", "-f", container_dump],
            env=child_env,
            label="remove temporary PostgreSQL dump",
            check=False,
        )
    if not dump_path.is_file() or dump_path.stat().st_size == 0:
        raise BackupCommandError("PostgreSQL dump is missing or empty")

    revision = _run(
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
        label="read Alembic revision",
    ).strip()
    if not revision or "\n" in revision:
        raise BackupCommandError(f"unexpected Alembic revision output: {revision!r}")
    (output_root / "alembic-revision.txt").write_text(
        f"{revision}\n", encoding="utf-8"
    )

    object_root = output_root / "object-storage"
    object_root.mkdir(parents=True, exist_ok=True)
    _mirror_objects(
        compose,
        source="local/${MINIO_BUCKET:-soit-artifacts}",
        destination="/backup",
        host_directory=object_root,
        env=child_env,
        remove_destination_extras=False,
        label="mirror object storage to backup directory",
    )

    finished_at = datetime.now(tz=UTC)
    manifest = _build_manifest(
        output_root,
        backup_id=backup_id,
        platform_version=args.platform_version,
        alembic_revision=revision,
        started_at=started_at,
        finished_at=finished_at,
        rpo_target_minutes=args.rpo_target_minutes,
        rto_target_minutes=args.rto_target_minutes,
    )
    manifest_path = output_root / "backup-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    from scripts.verify_backup_manifest import validate_backup_manifest

    validation = validate_backup_manifest(manifest, backup_root=output_root)
    return {
        **validation,
        "manifest": str(manifest_path),
        "startedAt": manifest["startedAt"],
        "finishedAt": manifest["finishedAt"],
    }


def _build_manifest(
    output_root: Path,
    *,
    backup_id: str,
    platform_version: str,
    alembic_revision: str,
    started_at: datetime,
    finished_at: datetime,
    rpo_target_minutes: int,
    rto_target_minutes: int,
) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(output_root.rglob("*")):
        if not path.is_file() or path.name == "backup-manifest.json":
            continue
        relative_path = path.relative_to(output_root).as_posix()
        files.append(
            {
                "path": relative_path,
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    object_files = [item["path"] for item in files if item["path"].startswith("object-storage/")]
    return {
        "featureKey": "operations.backup_manifest",
        "schemaVersion": 1,
        "backup_id": backup_id,
        "platform_version": platform_version,
        "alembic_revision": alembic_revision,
        "startedAt": _iso_z(started_at),
        "finishedAt": _iso_z(finished_at),
        "rpo_target_minutes": rpo_target_minutes,
        "rto_target_minutes": rto_target_minutes,
        "files": files,
        "components": {
            "postgres": {
                "strategy": "pg_dump_custom",
                "files": ["postgres.dump", "alembic-revision.txt"],
            },
            "object_storage": {
                "strategy": "object_mirror",
                "files": object_files,
            },
            "vector_index": {
                "recovery_mode": "rebuild_from_canonical_data",
                "canonical_sources": ["postgres", "object_storage"],
                "files": [],
            },
            "secret_metadata": {
                "recovery_mode": "postgres_metadata",
                "secret_values_included": False,
                "files": ["postgres.dump"],
            },
        },
    }


def _mirror_objects(
    compose: list[str],
    *,
    source: str,
    destination: str,
    host_directory: Path,
    env: dict[str, str],
    remove_destination_extras: bool,
    label: str,
) -> None:
    mirror_flags = "--overwrite"
    if remove_destination_extras:
        mirror_flags += " --remove"
    mount = f"{host_directory.resolve().as_posix()}:/backup"
    command = (
        'mc alias set local "$MINIO_BACKUP_ENDPOINT" '
        '"$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" >/dev/null; '
        f"mc mirror {mirror_flags} {source} {destination}"
    )
    _run(
        [
            *compose,
            "run",
            "--rm",
            "--no-deps",
            "--volume",
            mount,
            "--entrypoint",
            "/bin/sh",
            "-e",
            "MINIO_BACKUP_ENDPOINT",
            "-e",
            "MINIO_ACCESS_KEY",
            "-e",
            "MINIO_SECRET_KEY",
            "-e",
            "MINIO_BUCKET",
            "minio-init",
            "-ec",
            command,
        ],
        env=env,
        label=label,
    )


def _compose_command(compose_file: Path, project_name: str) -> list[str]:
    if not project_name.strip():
        raise BackupCommandError("project name must not be empty")
    return [
        "docker",
        "compose",
        "--project-name",
        project_name,
        "--file",
        str(compose_file),
    ]


def _compose_environment() -> dict[str, str]:
    env = dict(os.environ)
    env_path = REPOSITORY_ROOT / ".env"
    if env_path.is_file():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    env.setdefault("MINIO_ACCESS_KEY", "soitminio")
    env.setdefault("MINIO_SECRET_KEY", "soitminio")
    env.setdefault("MINIO_BUCKET", "soit-artifacts")
    env.setdefault("MINIO_BACKUP_ENDPOINT", "http://minio:9000")
    return env


def _run(
    command: list[str],
    *,
    env: dict[str, str],
    label: str,
    capture_output: bool = False,
    check: bool = True,
) -> str:
    result = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=env,
        check=False,
        capture_output=capture_output,
        text=True,
    )
    if check and result.returncode != 0:
        details = (result.stderr or result.stdout or "no command output").strip()
        raise BackupCommandError(f"failed to {label}: {details}")
    return result.stdout if capture_output else ""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iso_z(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compose-file", type=Path, default=DEFAULT_COMPOSE_FILE)
    parser.add_argument("--project-name", default=os.getenv("COMPOSE_PROJECT_NAME", "soit"))
    parser.add_argument("--backup-id")
    parser.add_argument("--platform-version", default=os.getenv("PLATFORM_VERSION", "1.0.0"))
    parser.add_argument(
        "--minio-endpoint",
        default=os.getenv("MINIO_BACKUP_ENDPOINT", "http://minio:9000"),
        help="MinIO endpoint reachable from the temporary mc container",
    )
    parser.add_argument("--rpo-target-minutes", type=int, default=60)
    parser.add_argument("--rto-target-minutes", type=int, default=240)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
