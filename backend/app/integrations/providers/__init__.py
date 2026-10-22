from app.integrations.providers.base import ConnectionTestResult, IntegrationProvider
from app.integrations.providers.jira import JiraProvider
from app.integrations.providers.opsgenie import OpsGenieProvider
from app.integrations.providers.pagerduty import PagerDutyProvider
from app.integrations.providers.servicenow import ServiceNowProvider

PROVIDERS: dict[str, type[IntegrationProvider]] = {
    "pagerduty": PagerDutyProvider,
    "jira": JiraProvider,
    "opsgenie": OpsGenieProvider,
    "servicenow": ServiceNowProvider,
}

__all__ = ["PROVIDERS", "ConnectionTestResult", "IntegrationProvider"]
