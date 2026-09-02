"""
Meoo 云库适配：
- 优先使用 SUPABASE_DB_URL / DATABASE_URL（Postgres）
- FREE 套餐通常不下发直连串时，用 SQLite + Supabase Storage 做持久化同步
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

BUCKET = "aisci-data"
OBJECT_KEY = "aiscientist.db"
REPORTS_OBJECT_KEY = "reports_bundle.tar.gz"
PINGFENBIAO_JOBS_OBJECT_KEY = "pingfenbiao_jobs_bundle.tar.gz"
ITERATIVE_EXPERIMENTS_OBJECT_KEY = "iterative_experiments_bundle.tar.gz"
SHAXIANG_DATA_OBJECT_KEY = "shaxiang_data_bundle.tar.gz"
_sync_stop = threading.Event()
_sync_thread: Optional[threading.Thread] = None


def resolve_database_url(current: str) -> str:
    """优先云 Postgres 直连串，否则保留现有 DATABASE_URL。"""
    supabase_db = (os.environ.get("SUPABASE_DB_URL") or "").strip()
    if supabase_db:
        if supabase_db.startswith("postgres://"):
            supabase_db = "postgresql+psycopg2://" + supabase_db[len("postgres://") :]
        elif supabase_db.startswith("postgresql://") and "+psycopg" not in supabase_db:
            supabase_db = "postgresql+psycopg2://" + supabase_db[len("postgresql://") :]
        os.environ["DATABASE_URL"] = supabase_db
        return supabase_db
    return current


def _supabase_config() -> tuple[str, str] | tuple[None, None]:
    # Ensure Meoo keys from .env are visible even if not in process env yet
    try:
        from dotenv import load_dotenv

        here = Path(__file__).resolve()
        backend_root = here.parents[2]  # backend/
        project_root = backend_root.parent
        load_dotenv(backend_root / ".env", override=False)
        load_dotenv(project_root / ".env", override=False)
    except Exception:
        pass

    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or ""
    ).strip()
    if not url or not key:
        return None, None
    return url, key


def cloud_sqlite_sync_enabled(database_url: str) -> bool:
    if os.environ.get("AISCI_CLOUD_DB_SYNC", "true").lower() in ("0", "false", "no"):
        return False
    if not database_url.startswith("sqlite"):
        return False
    url, key = _supabase_config()
    return bool(url and key)


def _sqlite_path(database_url: str) -> Path:
    raw = database_url.replace("sqlite:///", "", 1)
    path = Path(raw)
    if not path.is_absolute():
        # uvicorn cwd is backend/
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _headers(key: str) -> dict:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }


def ensure_bucket(base_url: str, key: str) -> None:
    with httpx.Client(timeout=30.0) as client:
        listed = client.get(f"{base_url}/storage/v1/bucket", headers=_headers(key))
        if listed.status_code == 200:
            names = {b.get("name") for b in (listed.json() or []) if isinstance(b, dict)}
            if BUCKET in names:
                return
        resp = client.post(
            f"{base_url}/storage/v1/bucket",
            headers={**_headers(key), "Content-Type": "application/json"},
            json={"id": BUCKET, "name": BUCKET, "public": False},
        )
        if resp.status_code not in (200, 201):
            logger.warning("create bucket %s failed: %s %s", BUCKET, resp.status_code, resp.text[:200])


def sqlite_integrity_ok(path: Path) -> bool:
    """PRAGMA integrity_check；损坏或无法打开时返回 False。"""
    import sqlite3

    if not path.is_file() or path.stat().st_size < 100:
        return False
    try:
        con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            row = con.execute("PRAGMA integrity_check").fetchone()
            return bool(row and row[0] == "ok")
        finally:
            con.close()
    except Exception as exc:
        logger.warning("sqlite integrity check failed for %s: %s", path, exc)
        return False


def download_sqlite(database_url: str) -> bool:
    """从 Storage 恢复 SQLite。下载到临时文件并做完整性校验，失败则保留本地原库。"""
    base_url, key = _supabase_config()
    if not base_url or not key:
        return False
    path = _sqlite_path(database_url)
    try:
        ensure_bucket(base_url, key)
        with httpx.Client(timeout=120.0) as client:
            resp = client.get(
                f"{base_url}/storage/v1/object/{BUCKET}/{OBJECT_KEY}",
                headers=_headers(key),
            )
            if resp.status_code == 404:
                logger.info("cloud sqlite: no remote object yet")
                return False
            if resp.status_code != 200:
                logger.warning("cloud sqlite download failed: %s", resp.status_code)
                return False

            tmp = path.with_suffix(path.suffix + ".download")
            tmp.write_bytes(resp.content)
            if not sqlite_integrity_ok(tmp):
                logger.error(
                    "cloud sqlite download rejected: integrity check failed (%s bytes)",
                    len(resp.content),
                )
                try:
                    tmp.unlink(missing_ok=True)
                except Exception:
                    pass
                return False

            # 覆盖前备份现有库（即使已损坏也便于排查）
            if path.is_file():
                bak = path.with_suffix(path.suffix + ".pre_restore.bak")
                try:
                    bak.write_bytes(path.read_bytes())
                except Exception as exc:
                    logger.warning("backup before sqlite restore failed: %s", exc)

            tmp.replace(path)
            logger.info("cloud sqlite restored from storage (%s bytes)", len(resp.content))
            return True
    except Exception as exc:
        logger.warning("cloud sqlite download error: %s", exc)
        return False


def _storage_root() -> Path:
    # backend/storage
    return Path(__file__).resolve().parents[2] / "storage"


def _project_root() -> Path:
    # AISci/
    return Path(__file__).resolve().parents[3]


def _shaxiang_data_root() -> Path:
    return _project_root() / "shaxiang-main" / "shaxiang-main" / "data"


def download_reports_bundle() -> bool:
    """从 Storage 拉取报告产物包并解压到 backend/storage/reports。"""
    return _download_and_extract_tar(
        REPORTS_OBJECT_KEY,
        _storage_root(),
        label="reports",
    )


def download_pingfenbiao_jobs_bundle() -> bool:
    """从 Storage 拉取预测 Tab 任务包到 backend/storage/pingfenbiao_jobs。"""
    import shutil

    dest = _storage_root() / "pingfenbiao_jobs"
    # 先清空旧任务，避免已删除的本地记录（如错误评分）在云端残留
    if dest.exists():
        for child in dest.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            elif child.is_file():
                try:
                    child.unlink()
                except OSError:
                    pass
    dest.mkdir(parents=True, exist_ok=True)
    # tar 内路径为 pingfenbiao_jobs/<job_id>/...
    return _download_and_extract_tar(
        PINGFENBIAO_JOBS_OBJECT_KEY,
        _storage_root(),
        label="pingfenbiao_jobs",
    )


def download_iterative_experiments_bundle() -> bool:
    """恢复 backend/storage/iterative_experiments/{project_id}.json"""
    (_storage_root() / "iterative_experiments").mkdir(parents=True, exist_ok=True)
    return _download_and_extract_tar(
        ITERATIVE_EXPERIMENTS_OBJECT_KEY,
        _storage_root(),
        label="iterative_experiments",
    )


def download_shaxiang_data_bundle() -> bool:
    """恢复 shaxiang data/experiments.db + charts/"""
    dest = _shaxiang_data_root()
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "charts").mkdir(parents=True, exist_ok=True)
    return _download_and_extract_tar(
        SHAXIANG_DATA_OBJECT_KEY,
        dest,
        label="shaxiang_data",
    )


def _download_and_extract_tar(object_key: str, extract_root: Path, label: str) -> bool:
    import io
    import tarfile

    base_url, key = _supabase_config()
    if not base_url or not key:
        return False
    try:
        ensure_bucket(base_url, key)
        with httpx.Client(timeout=300.0) as client:
            resp = client.get(
                f"{base_url}/storage/v1/object/{BUCKET}/{object_key}",
                headers=_headers(key),
            )
            if resp.status_code == 404:
                logger.info("cloud %s bundle: not present", label)
                return False
            if resp.status_code != 200:
                logger.warning("cloud %s download failed: %s", label, resp.status_code)
                return False
            extract_root.mkdir(parents=True, exist_ok=True)
            with tarfile.open(fileobj=io.BytesIO(resp.content), mode="r:gz") as tar:
                tar.extractall(path=extract_root)
            logger.info(
                "cloud %s restored (%s bytes) -> %s",
                label,
                len(resp.content),
                extract_root,
            )
            return True
    except Exception as exc:
        logger.warning("cloud %s download error: %s", label, exc)
        return False


def upload_storage_object(object_key: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
    base_url, key = _supabase_config()
    if not base_url or not key:
        return False
    try:
        ensure_bucket(base_url, key)
        with httpx.Client(timeout=300.0) as client:
            resp = client.post(
                f"{base_url}/storage/v1/object/{BUCKET}/{object_key}",
                headers={
                    **_headers(key),
                    "Content-Type": content_type,
                    "x-upsert": "true",
                },
                content=data,
            )
            if resp.status_code not in (200, 201):
                resp = client.put(
                    f"{base_url}/storage/v1/object/{BUCKET}/{object_key}",
                    headers={
                        **_headers(key),
                        "Content-Type": content_type,
                        "x-upsert": "true",
                    },
                    content=data,
                )
            if resp.status_code not in (200, 201):
                logger.warning(
                    "upload %s failed: %s %s", object_key, resp.status_code, resp.text[:200]
                )
                return False
            logger.info("uploaded %s (%s bytes)", object_key, len(data))
            return True
    except Exception as exc:
        logger.warning("upload %s error: %s", object_key, exc)
        return False


def upload_sqlite(database_url: str) -> bool:
    path = _sqlite_path(database_url)
    if not path.is_file():
        return False
    # WAL 模式下评估等写入可能只在 -wal 文件中；上传前强制合并到主库
    try:
        import sqlite3

        con = sqlite3.connect(str(path))
        try:
            con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            con.close()
    except Exception as exc:
        logger.warning("sqlite wal_checkpoint before upload failed: %s", exc)
    if not sqlite_integrity_ok(path):
        logger.error("skip cloud sqlite upload: local database is malformed (%s)", path)
        return False
    return upload_storage_object(OBJECT_KEY, path.read_bytes())


def start_periodic_sync(database_url: str, interval_sec: int = 10800) -> None:
    """周期性上传 SQLite 到 Storage。默认 10800 秒（3 小时）。"""
    global _sync_thread
    if not cloud_sqlite_sync_enabled(database_url):
        return
    if _sync_thread and _sync_thread.is_alive():
        return

    interval = max(60, int(interval_sec or 10800))

    def _loop() -> None:
        while not _sync_stop.wait(interval):
            upload_sqlite(database_url)

    _sync_stop.clear()
    _sync_thread = threading.Thread(target=_loop, name="aisci-cloud-sqlite-sync", daemon=True)
    _sync_thread.start()
    logger.info("cloud sqlite periodic sync started (interval=%ss)", interval)


def stop_periodic_sync(database_url: str) -> None:
    _sync_stop.set()
    if cloud_sqlite_sync_enabled(database_url):
        upload_sqlite(database_url)


def database_backend_label(database_url: str) -> str:
    if database_url.startswith("postgres"):
        host = urlparse(database_url.replace("postgresql+psycopg2", "postgresql")).hostname
        return f"postgresql({host or 'unknown'})"
    if cloud_sqlite_sync_enabled(database_url):
        return "sqlite+supabase_storage"
    return "sqlite"


# 演示库报告引用清理（挑战杯展示：去掉无溯源的占位文献）
_DEMO_REF_REMOVE_NEEDLES = (
    "Federated Learning with Generative Models: A Survey",
    "FedDiff: Diffusion Models for Federated Learning",
    "Privacy-Preserving Federated Learning for Fall Detection Using Wearable Sensors",
)


def scrub_demo_report_references(database_url: str) -> int:
    """从 SQLite reports.references 中移除指定占位文献；返回删除条数。"""
    import json
    import sqlite3

    if not database_url.startswith("sqlite"):
        return 0
    path = _sqlite_path(database_url)
    if not path.is_file():
        return 0

    if not sqlite_integrity_ok(path):
        logger.error("skip scrub_demo_report_references: database malformed (%s)", path)
        return 0

    removed_total = 0
    try:
        con = sqlite3.connect(str(path))
        try:
            rows = con.execute('SELECT id, "references" FROM reports').fetchall()
            for rid, raw in rows:
                if not raw:
                    continue
                try:
                    refs = json.loads(raw)
                except Exception:
                    continue
                if not isinstance(refs, list):
                    continue
                kept = []
                removed = 0
                for item in refs:
                    text = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
                    if any(n in text for n in _DEMO_REF_REMOVE_NEEDLES):
                        removed += 1
                        continue
                    kept.append(item)
                if removed:
                    con.execute(
                        'UPDATE reports SET "references"=? WHERE id=?',
                        (json.dumps(kept, ensure_ascii=False), rid),
                    )
                    removed_total += removed
            if removed_total:
                con.commit()
        finally:
            con.close()
    except sqlite3.DatabaseError as exc:
        logger.error("scrub_demo_report_references aborted: %s", exc)
        return 0
    if removed_total:
        logger.info("scrubbed %s demo report reference(s)", removed_total)
    return removed_total


def scrub_stuck_report_quality_hints(database_url: str) -> int:
    """删除卡住的「报告内容质量问题 / 自动修复中」大家长提示。

    成因：二次报告生成新增 rg_content_quality hint 后，自动修复只更新了首条 hint，
    后续条目 fix_status 为空，前端一直显示「修复中」。
    """
    import json
    import sqlite3

    if not database_url.startswith("sqlite"):
        return 0
    path = _sqlite_path(database_url)
    if not path.is_file():
        return 0
    if not sqlite_integrity_ok(path):
        logger.error("skip scrub_stuck_report_quality_hints: database malformed (%s)", path)
        return 0

    removed = 0
    try:
        con = sqlite3.connect(str(path))
    except sqlite3.DatabaseError as exc:
        logger.error("scrub_stuck_report_quality_hints open failed: %s", exc)
        return 0
    try:
        # 1) coordinator_advice：未完成自动修复的质量问题提示
        if con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='coordinator_advice'"
        ).fetchone():
            rows = con.execute(
                "SELECT id, message, suggestion, extra_data FROM coordinator_advice "
                "WHERE advice_type='stage_check' AND suggestion='auto_fix_report'"
            ).fetchall()
            for rid, message, _suggestion, extra_raw in rows:
                msg = message or ""
                extra: dict = {}
                if extra_raw:
                    try:
                        extra = json.loads(extra_raw) if isinstance(extra_raw, str) else dict(extra_raw)
                    except Exception:
                        extra = {}
                fix_status = extra.get("fix_status")
                stuck = (
                    "报告内容存在质量问题" in msg
                    or (fix_status not in ("completed", "failed") and "质量问题" in msg)
                )
                if stuck:
                    con.execute("DELETE FROM coordinator_advice WHERE id=?", (rid,))
                    removed += 1

        # 2) pipeline_runs.output_data.coordinator_hints
        if con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='pipeline_runs'"
        ).fetchone():
            runs = con.execute("SELECT id, output_data FROM pipeline_runs").fetchall()
            for run_id, output_raw in runs:
                if not output_raw:
                    continue
                try:
                    output = json.loads(output_raw) if isinstance(output_raw, str) else output_raw
                except Exception:
                    continue
                if not isinstance(output, dict):
                    continue
                hints = output.get("coordinator_hints")
                if not isinstance(hints, list) or not hints:
                    continue
                kept = []
                changed = False
                for h in hints:
                    if not isinstance(h, dict):
                        kept.append(h)
                        continue
                    msg = str(h.get("message") or "")
                    rem = h.get("remediation") or ""
                    fix_status = h.get("fix_status")
                    stuck = rem == "auto_fix_report" and (
                        "报告内容存在质量问题" in msg
                        or (fix_status not in ("completed", "failed") and "质量问题" in msg and fix_status is None)
                    )
                    if stuck:
                        changed = True
                        removed += 1
                        continue
                    kept.append(h)
                if changed:
                    output["coordinator_hints"] = kept
                    con.execute(
                        "UPDATE pipeline_runs SET output_data=? WHERE id=?",
                        (json.dumps(output, ensure_ascii=False), run_id),
                    )

        if removed:
            con.commit()
    except sqlite3.DatabaseError as exc:
        logger.error("scrub_stuck_report_quality_hints aborted: %s", exc)
        return 0
    finally:
        con.close()
    if removed:
        logger.info("scrubbed %s stuck report-quality coordinator hint(s)", removed)
    return removed
