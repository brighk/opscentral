import logging
from typing import Any

import httpx

from opscentral_agent.config import config

logger = logging.getLogger(__name__)


class AgentClient:
    def __init__(self):
        self.base_url = config.server_url.rstrip("/")
        self.api_key = config.api_key
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"X-Agent-Key": self.api_key},
            timeout=30.0,
        )

    def send_heartbeat(self, agent_version: str, ip_address: str | None = None):
        try:
            response = self._client.post(
                "/api/v1/gateway/heartbeat",
                json={"agent_version": agent_version, "ip_address": ip_address},
            )
            response.raise_for_status()
            logger.debug("Heartbeat sent successfully")
        except httpx.HTTPError as e:
            logger.error(f"Failed to send heartbeat: {e}")

    def send_metrics(self, metrics: list[dict]):
        try:
            response = self._client.post(
                "/api/v1/gateway/metrics",
                json={"metrics": metrics},
            )
            response.raise_for_status()
            logger.info(f"Sent {len(metrics)} metrics")
        except httpx.HTTPError as e:
            logger.error(f"Failed to send metrics: {e}")

    def send_processes(self, processes: list[dict]):
        try:
            response = self._client.post(
                "/api/v1/gateway/processes",
                json={"processes": processes},
            )
            response.raise_for_status()
            logger.debug(f"Sent {len(processes)} processes")
        except httpx.HTTPError as e:
            logger.error(f"Failed to send processes: {e}")

    def send_inventory(self, system_info: dict, software: list[dict] | None = None):
        try:
            response = self._client.post(
                "/api/v1/gateway/inventory",
                json={"system_info": system_info, "software": software},
            )
            response.raise_for_status()
            logger.info("Inventory submitted successfully")
        except httpx.HTTPError as e:
            logger.error(f"Failed to send inventory: {e}")

    def poll_actions(self) -> list[dict]:
        try:
            response = self._client.get("/api/v1/gateway/actions/poll")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to poll actions: {e}")
            return []

    def report_action_result(
        self, action_id: str, status: str, result: dict | None = None, error: str | None = None
    ):
        try:
            payload: dict[str, Any] = {"status": status}
            if result is not None:
                payload["result"] = result
            if error is not None:
                payload["error"] = error

            response = self._client.post(
                f"/api/v1/gateway/actions/{action_id}/result",
                json=payload,
            )
            response.raise_for_status()
            logger.info(f"Reported result for action {action_id}: {status}")
        except httpx.HTTPError as e:
            logger.error(f"Failed to report action result: {e}")

    def close(self):
        self._client.close()
