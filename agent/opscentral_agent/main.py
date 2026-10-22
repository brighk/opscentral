import logging
import platform
import signal
import sys
import time

import schedule

from opscentral_agent import __version__
from opscentral_agent.client import AgentClient
from opscentral_agent.collectors import (
    collect_cpu,
    collect_disk,
    collect_memory,
    collect_network,
    collect_process_summary,
    collect_processes,
    collect_software,
    collect_system_info,
)
from opscentral_agent.config import config

logger = logging.getLogger("opscentral_agent")
running = True


def setup_logging():
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def collect_and_send_metrics(client: AgentClient):
    """Collect all metrics and send to server."""
    metrics = []
    # A failing collector only drops its own metrics, not the whole batch
    for collector in (
        collect_cpu,
        collect_memory,
        collect_disk,
        collect_network,
        collect_process_summary,
    ):
        try:
            metrics.extend(collector())
        except Exception as e:
            logger.error(f"{collector.__name__} failed: {e}")

    try:
        client.send_metrics(metrics)
        client.send_heartbeat(
            agent_version=__version__,
            ip_address=_get_primary_ip(),
        )

        # Send process list
        processes = collect_processes()
        if processes:
            client.send_processes(processes)
    except Exception as e:
        logger.error(f"Error collecting/sending metrics: {e}")


def poll_and_execute_actions(client: AgentClient):
    """Poll for remote actions and execute them."""
    if not config.enable_remote_actions:
        return

    try:
        from opscentral_agent.executor import ActionExecutor

        actions = client.poll_actions()
        if not actions:
            return

        executor = ActionExecutor()
        for action in actions:
            action_type = action.get("action_type")
            action_id = action.get("id")
            parameters = action.get("parameters")

            if not action_id:
                logger.warning(f"Ignoring action without an id: {action!r}")
                continue

            if not action_type or action_type not in config.allowed_actions:
                client.report_action_result(
                    action_id, "failed", error=f"Action type '{action_type}' is not allowed"
                )
                continue

            logger.info(f"Executing action {action_id}: {action_type}")
            result = executor.execute(action_type, parameters)
            client.report_action_result(
                action_id,
                result.get("status", "completed"),
                result=result.get("result"),
                error=result.get("error"),
            )
    except Exception as e:
        logger.error(f"Error polling/executing actions: {e}")


def collect_and_send_inventory(client: AgentClient):
    """Collect system inventory and send to server."""
    try:
        system_info = collect_system_info()
        software = collect_software()
        client.send_inventory(system_info, software)
    except Exception as e:
        logger.error(f"Error collecting/sending inventory: {e}")


def _get_primary_ip() -> str | None:
    import socket

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def signal_handler(sig, frame):
    global running
    logger.info("Shutting down agent...")
    running = False


def main():
    global running

    # Load config: file first, then env vars override
    config.load_from_file()
    config.load_from_env()
    setup_logging()

    if not config.api_key:
        logger.error("No API key configured. Set OC_API_KEY or configure agent.yml")
        sys.exit(1)

    logger.info(f"OpsCentral Agent v{__version__} starting")
    logger.info(f"Platform: {platform.system()} {platform.release()}")
    logger.info(f"Server: {config.server_url}")
    logger.info(f"Collect interval: {config.collect_interval}s")

    # Signal handling: SIGINT works on all platforms, SIGTERM only on Unix
    signal.signal(signal.SIGINT, signal_handler)
    if platform.system() != "Windows":
        signal.signal(signal.SIGTERM, signal_handler)

    client = AgentClient()

    # Initial collection
    collect_and_send_metrics(client)
    collect_and_send_inventory(client)

    # Schedule recurring tasks
    schedule.every(config.collect_interval).seconds.do(collect_and_send_metrics, client)
    schedule.every(config.inventory_interval).seconds.do(collect_and_send_inventory, client)
    if config.enable_remote_actions:
        schedule.every(config.action_poll_interval).seconds.do(poll_and_execute_actions, client)
        logger.info(f"Remote actions enabled (poll interval: {config.action_poll_interval}s)")

    while running:
        schedule.run_pending()
        time.sleep(1)

    client.close()
    logger.info("Agent stopped")


if __name__ == "__main__":
    main()
