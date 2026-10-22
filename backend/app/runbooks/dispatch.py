import logging
import uuid

logger = logging.getLogger(__name__)


class QueueUnavailableError(Exception):
    pass


async def dispatch_execution(execution_id: uuid.UUID) -> None:
    """Hand an approved execution to a Celery worker.

    Runbooks can wait minutes on agents, so they never run inside the request.
    Tests replace this function to run the engine inline.
    """
    from app.tasks.runbook_tasks import execute_runbook_async

    try:
        execute_runbook_async.delay(str(execution_id))
    except Exception as e:
        logger.exception(f"Could not queue runbook execution {execution_id}")
        raise QueueUnavailableError(str(e)) from e
