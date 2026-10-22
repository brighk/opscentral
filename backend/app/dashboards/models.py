import uuid

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class CustomDashboard(Base, UUIDMixin, TimestampMixin):
    """A user-created custom dashboard."""

    __tablename__ = "custom_dashboards"

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    layout: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # layout stores grid positions: [{"widget_id": "uuid", "x": 0, "y": 0, "w": 6, "h": 4}]

    widgets: Mapped[list["DashboardWidget"]] = relationship(
        back_populates="dashboard", cascade="all, delete-orphan"
    )


class DashboardWidget(Base, UUIDMixin, TimestampMixin):
    """A widget on a custom dashboard."""

    __tablename__ = "dashboard_widgets"

    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("custom_dashboards.id", ondelete="CASCADE"), nullable=False
    )
    widget_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Types: metric_chart, status_card, alert_feed, asset_summary,
    #        process_list, health_check_status, vuln_summary
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # config varies by type:
    #   metric_chart: {"metric_name": "cpu_percent", "agent_id": null, "time_range": "1h"}
    #   status_card: {"metric_name": "memory_percent", "agent_id": "uuid"}
    #   alert_feed: {"severity": "critical", "limit": 10}
    #   asset_summary: {}
    #   process_list: {"agent_id": "uuid", "limit": 10}
    #   health_check_status: {}
    #   vuln_summary: {}
    position_x: Mapped[int] = mapped_column(Integer, default=0)
    position_y: Mapped[int] = mapped_column(Integer, default=0)
    width: Mapped[int] = mapped_column(Integer, default=6)  # out of 12 grid columns
    height: Mapped[int] = mapped_column(Integer, default=4)  # grid rows

    dashboard: Mapped["CustomDashboard"] = relationship(back_populates="widgets")
