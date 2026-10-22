import asyncio
import uuid

from app.tasks.celery_app import celery


@celery.task(name="app.tasks.runbook_tasks.execute_runbook_async")
def execute_runbook_async(execution_id: str):
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import settings
    from app.runbooks.engine import RunbookEngine

    async def _run():
        engine = create_async_engine(settings.DATABASE_URL)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as db:
            runner = RunbookEngine(db)
            await runner.execute_runbook(uuid.UUID(execution_id))
        await engine.dispose()

    asyncio.run(_run())
