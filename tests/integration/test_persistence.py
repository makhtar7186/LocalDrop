"""Persistance SQLite, migrations et reprise après redémarrage (§5.2, §11, §16.2, FR-026)."""

import hashlib
import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, inspect

from localdrop.core.config import Settings
from localdrop.domain.devices.models import Device, DeviceStatus, Platform
from localdrop.domain.sessions.models import Session, SessionStatus
from localdrop.domain.transfers.models import ChunkRecord, Direction, Transfer, TransferStatus
from localdrop.infrastructure.database.engine import database_url, make_engine, make_session_factory
from localdrop.infrastructure.database.memory import InMemorySessionRepository
from localdrop.infrastructure.database.memory_transfers import InMemoryTransferRepository
from localdrop.infrastructure.database.migrate import (
    alembic_config,
    backup_database,
    current_revision,
    upgrade_database,
)
from localdrop.infrastructure.database.models import Base
from localdrop.infrastructure.database.sql_repositories import (
    SqlSessionRepository,
    SqlTransferRepository,
)
from localdrop.infrastructure.network.interfaces import AddressCandidate
from localdrop.services.container import AppServices, build_services

pytestmark = pytest.mark.integration
NOW = datetime(2026, 11, 20, 12, 0, 0, 123456, tzinfo=UTC)


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    db_dir = tmp_path / "database"
    db_dir.mkdir()
    eng = make_engine(database_url(db_dir))
    upgrade_database(eng, db_dir)
    yield eng
    eng.dispose()


# ----------------------------------------------------------------------------- migrations
def test_migrated_schema_matches_orm_models(engine: Engine) -> None:
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []
    assert current_revision(engine) == "0001"


def test_downgrade_then_upgrade(engine: Engine) -> None:
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    assert {"sessions", "devices", "transfers", "transfer_chunks"} <= set(
        inspect(engine).get_table_names()
    )


def test_sqlite_pragmas_for_durability(engine: Engine) -> None:
    with engine.connect() as connection:
        raw = connection.connection.driver_connection
        assert raw is not None
        assert raw.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert raw.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert raw.execute("PRAGMA synchronous").fetchone()[0] == 2  # FULL


def test_backups_are_rotated(engine: Engine, tmp_path: Path) -> None:
    db_file = tmp_path / "database" / "localdrop.db"
    backups = tmp_path / "database" / "backups"
    for _ in range(4):
        backup_database(db_file, backups, keep=2)
    kept = sorted(backups.glob("localdrop-*.db"))
    assert len(kept) == 2
    assert all(f.stat().st_size > 0 for f in kept)


# ----------------------------------------------------------------------------- contrat des dépôts
Repos = tuple[object, object]


@pytest.fixture(params=["memory", "sqlite"])
def repos(request: pytest.FixtureRequest, engine: Engine) -> Repos:
    if request.param == "memory":
        return InMemorySessionRepository(), InMemoryTransferRepository()
    factory = make_session_factory(engine)
    return SqlSessionRepository(factory), SqlTransferRepository(factory)


def _session(session_id: str = "s1", created: datetime = NOW) -> Session:
    return Session(
        id=session_id,
        created_at=created,
        expires_at=created + timedelta(hours=12),
        status=SessionStatus.ACTIVE,
        pairing_secret_hash="a" * 64,
        pairing_expires_at=created + timedelta(minutes=5),
    )


def _device(device_id: str = "d1", session_id: str = "s1") -> Device:
    return Device(
        id=device_id,
        session_id=session_id,
        display_name="Pixel été",
        platform=Platform.ANDROID,
        status=DeviceStatus.CONNECTED,
        token_hash=f"{device_id:0>64}",
        client_ip="192.168.1.50",
        created_at=NOW,
        last_seen_at=NOW,
        connected_at=NOW,
    )


def _transfer(transfer_id: str = "t1", device_id: str = "d1") -> Transfer:
    return Transfer(
        id=transfer_id,
        device_id=device_id,
        direction=Direction.UPLOAD,
        filename="../Vidéo.mp4",
        safe_filename="Vidéo.mp4",
        total_size=10,
        chunk_size=4,
        total_chunks=3,
        status=TransferStatus.WAITING,
        created_at=NOW,
        updated_at=NOW,
        expires_at=NOW + timedelta(hours=24),
    )


def test_sessions_and_devices_round_trip(repos: Repos) -> None:
    sessions = repos[0]
    assert isinstance(sessions, InMemorySessionRepository | SqlSessionRepository)
    sessions.save_session(_session())
    sessions.save_session(_session("s0", NOW - timedelta(hours=1)))
    sessions.save_device(_device())

    assert sessions.get_session("s1") == _session()
    assert sessions.get_device("d1") == _device()  # datetimes UTC conservés à la µs
    assert sessions.get_device_by_token_hash(_device().token_hash) == _device()
    assert [d.id for d in sessions.list_devices("s1")] == ["d1"]
    active = sessions.find_active_session(NOW)
    assert active is not None and active.id == "s1"  # la plus récente
    assert sessions.find_active_session(NOW + timedelta(hours=13)) is None

    revoked = _session()
    revoked.status = SessionStatus.REVOKED
    sessions.save_session(revoked)
    found = sessions.find_active_session(NOW)
    assert found is not None and found.id == "s0"


def test_transfers_conditional_update_and_chunks(repos: Repos) -> None:
    sessions, transfers = repos
    assert isinstance(sessions, InMemorySessionRepository | SqlSessionRepository)
    assert isinstance(transfers, InMemoryTransferRepository | SqlTransferRepository)
    sessions.save_session(_session())
    sessions.save_device(_device())
    transfers.add(_transfer())

    moving = _transfer()
    moving.status = TransferStatus.TRANSFERRING
    assert transfers.save(moving, expected_status=TransferStatus.WAITING) is True
    assert transfers.save(moving, expected_status=TransferStatus.WAITING) is False  # perdu
    stored = transfers.get("t1")
    assert stored is not None and stored.status is TransferStatus.TRANSFERRING
    assert stored.filename == "../Vidéo.mp4"

    assert transfers.add_chunk("t1", ChunkRecord(0, 4, "b" * 64, NOW)) is True
    assert transfers.add_chunk("t1", ChunkRecord(0, 4, "c" * 64, NOW)) is False  # unique
    assert transfers.add_chunk("t1", ChunkRecord(2, 2, "d" * 64, NOW)) is True
    assert sorted(transfers.get_chunks("t1")) == [0, 2]
    chunk = transfers.get_chunk("t1", 0)
    assert chunk is not None and chunk.sha256 == "b" * 64
    assert transfers.get_chunk("t1", 1) is None
    assert transfers.received_bytes("t1") == 6
    assert transfers.received_bytes("inconnu") == 0
    assert [t.id for t in transfers.list_for_device("d1")] == ["t1"]


# ----------------------------------------------------------------------------- redémarrage
@pytest.fixture
def sqlite_settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        receive_dir=tmp_path / "recus",
        web_dist_dir=None,
        chunk_size=64 * 1024,
        network_poll_seconds=0,
        free_space_margin=0,
        persistence="sqlite",
    )


@pytest.fixture
def start(sqlite_settings: Settings) -> Iterator[Callable[[], AppServices]]:
    """Démarre les services ; chaque appel simule un redémarrage du processus."""
    running: list[AppServices] = []

    def _start() -> AppServices:
        for previous in running:
            previous.close()
        running.clear()
        services = build_services(
            sqlite_settings,
            address_provider=lambda: [AddressCandidate(1, "192.168.1.14", "Wi-Fi")],
        )
        running.append(services)
        return services

    yield _start
    for services in running:
        services.close()


def _approved_device(services: AppServices) -> tuple[Device, str]:
    info = services.pairing.current_pairing()
    joined = services.pairing.join(
        session_id=info.session_id,
        secret=info.secret,
        display_name="Pixel",
        platform=Platform.ANDROID,
        client_ip="192.168.1.50",
    )
    services.pairing.approve(joined.device.id)
    return services.pairing.authenticate(joined.device_token), joined.device_token


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


DATA = os.urandom(64 * 1024 * 2 + 500)  # 3 blocs
PARTS = [DATA[i : i + 64 * 1024] for i in range(0, len(DATA), 64 * 1024)]


def test_FR_026_upload_resumes_after_server_restart(
    start: Callable[[], AppServices], sqlite_settings: Settings
) -> None:
    first = start()
    device, token = _approved_device(first)
    transfer = first.transfers.create_upload(device, "film.mp4", len(DATA))
    first.transfers.put_chunk(device, transfer.id, 0, PARTS[0], sha(PARTS[0]))
    first.transfers.put_chunk(device, transfer.id, 2, PARTS[2], sha(PARTS[2]))

    # --- redémarrage : l'appareil approuvé et le manifeste sont retrouvés
    second = start()
    assert second.reconcile_report.paused == [transfer.id]
    device = second.pairing.authenticate(token)
    paused = second.transfers.get(device, transfer.id)
    assert paused.status is TransferStatus.PAUSED
    assert paused.received_bytes == len(PARTS[0]) + len(PARTS[2])
    assert second.transfers.received_chunks(device, transfer.id) == [0, 2]

    second.transfers.resume(device, transfer.id)
    second.transfers.put_chunk(device, transfer.id, 1, PARTS[1], sha(PARTS[1]))
    done = second.transfers.complete(device, transfer.id, sha(DATA))
    assert done.status is TransferStatus.COMPLETED
    assert (sqlite_settings.receive_dir / "film.mp4").read_bytes() == DATA


def test_interrupted_verification_is_replayed_at_startup(
    start: Callable[[], AppServices], sqlite_settings: Settings
) -> None:
    first = start()
    device, _ = _approved_device(first)
    transfer = first.transfers.create_upload(device, "doc.pdf", len(DATA))
    for index, part in enumerate(PARTS):
        first.transfers.put_chunk(device, transfer.id, index, part, sha(part))
    # Arrêt brutal pendant la vérification : état « verifying » et hash annoncé enregistrés.
    stored = first.transfers.get(device, transfer.id)
    stored.status = TransferStatus.VERIFYING
    stored.expected_sha256 = sha(DATA)
    first.transfers._repo.save(stored)

    second = start()
    assert second.reconcile_report.reverified == [transfer.id]
    device = second.pairing.active_device(device.id)
    assert second.transfers.get(device, transfer.id).status is TransferStatus.COMPLETED
    assert (sqlite_settings.receive_dir / "doc.pdf").read_bytes() == DATA


def test_missing_temp_file_fails_and_orphans_are_removed(
    start: Callable[[], AppServices], sqlite_settings: Settings
) -> None:
    first = start()
    device, _ = _approved_device(first)
    lost = first.transfers.create_upload(device, "perdu.bin", 10)
    first.storage.temp_path(lost.id).unlink()
    orphan = first.storage.temp_dir / ("f" * 32 + ".part")
    orphan.write_bytes(b"reste d'un ancien transfert")
    kept_file = sqlite_settings.receive_dir / "photo.jpg"
    kept_file.write_bytes(b"fichier final")

    second = start()
    report = second.reconcile_report
    assert report.failed == [lost.id]
    assert report.orphans_deleted == ["f" * 32]
    assert not orphan.exists()
    assert kept_file.read_bytes() == b"fichier final"  # jamais un fichier final
    device = second.pairing.active_device(device.id)
    failed = second.transfers.get(device, lost.id)
    assert (failed.status, failed.error_code) == (TransferStatus.FAILED, "TEMP_FILE_MISSING")


def test_revoked_device_stays_revoked_after_restart(start: Callable[[], AppServices]) -> None:
    first = start()
    device, token = _approved_device(first)
    first.pairing.revoke(device.id)
    second = start()
    with pytest.raises(Exception, match="Session terminée"):
        second.pairing.authenticate(token)


def test_new_pairing_secret_after_restart(start: Callable[[], AppServices]) -> None:
    first = start()
    before = first.pairing.current_pairing()
    second = start()
    after = second.pairing.current_pairing()
    assert after.session_id == before.session_id  # même session, appareils conservés
    assert after.secret != before.secret  # mais nouveau QR Code : le secret n'est pas stocké


# ----------------------------------------------------------------------------- historique (phase 7)
def _seed_history(repos: Repos) -> None:
    sessions, transfers = repos
    assert isinstance(sessions, InMemorySessionRepository | SqlSessionRepository)
    assert isinstance(transfers, InMemoryTransferRepository | SqlTransferRepository)
    sessions.save_session(_session())
    sessions.save_device(_device("d1"))
    sessions.save_device(_device("d2"))
    specs = [
        ("t1", "d1", Direction.UPLOAD, TransferStatus.COMPLETED, "Été 2026.mp4", 0),
        ("t2", "d1", Direction.DOWNLOAD, TransferStatus.COMPLETED, "rapport_final.pdf", 1),
        ("t3", "d1", Direction.UPLOAD, TransferStatus.FAILED, "100%_réussi.txt", 2),
        ("t4", "d2", Direction.UPLOAD, TransferStatus.COMPLETED, "été.jpg", 3),
        ("t5", "d1", Direction.UPLOAD, TransferStatus.TRANSFERRING, "en_cours.iso", 4),
    ]
    for transfer_id, device_id, direction, status, name, minutes in specs:
        transfer = _transfer(transfer_id, device_id)
        transfer.direction = direction
        transfer.status = status
        transfer.safe_filename = name
        transfer.filename = name
        transfer.created_at = transfer.updated_at = NOW + timedelta(minutes=minutes)
        transfers.add(transfer)


def test_FR_034_history_filters_and_pagination(repos: Repos) -> None:
    from localdrop.domain.transfers.query import TransferQuery

    _seed_history(repos)
    transfers = repos[1]
    assert isinstance(transfers, InMemoryTransferRepository | SqlTransferRepository)

    def ids(**criteria: object) -> list[str]:
        return [t.id for t in transfers.search(TransferQuery(**criteria)).items]  # type: ignore[arg-type]

    assert ids() == ["t5", "t4", "t3", "t2", "t1"]  # du plus récent au plus ancien
    assert ids(device_id="d1", direction=Direction.UPLOAD) == ["t5", "t3", "t1"]
    assert ids(statuses=frozenset({TransferStatus.FAILED, TransferStatus.TRANSFERRING})) == [
        "t5",
        "t3",
    ]
    # Insensible à la casse ET aux accents majuscules : « été » trouve « Été 2026.mp4 ».
    assert ids(text="été") == ["t4", "t1"]
    assert ids(text="ÉTÉ", device_id="d1") == ["t1"]
    # Les jokers SQL saisis par l'utilisateur sont pris littéralement.
    assert ids(text="100%") == ["t3"]
    assert ids(text="_final") == ["t2"]
    assert ids(text="%") == ["t3"]

    page = transfers.search(TransferQuery(limit=2, offset=2))
    assert ([t.id for t in page.items], page.total) == (["t3", "t2"], 5)


def test_FR_035_purge_only_old_terminal_transfers(repos: Repos) -> None:
    _seed_history(repos)
    sessions, transfers = repos
    assert isinstance(transfers, InMemoryTransferRepository | SqlTransferRepository)
    assert isinstance(sessions, InMemorySessionRepository | SqlSessionRepository)
    transfers.add_chunk("t1", ChunkRecord(0, 4, "b" * 64, NOW))

    # t1, t2, t3 terminés avant NOW+2min30 ; t4 terminé après ; t5 actif.
    purged = transfers.delete_terminal_before(NOW + timedelta(minutes=2, seconds=30))
    assert purged == 3
    assert [t.id for t in transfers.list_all()] == ["t4", "t5"]
    assert transfers.get_chunks("t1") == {}

    assert sessions.expire_sessions(NOW) == 0
    assert sessions.expire_sessions(NOW + timedelta(hours=13)) == 1
    assert sessions.find_active_session(NOW) is None
