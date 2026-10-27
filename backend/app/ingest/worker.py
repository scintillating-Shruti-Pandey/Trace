import asyncio
import logging

from arq.connections import RedisSettings

from app.config import Settings
from app.corpus import register
from app.db import make_engine, session_factory
from app.schemas import AssetCreate
from app.stores.blob import BlobStore

logger = logging.getLogger(__name__)


async def startup(ctx):
    settings = Settings()
    ctx["settings"] = settings
    ctx["engine"] = make_engine(settings)
    ctx["sessions"] = session_factory(ctx["engine"])
    ctx["blobs"] = BlobStore(settings)


async def shutdown(ctx):
    ctx["engine"].dispose()


async def ingest_asset(ctx, manifest: dict):
    def work():
        with ctx["sessions"].begin() as session:
            return register(
                session, AssetCreate.model_validate(manifest), ctx["settings"], ctx["blobs"]
            )

    try:
        result = await asyncio.to_thread(work)
        return {**result, "next_step": "annotation; model processing is not implemented yet"}
    except ValueError as exc:
        return {"status": "failed", "error": str(exc)}
    except Exception:
        logger.exception("Asset registration failed")
        return {"status": "failed", "error": "Registration failed; inspect worker logs"}


class WorkerSettings:
    functions = [ingest_asset]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(Settings().redis_url)
    max_jobs = 2
    job_timeout = 1800
    keep_result = 7 * 24 * 3600
