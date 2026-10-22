import uuid

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Asset(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "assets"

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("agents.id"), nullable=True, unique=True
    )
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), default="server")
    os_type: Mapped[str | None] = mapped_column(String(50))
    os_version: Mapped[str | None] = mapped_column(String(100))
    cpu_model: Mapped[str | None] = mapped_column(String(200))
    cpu_cores: Mapped[int | None] = mapped_column(Integer)
    ram_total_gb: Mapped[float | None] = mapped_column(Float)
    disk_total_gb: Mapped[float | None] = mapped_column(Float)
    ip_addresses: Mapped[list | None] = mapped_column(JSON)
    mac_addresses: Mapped[list | None] = mapped_column(JSON)
    system_info: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="active")

    software: Mapped[list["SoftwareInventory"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )


class SoftwareInventory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "software_inventory"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("assets.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str | None] = mapped_column(String(100))
    publisher: Mapped[str | None] = mapped_column(String(255))

    asset: Mapped["Asset"] = relationship(back_populates="software")
