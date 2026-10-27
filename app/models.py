import reflex as rx

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class AuditColumns:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ClientOrganization(AuditColumns, Base):
    __tablename__ = "client_organization"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'suspended', 'archived')", name="status"
        ),
        CheckConstraint("preferred_language IN ('es', 'en')", name="language"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str | None] = mapped_column(String(40), unique=True)
    legal_name: Mapped[str] = mapped_column(
        String(200), default="", server_default=""
    )
    display_name: Mapped[str] = mapped_column(
        String(160), default="", server_default=""
    )
    tax_identifier: Mapped[str | None] = mapped_column(String(80))
    contact_name: Mapped[str | None] = mapped_column(String(160))
    contact_email: Mapped[str | None] = mapped_column(String(254))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    billing_address: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str] = mapped_column(
        String(2), default="MX", server_default="MX"
    )
    timezone: Mapped[str] = mapped_column(
        String(80),
        default="America/Mexico_City",
        server_default="America/Mexico_City",
    )
    currency: Mapped[str] = mapped_column(
        String(3), default="MXN", server_default="MXN"
    )
    preferred_language: Mapped[str] = mapped_column(
        String(2), default="es", server_default="es"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active"
    )

    fleets: Mapped[list["Fleet"]] = relationship(
        back_populates="client", passive_deletes=True
    )
    users: Mapped[list["AppUser"]] = relationship(
        back_populates="client", passive_deletes=True
    )


class AppUser(AuditColumns, Base):
    __tablename__ = "app_user"
    __table_args__ = (
        CheckConstraint(
            "email IS NOT NULL AND email = lower(trim(email)) AND length(email) > 3",
            name="normalized_email",
        ),
        CheckConstraint(
            "password_hash IS NOT NULL AND length(password_hash) > 0",
            name="password_hash_present",
        ),
        CheckConstraint(
            "(role = 'admin' AND client_id IS NULL) OR (role = 'client' AND client_id IS NOT NULL)",
            name="role_client_scope",
        ),
        CheckConstraint("preferred_language IN ('es', 'en')", name="language"),
        CheckConstraint("preferred_theme IN ('light', 'dark')", name="theme"),
        CheckConstraint("failed_login_attempts >= 0", name="login_attempts"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey("client_organization.id", ondelete="RESTRICT"), index=True
    )
    email: Mapped[str | None] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    password_algorithm: Mapped[str] = mapped_column(
        String(40), default="argon2id", server_default="argon2id"
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    display_name: Mapped[str] = mapped_column(
        String(160), default="", server_default=""
    )
    role: Mapped[str] = mapped_column(
        String(20), default="client", server_default="client"
    )
    is_active: Mapped[bool] = mapped_column(
        default=True, server_default=text("true")
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    failed_login_attempts: Mapped[int] = mapped_column(
        default=0, server_default="0"
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    preferred_language: Mapped[str] = mapped_column(
        String(2), default="es", server_default="es"
    )
    preferred_theme: Mapped[str] = mapped_column(
        String(10), default="light", server_default="light"
    )

    client: Mapped["ClientOrganization | None"] = relationship(
        back_populates="users"
    )


class Fleet(AuditColumns, Base):
    __tablename__ = "fleet"
    __table_args__ = (
        CheckConstraint("client_id IS NOT NULL", name="client_required"),
        UniqueConstraint("client_id", "code"),
        CheckConstraint(
            "status IN ('active', 'inactive', 'archived')", name="status"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey("client_organization.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str | None] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(
        String(160), default="", server_default=""
    )
    operating_region: Mapped[str | None] = mapped_column(String(160))
    depot_name: Mapped[str | None] = mapped_column(String(160))
    depot_address: Mapped[str | None] = mapped_column(Text)
    manager_name: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active"
    )
    notes: Mapped[str | None] = mapped_column(Text)

    client: Mapped["ClientOrganization"] = relationship(back_populates="fleets")
    units: Mapped[list["Unit"]] = relationship(
        back_populates="fleet", passive_deletes=True
    )


class Unit(AuditColumns, Base):
    __tablename__ = "unit"
    __table_args__ = (
        CheckConstraint("fleet_id IS NOT NULL", name="fleet_required"),
        UniqueConstraint("fleet_id", "unit_number"),
        CheckConstraint(
            "status IN ('active', 'in_service', 'out_of_service', 'retired')",
            name="status",
        ),
        CheckConstraint("odometer_km >= 0 AND engine_hours >= 0", name="usage"),
        CheckConstraint(
            "model_year IS NULL OR model_year BETWEEN 1900 AND 2200",
            name="model_year",
        ),
        CheckConstraint(
            "purchase_cost IS NULL OR purchase_cost >= 0", name="purchase_cost"
        ),
        CheckConstraint(
            "gross_vehicle_weight_kg IS NULL OR gross_vehicle_weight_kg > 0",
            name="weight",
        ),
        CheckConstraint(
            "retired_on IS NULL OR commissioned_on IS NULL OR retired_on >= commissioned_on",
            name="lifecycle_dates",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fleet_id: Mapped[int | None] = mapped_column(
        ForeignKey("fleet.id", ondelete="RESTRICT"), index=True
    )
    unit_number: Mapped[str | None] = mapped_column(String(60))
    vin: Mapped[str | None] = mapped_column(String(17), unique=True)
    registration_plate: Mapped[str | None] = mapped_column(String(30))
    manufacturer: Mapped[str] = mapped_column(
        String(80), default="Daimler", server_default="Daimler"
    )
    model: Mapped[str] = mapped_column(
        String(100), default="", server_default=""
    )
    model_year: Mapped[int | None]
    vehicle_type: Mapped[str] = mapped_column(
        String(40), default="truck", server_default="truck"
    )
    fuel_type: Mapped[str] = mapped_column(
        String(30), default="diesel", server_default="diesel"
    )
    engine_model: Mapped[str | None] = mapped_column(String(100))
    engine_serial: Mapped[str | None] = mapped_column(String(100))
    transmission_model: Mapped[str | None] = mapped_column(String(100))
    gross_vehicle_weight_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2)
    )
    purchased_on: Mapped[date | None]
    commissioned_on: Mapped[date | None]
    retired_on: Mapped[date | None]
    purchase_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(
        String(3), default="MXN", server_default="MXN"
    )
    odometer_km: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default="0"
    )
    engine_hours: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default="0"
    )
    usage_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    duty_cycle: Mapped[str] = mapped_column(
        String(40), default="mixed", server_default="mixed"
    )
    typical_route: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(
        String(30), default="active", server_default="active"
    )
    notes: Mapped[str | None] = mapped_column(Text)

    fleet: Mapped["Fleet"] = relationship(back_populates="units")
    telemetry_snapshots: Mapped[list["TelemetrySnapshot"]] = relationship(
        back_populates="unit", passive_deletes=True
    )
    faults: Mapped[list["UnitFault"]] = relationship(
        back_populates="unit", passive_deletes=True
    )
    service_history: Mapped[list["ServiceRecord"]] = relationship(
        back_populates="unit", passive_deletes=True
    )
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="unit", passive_deletes=True
    )
    predictions: Mapped[list["ComponentPrediction"]] = relationship(
        back_populates="unit", passive_deletes=True
    )
    warranties: Mapped[list["WarrantyContract"]] = relationship(
        back_populates="unit", passive_deletes=True
    )
    claims: Mapped[list["WarrantyClaim"]] = relationship(
        back_populates="unit", passive_deletes=True
    )
    service_orders: Mapped[list["ServiceOrder"]] = relationship(
        back_populates="unit", passive_deletes=True
    )


class TelemetrySnapshot(Base):
    __tablename__ = "telemetry_snapshot"
    __table_args__ = (
        CheckConstraint("unit_id IS NOT NULL", name="unit_required"),
        UniqueConstraint("unit_id", "id"),
        UniqueConstraint("unit_id", "source", "source_record_id"),
        Index("ix_telemetry_unit_observed", "unit_id", "observed_at"),
        CheckConstraint(
            "odometer_km >= 0 AND engine_hours >= 0 AND distance_km >= 0 AND driving_hours >= 0",
            name="usage",
        ),
        CheckConstraint(
            "idle_percent BETWEEN 0 AND 100 AND urban_percent BETWEEN 0 AND 100 AND highway_percent BETWEEN 0 AND 100 AND urban_percent + highway_percent <= 100",
            name="driving_percentages",
        ),
        CheckConstraint(
            "harsh_braking_events >= 0 AND harsh_acceleration_events >= 0 AND overspeed_events >= 0",
            name="driving_events",
        ),
        CheckConstraint(
            "average_speed_kph >= 0 AND max_speed_kph >= average_speed_kph",
            name="speed",
        ),
        CheckConstraint(
            "fuel_consumed_liters IS NULL OR fuel_consumed_liters >= 0",
            name="fuel",
        ),
        CheckConstraint(
            "battery_voltage IS NULL OR battery_voltage >= 0", name="voltage"
        ),
        CheckConstraint(
            "load_percent IS NULL OR load_percent BETWEEN 0 AND 100",
            name="load",
        ),
        CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90", name="latitude"
        ),
        CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180",
            name="longitude",
        ),
        CheckConstraint(
            "window_started_at IS NULL OR window_started_at <= observed_at",
            name="window",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("unit.id", ondelete="RESTRICT")
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    window_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    source: Mapped[str] = mapped_column(
        String(60), default="synthetic", server_default="synthetic"
    )
    source_record_id: Mapped[str | None] = mapped_column(String(160))
    is_synthetic: Mapped[bool] = mapped_column(
        default=True, server_default=text("true")
    )
    generator_version: Mapped[str | None] = mapped_column(String(100))
    quality_status: Mapped[str] = mapped_column(
        String(30), default="unvalidated", server_default="unvalidated"
    )
    odometer_km: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default="0"
    )
    engine_hours: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default="0"
    )
    distance_km: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0"
    )
    driving_hours: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0"), server_default="0"
    )
    average_speed_kph: Mapped[Decimal] = mapped_column(
        Numeric(7, 2), default=Decimal("0"), server_default="0"
    )
    max_speed_kph: Mapped[Decimal] = mapped_column(
        Numeric(7, 2), default=Decimal("0"), server_default="0"
    )
    idle_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0"), server_default="0"
    )
    urban_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0"), server_default="0"
    )
    highway_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0"), server_default="0"
    )
    harsh_braking_events: Mapped[int] = mapped_column(
        default=0, server_default="0"
    )
    harsh_acceleration_events: Mapped[int] = mapped_column(
        default=0, server_default="0"
    )
    overspeed_events: Mapped[int] = mapped_column(default=0, server_default="0")
    fuel_consumed_liters: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    coolant_temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    oil_temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    oil_pressure_kpa: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    battery_voltage: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    brake_wear_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        CheckConstraint(
            "brake_wear_percent BETWEEN 0 AND 100", name="brake_wear"
        ),
    )
    tire_pressure_kpa: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    load_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    ambient_temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))

    unit: Mapped["Unit"] = relationship(back_populates="telemetry_snapshots")
    faults: Mapped[list["UnitFault"]] = relationship(
        back_populates="telemetry",
        foreign_keys="UnitFault.telemetry_snapshot_id",
        passive_deletes=True,
    )
    predictions: Mapped[list["ComponentPrediction"]] = relationship(
        back_populates="telemetry",
        foreign_keys="ComponentPrediction.telemetry_snapshot_id",
        passive_deletes=True,
    )


class DTCCode(Base):
    __tablename__ = "dtc_code"
    __table_args__ = (
        UniqueConstraint("standard", "code", "manufacturer"),
        CheckConstraint(
            "severity IN ('info', 'warning', 'critical')", name="severity"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    standard: Mapped[str] = mapped_column(
        String(30), default="J1939", server_default="J1939"
    )
    code: Mapped[str | None] = mapped_column(String(60))
    manufacturer: Mapped[str] = mapped_column(
        String(80), default="generic", server_default="generic"
    )
    spn: Mapped[int | None]
    fmi: Mapped[int | None]
    system: Mapped[str] = mapped_column(
        String(60), default="engine", server_default="engine"
    )
    component_code: Mapped[str | None] = mapped_column(String(80))
    description_es: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    description_en: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    severity: Mapped[str] = mapped_column(
        String(20), default="warning", server_default="warning"
    )
    recommended_action_es: Mapped[str | None] = mapped_column(Text)
    recommended_action_en: Mapped[str | None] = mapped_column(Text)

    occurrences: Mapped[list["UnitFault"]] = relationship(
        back_populates="dtc", passive_deletes=True
    )


class UnitFault(AuditColumns, Base):
    __tablename__ = "unit_fault"
    __table_args__ = (
        CheckConstraint(
            "unit_id IS NOT NULL AND dtc_code_id IS NOT NULL",
            name="ownership_and_code",
        ),
        ForeignKeyConstraint(
            ["unit_id", "telemetry_snapshot_id"],
            ["telemetry_snapshot.unit_id", "telemetry_snapshot.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_fault_unit_status", "unit_id", "status"),
        CheckConstraint(
            "status IN ('active', 'intermittent', 'cleared')", name="status"
        ),
        CheckConstraint("occurrence_count >= 1", name="occurrences"),
        CheckConstraint(
            "last_seen_at >= first_seen_at AND (cleared_at IS NULL OR cleared_at >= first_seen_at)",
            name="dates",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("unit.id", ondelete="RESTRICT")
    )
    dtc_code_id: Mapped[int | None] = mapped_column(
        ForeignKey("dtc_code.id", ondelete="RESTRICT"), index=True
    )
    telemetry_snapshot_id: Mapped[int | None] = mapped_column(index=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active"
    )
    occurrence_count: Mapped[int] = mapped_column(default=1, server_default="1")
    odometer_km: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    engine_hours: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    source: Mapped[str] = mapped_column(
        String(60), default="telemetry", server_default="telemetry"
    )
    notes: Mapped[str | None] = mapped_column(Text)

    unit: Mapped["Unit"] = relationship(back_populates="faults")
    dtc: Mapped["DTCCode"] = relationship(back_populates="occurrences")
    telemetry: Mapped["TelemetrySnapshot | None"] = relationship(
        back_populates="faults", foreign_keys=[telemetry_snapshot_id]
    )


class ComponentPrediction(Base):
    __tablename__ = "component_prediction"
    __table_args__ = (
        CheckConstraint("unit_id IS NOT NULL", name="unit_required"),
        UniqueConstraint("unit_id", "id"),
        ForeignKeyConstraint(
            ["unit_id", "telemetry_snapshot_id"],
            ["telemetry_snapshot.unit_id", "telemetry_snapshot.id"],
            ondelete="RESTRICT",
        ),
        Index(
            "ix_prediction_unit_component_date",
            "unit_id",
            "component_code",
            "predicted_at",
        ),
        CheckConstraint(
            "failure_probability_30d BETWEEN 0 AND 1 AND failure_probability_90d BETWEEN 0 AND 1 AND failure_probability_90d >= failure_probability_30d",
            name="probabilities",
        ),
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name="confidence",
        ),
        CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name="risk_level",
        ),
        CheckConstraint(
            "estimated_repair_cost IS NULL OR estimated_repair_cost >= 0",
            name="repair_cost",
        ),
        CheckConstraint(
            "estimated_downtime_hours IS NULL OR estimated_downtime_hours >= 0",
            name="downtime",
        ),
        CheckConstraint(
            "remaining_useful_life_km IS NULL OR remaining_useful_life_km >= 0",
            name="remaining_km",
        ),
        CheckConstraint(
            "remaining_useful_life_hours IS NULL OR remaining_useful_life_hours >= 0",
            name="remaining_hours",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_until >= predicted_at",
            name="validity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("unit.id", ondelete="RESTRICT")
    )
    telemetry_snapshot_id: Mapped[int | None] = mapped_column(index=True)
    system: Mapped[str] = mapped_column(
        String(60), default="engine", server_default="engine"
    )
    component_code: Mapped[str] = mapped_column(
        String(80), default="", server_default=""
    )
    predicted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    failure_probability_30d: Mapped[Decimal] = mapped_column(
        Numeric(7, 6), default=Decimal("0"), server_default="0"
    )
    failure_probability_90d: Mapped[Decimal] = mapped_column(
        Numeric(7, 6), default=Decimal("0"), server_default="0"
    )
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(7, 6))
    risk_level: Mapped[str] = mapped_column(
        String(20), default="low", server_default="low"
    )
    remaining_useful_life_km: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2)
    )
    remaining_useful_life_hours: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2)
    )
    odometer_km: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    engine_hours: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    model_name: Mapped[str] = mapped_column(
        String(120), default="", server_default=""
    )
    model_version: Mapped[str] = mapped_column(
        String(80), default="", server_default=""
    )
    model_artifact_sha256: Mapped[str | None] = mapped_column(String(64))
    training_dataset_version: Mapped[str | None] = mapped_column(String(120))
    training_data_is_synthetic: Mapped[bool] = mapped_column(
        default=True, server_default=text("true")
    )
    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    feature_schema_version: Mapped[str | None] = mapped_column(String(80))
    inference_run_id: Mapped[str | None] = mapped_column(String(100))
    explanation_es: Mapped[str | None] = mapped_column(Text)
    explanation_en: Mapped[str | None] = mapped_column(Text)
    recommended_action_es: Mapped[str | None] = mapped_column(Text)
    recommended_action_en: Mapped[str | None] = mapped_column(Text)
    recommended_by: Mapped[date | None]
    estimated_repair_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2)
    )
    estimated_downtime_hours: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2)
    )
    currency: Mapped[str] = mapped_column(
        String(3), default="MXN", server_default="MXN"
    )

    unit: Mapped["Unit"] = relationship(back_populates="predictions")
    telemetry: Mapped["TelemetrySnapshot | None"] = relationship(
        back_populates="predictions", foreign_keys=[telemetry_snapshot_id]
    )
    service_orders: Mapped[list["ServiceOrder"]] = relationship(
        back_populates="prediction",
        foreign_keys="ServiceOrder.prediction_id",
        passive_deletes=True,
    )


class WarrantyContract(AuditColumns, Base):
    __tablename__ = "warranty_contract"
    __table_args__ = (
        CheckConstraint("unit_id IS NOT NULL", name="unit_required"),
        UniqueConstraint("unit_id", "id"),
        UniqueConstraint("unit_id", "contract_number"),
        CheckConstraint(
            "status IN ('pending', 'active', 'expired', 'void', 'cancelled')",
            name="status",
        ),
        CheckConstraint(
            "ends_on IS NULL OR starts_on IS NULL OR ends_on >= starts_on",
            name="dates",
        ),
        CheckConstraint(
            "mileage_limit_km IS NULL OR mileage_limit_km >= 0",
            name="mileage_limit",
        ),
        CheckConstraint(
            "engine_hours_limit IS NULL OR engine_hours_limit >= 0",
            name="hours_limit",
        ),
        CheckConstraint(
            "deductible >= 0 AND (total_claim_limit IS NULL OR total_claim_limit >= 0)",
            name="cost_limits",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("unit.id", ondelete="RESTRICT"), index=True
    )
    contract_number: Mapped[str | None] = mapped_column(String(100))
    provider_name: Mapped[str] = mapped_column(
        String(160), default="", server_default=""
    )
    contract_type: Mapped[str] = mapped_column(
        String(40), default="manufacturer", server_default="manufacturer"
    )
    starts_on: Mapped[date | None]
    ends_on: Mapped[date | None]
    starting_odometer_km: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    mileage_limit_km: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    starting_engine_hours: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2)
    )
    engine_hours_limit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    deductible: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default="0"
    )
    total_claim_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(
        String(3), default="MXN", server_default="MXN"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending"
    )
    terms: Mapped[str | None] = mapped_column(Text)
    exclusions: Mapped[str | None] = mapped_column(Text)
    document_storage_key: Mapped[str | None] = mapped_column(Text)

    unit: Mapped["Unit"] = relationship(back_populates="warranties")
    coverage: Mapped[list["WarrantyCoverage"]] = relationship(
        back_populates="contract", passive_deletes=True
    )
    claims: Mapped[list["WarrantyClaim"]] = relationship(
        back_populates="contract",
        foreign_keys="WarrantyClaim.warranty_contract_id",
        passive_deletes=True,
    )


class WarrantyCoverage(AuditColumns, Base):
    __tablename__ = "warranty_coverage"
    __table_args__ = (
        CheckConstraint(
            "warranty_contract_id IS NOT NULL", name="contract_required"
        ),
        UniqueConstraint("warranty_contract_id", "id"),
        UniqueConstraint("warranty_contract_id", "component_code"),
        CheckConstraint(
            "parts_coverage_percent BETWEEN 0 AND 100 AND labor_coverage_percent BETWEEN 0 AND 100",
            name="coverage_percentages",
        ),
        CheckConstraint(
            "claim_limit IS NULL OR claim_limit >= 0", name="claim_limit"
        ),
        CheckConstraint(
            "deductible IS NULL OR deductible >= 0", name="deductible"
        ),
        CheckConstraint(
            "ends_on IS NULL OR starts_on IS NULL OR ends_on >= starts_on",
            name="dates",
        ),
        CheckConstraint(
            "mileage_limit_km IS NULL OR mileage_limit_km >= 0",
            name="mileage_limit",
        ),
        CheckConstraint(
            "engine_hours_limit IS NULL OR engine_hours_limit >= 0",
            name="hours_limit",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    warranty_contract_id: Mapped[int | None] = mapped_column(
        ForeignKey("warranty_contract.id", ondelete="RESTRICT"), index=True
    )
    system: Mapped[str] = mapped_column(
        String(60), default="engine", server_default="engine"
    )
    component_code: Mapped[str | None] = mapped_column(String(80))
    starts_on: Mapped[date | None]
    ends_on: Mapped[date | None]
    mileage_limit_km: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    engine_hours_limit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    parts_coverage_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("100"), server_default="100"
    )
    labor_coverage_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("100"), server_default="100"
    )
    deductible: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    claim_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    requires_preapproval: Mapped[bool] = mapped_column(
        default=False, server_default=text("false")
    )
    maintenance_requirements: Mapped[str | None] = mapped_column(Text)
    exclusions: Mapped[str | None] = mapped_column(Text)

    contract: Mapped["WarrantyContract"] = relationship(
        back_populates="coverage"
    )
    claims: Mapped[list["WarrantyClaim"]] = relationship(
        back_populates="coverage",
        foreign_keys="WarrantyClaim.warranty_coverage_id",
        passive_deletes=True,
    )


class ServiceOrder(AuditColumns, Base):
    __tablename__ = "service_order"
    __table_args__ = (
        CheckConstraint("unit_id IS NOT NULL", name="unit_required"),
        UniqueConstraint("unit_id", "id"),
        UniqueConstraint("unit_id", "order_number"),
        ForeignKeyConstraint(
            ["unit_id", "prediction_id"],
            ["component_prediction.unit_id", "component_prediction.id"],
            ondelete="RESTRICT",
        ),
        Index(
            "ix_order_unit_status_schedule",
            "unit_id",
            "status",
            "scheduled_start_at",
        ),
        CheckConstraint(
            "status IN ('draft', 'scheduled', 'in_progress', 'awaiting_parts', 'completed', 'cancelled')",
            name="status",
        ),
        CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'critical')", name="priority"
        ),
        CheckConstraint(
            "progress_percent BETWEEN 0 AND 100 AND (status <> 'completed' OR progress_percent = 100)",
            name="progress",
        ),
        CheckConstraint(
            "estimated_labor_cost >= 0 AND estimated_parts_cost >= 0 AND estimated_other_cost >= 0 AND actual_labor_cost >= 0 AND actual_parts_cost >= 0 AND actual_other_cost >= 0",
            name="costs",
        ),
        CheckConstraint(
            "estimated_downtime_hours >= 0 AND actual_downtime_hours >= 0",
            name="downtime",
        ),
        CheckConstraint(
            "scheduled_end_at IS NULL OR scheduled_start_at IS NULL OR scheduled_end_at >= scheduled_start_at",
            name="schedule",
        ),
        CheckConstraint(
            "completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at",
            name="actual_dates",
        ),
        CheckConstraint(
            "status <> 'completed' OR completed_at IS NOT NULL",
            name="completion_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("unit.id", ondelete="RESTRICT")
    )
    prediction_id: Mapped[int | None] = mapped_column(index=True)
    order_number: Mapped[str | None] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(
        String(200), default="", server_default=""
    )
    description: Mapped[str | None] = mapped_column(Text)
    service_type: Mapped[str] = mapped_column(
        String(40), default="preventive", server_default="preventive"
    )
    component_code: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(
        String(30), default="draft", server_default="draft"
    )
    priority: Mapped[str] = mapped_column(
        String(20), default="normal", server_default="normal"
    )
    progress_percent: Mapped[int] = mapped_column(default=0, server_default="0")
    current_step: Mapped[str | None] = mapped_column(String(160))
    progress_notes: Mapped[str | None] = mapped_column(Text)
    progress_saved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    workshop_name: Mapped[str | None] = mapped_column(String(160))
    assigned_technician: Mapped[str | None] = mapped_column(String(160))
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    due_on: Mapped[date | None]
    scheduled_start_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    scheduled_end_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    odometer_km: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    engine_hours: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    estimated_labor_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default="0"
    )
    estimated_parts_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default="0"
    )
    estimated_other_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default="0"
    )
    actual_labor_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default="0"
    )
    actual_parts_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default="0"
    )
    actual_other_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default="0"
    )
    currency: Mapped[str] = mapped_column(
        String(3), default="MXN", server_default="MXN"
    )
    estimated_downtime_hours: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0"), server_default="0"
    )
    actual_downtime_hours: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0"), server_default="0"
    )
    warranty_eligibility: Mapped[str] = mapped_column(
        String(30), default="unchecked", server_default="unchecked"
    )
    warranty_review_notes: Mapped[str | None] = mapped_column(Text)

    unit: Mapped["Unit"] = relationship(back_populates="service_orders")
    prediction: Mapped["ComponentPrediction | None"] = relationship(
        back_populates="service_orders", foreign_keys=[prediction_id]
    )
    parts: Mapped[list["OrderPart"]] = relationship(
        back_populates="order", passive_deletes=True
    )
    service_records: Mapped[list["ServiceRecord"]] = relationship(
        back_populates="order",
        foreign_keys="ServiceRecord.service_order_id",
        passive_deletes=True,
    )
    claims: Mapped[list["WarrantyClaim"]] = relationship(
        back_populates="order",
        foreign_keys="WarrantyClaim.service_order_id",
        passive_deletes=True,
    )
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="order",
        foreign_keys="Evidence.service_order_id",
        passive_deletes=True,
    )


class OrderPart(AuditColumns, Base):
    __tablename__ = "order_part"
    __table_args__ = (
        CheckConstraint("service_order_id IS NOT NULL", name="order_required"),
        UniqueConstraint("service_order_id", "line_number"),
        CheckConstraint("line_number >= 1", name="line_number"),
        CheckConstraint(
            "quantity_required > 0 AND quantity_ordered >= 0 AND quantity_received >= 0 AND quantity_installed >= 0 AND quantity_installed <= quantity_received",
            name="quantities",
        ),
        CheckConstraint(
            "estimated_unit_cost >= 0 AND (actual_unit_cost IS NULL OR actual_unit_cost >= 0)",
            name="costs",
        ),
        CheckConstraint(
            "status IN ('needed', 'ordered', 'partially_received', 'received', 'installed', 'cancelled')",
            name="status",
        ),
        CheckConstraint(
            "received_at IS NULL OR ordered_at IS NULL OR received_at >= ordered_at",
            name="receipt_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    service_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("service_order.id", ondelete="RESTRICT"), index=True
    )
    line_number: Mapped[int] = mapped_column(default=1, server_default="1")
    part_number: Mapped[str] = mapped_column(
        String(100), default="", server_default=""
    )
    description: Mapped[str] = mapped_column(
        String(200), default="", server_default=""
    )
    component_code: Mapped[str | None] = mapped_column(String(80))
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    supplier_name: Mapped[str | None] = mapped_column(String(160))
    supplier_order_reference: Mapped[str | None] = mapped_column(String(100))
    quantity_required: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), default=Decimal("1"), server_default="1"
    )
    quantity_ordered: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), default=Decimal("0"), server_default="0"
    )
    quantity_received: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), default=Decimal("0"), server_default="0"
    )
    quantity_installed: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), default=Decimal("0"), server_default="0"
    )
    unit_of_measure: Mapped[str] = mapped_column(
        String(20), default="each", server_default="each"
    )
    estimated_unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default="0"
    )
    actual_unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(
        String(30), default="needed", server_default="needed"
    )
    ordered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expected_on: Mapped[date | None]
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    installed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    warranty_covered: Mapped[bool | None]
    notes: Mapped[str | None] = mapped_column(Text)

    order: Mapped["ServiceOrder"] = relationship(back_populates="parts")


class ServiceRecord(AuditColumns, Base):
    __tablename__ = "service_record"
    __table_args__ = (
        CheckConstraint("unit_id IS NOT NULL", name="unit_required"),
        UniqueConstraint("unit_id", "id"),
        ForeignKeyConstraint(
            ["unit_id", "service_order_id"],
            ["service_order.unit_id", "service_order.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_service_unit_performed", "unit_id", "performed_at"),
        CheckConstraint(
            "odometer_km >= 0 AND engine_hours >= 0 AND labor_hours >= 0 AND downtime_hours >= 0",
            name="usage",
        ),
        CheckConstraint(
            "labor_cost >= 0 AND parts_cost >= 0 AND other_cost >= 0",
            name="costs",
        ),
        CheckConstraint(
            "status IN ('completed', 'verified', 'void')", name="status"
        ),
        CheckConstraint(
            "next_service_odometer_km IS NULL OR next_service_odometer_km >= odometer_km",
            name="next_mileage",
        ),
        CheckConstraint(
            "next_service_engine_hours IS NULL OR next_service_engine_hours >= engine_hours",
            name="next_hours",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("unit.id", ondelete="RESTRICT")
    )
    service_order_id: Mapped[int | None] = mapped_column(index=True)
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    service_type: Mapped[str] = mapped_column(
        String(40), default="preventive", server_default="preventive"
    )
    system: Mapped[str | None] = mapped_column(String(60))
    component_code: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    findings: Mapped[str | None] = mapped_column(Text)
    work_performed: Mapped[str | None] = mapped_column(Text)
    technician_name: Mapped[str | None] = mapped_column(String(160))
    workshop_name: Mapped[str | None] = mapped_column(String(160))
    invoice_reference: Mapped[str | None] = mapped_column(String(100))
    odometer_km: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default="0"
    )
    engine_hours: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0"
    )
    labor_hours: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0"), server_default="0"
    )
    downtime_hours: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0"), server_default="0"
    )
    labor_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default="0"
    )
    parts_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default="0"
    )
    other_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default="0"
    )
    currency: Mapped[str] = mapped_column(
        String(3), default="MXN", server_default="MXN"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="completed", server_default="completed"
    )
    next_service_on: Mapped[date | None]
    next_service_odometer_km: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2)
    )
    next_service_engine_hours: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2)
    )

    unit: Mapped["Unit"] = relationship(back_populates="service_history")
    order: Mapped["ServiceOrder | None"] = relationship(
        back_populates="service_records", foreign_keys=[service_order_id]
    )
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="service_record",
        foreign_keys="Evidence.service_record_id",
        passive_deletes=True,
    )
    claims: Mapped[list["WarrantyClaim"]] = relationship(
        back_populates="service_record",
        foreign_keys="WarrantyClaim.service_record_id",
        passive_deletes=True,
    )


class WarrantyClaim(AuditColumns, Base):
    __tablename__ = "warranty_claim"
    __table_args__ = (
        CheckConstraint(
            "unit_id IS NOT NULL AND warranty_contract_id IS NOT NULL",
            name="unit_and_contract_required",
        ),
        UniqueConstraint("unit_id", "id"),
        UniqueConstraint("warranty_contract_id", "claim_number"),
        ForeignKeyConstraint(
            ["unit_id", "warranty_contract_id"],
            ["warranty_contract.unit_id", "warranty_contract.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["warranty_contract_id", "warranty_coverage_id"],
            ["warranty_coverage.warranty_contract_id", "warranty_coverage.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["unit_id", "service_order_id"],
            ["service_order.unit_id", "service_order.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["unit_id", "service_record_id"],
            ["service_record.unit_id", "service_record.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_claim_unit_status", "unit_id", "status"),
        CheckConstraint(
            "status IN ('draft', 'submitted', 'under_review', 'approved', 'partially_approved', 'rejected', 'paid', 'withdrawn')",
            name="status",
        ),
        CheckConstraint(
            "requested_amount >= 0 AND approved_amount >= 0 AND paid_amount >= 0 AND deductible_amount >= 0 AND approved_amount <= requested_amount AND paid_amount <= approved_amount",
            name="amounts",
        ),
        CheckConstraint(
            "decided_at IS NULL OR submitted_at IS NULL OR decided_at >= submitted_at",
            name="decision_date",
        ),
        CheckConstraint(
            "paid_at IS NULL OR decided_at IS NULL OR paid_at >= decided_at",
            name="payment_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("unit.id", ondelete="RESTRICT")
    )
    warranty_contract_id: Mapped[int | None] = mapped_column(index=True)
    warranty_coverage_id: Mapped[int | None] = mapped_column(index=True)
    service_order_id: Mapped[int | None] = mapped_column(index=True)
    service_record_id: Mapped[int | None] = mapped_column(index=True)
    claim_number: Mapped[str | None] = mapped_column(String(100))
    provider_reference: Mapped[str | None] = mapped_column(String(100))
    component_code: Mapped[str | None] = mapped_column(String(80))
    failure_on: Mapped[date | None]
    failure_description: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    diagnosis: Mapped[str | None] = mapped_column(Text)
    odometer_km: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    engine_hours: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(
        String(30), default="draft", server_default="draft"
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default="0"
    )
    approved_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default="0"
    )
    paid_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default="0"
    )
    deductible_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), server_default="0"
    )
    currency: Mapped[str] = mapped_column(
        String(3), default="MXN", server_default="MXN"
    )
    decision_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    unit: Mapped["Unit"] = relationship(back_populates="claims")
    contract: Mapped["WarrantyContract"] = relationship(
        back_populates="claims", foreign_keys=[warranty_contract_id]
    )
    coverage: Mapped["WarrantyCoverage | None"] = relationship(
        back_populates="claims", foreign_keys=[warranty_coverage_id]
    )
    order: Mapped["ServiceOrder | None"] = relationship(
        back_populates="claims", foreign_keys=[service_order_id]
    )
    service_record: Mapped["ServiceRecord | None"] = relationship(
        back_populates="claims", foreign_keys=[service_record_id]
    )
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="claim",
        foreign_keys="Evidence.warranty_claim_id",
        passive_deletes=True,
    )


class Evidence(AuditColumns, Base):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint("unit_id IS NOT NULL", name="unit_required"),
        ForeignKeyConstraint(
            ["unit_id", "service_order_id"],
            ["service_order.unit_id", "service_order.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["unit_id", "service_record_id"],
            ["service_record.unit_id", "service_record.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["unit_id", "warranty_claim_id"],
            ["warranty_claim.unit_id", "warranty_claim.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_evidence_unit_captured", "unit_id", "captured_at"),
        CheckConstraint("media_type IN ('photo', 'video')", name="media_type"),
        CheckConstraint(
            "byte_size >= 0 AND (duration_seconds IS NULL OR duration_seconds >= 0)",
            name="media_size",
        ),
        CheckConstraint(
            "width_pixels IS NULL OR width_pixels > 0", name="width"
        ),
        CheckConstraint(
            "height_pixels IS NULL OR height_pixels > 0", name="height"
        ),
        CheckConstraint(
            "status IN ('pending', 'available', 'quarantined', 'deleted')",
            name="status",
        ),
        CheckConstraint(
            "status <> 'available' OR (storage_key IS NOT NULL AND length(storage_key) > 0)",
            name="available_storage",
        ),
        CheckConstraint(
            "sha256 IS NULL OR length(sha256) = 64", name="checksum"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("unit.id", ondelete="RESTRICT")
    )
    service_order_id: Mapped[int | None] = mapped_column(index=True)
    service_record_id: Mapped[int | None] = mapped_column(index=True)
    warranty_claim_id: Mapped[int | None] = mapped_column(index=True)
    media_type: Mapped[str] = mapped_column(
        String(10), default="photo", server_default="photo"
    )
    original_filename: Mapped[str] = mapped_column(
        String(255), default="", server_default=""
    )
    mime_type: Mapped[str | None] = mapped_column(String(100))
    storage_key: Mapped[str | None] = mapped_column(Text)
    thumbnail_storage_key: Mapped[str | None] = mapped_column(Text)
    byte_size: Mapped[int] = mapped_column(default=0, server_default="0")
    sha256: Mapped[str | None] = mapped_column(String(64))
    duration_seconds: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    width_pixels: Mapped[int | None]
    height_pixels: Mapped[int | None]
    captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    system: Mapped[str | None] = mapped_column(String(60))
    component_code: Mapped[str | None] = mapped_column(String(80))
    caption: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending"
    )

    unit: Mapped["Unit"] = relationship(back_populates="evidence")
    order: Mapped["ServiceOrder | None"] = relationship(
        back_populates="evidence", foreign_keys=[service_order_id]
    )
    service_record: Mapped["ServiceRecord | None"] = relationship(
        back_populates="evidence", foreign_keys=[service_record_id]
    )
    claim: Mapped["WarrantyClaim | None"] = relationship(
        back_populates="evidence", foreign_keys=[warranty_claim_id]
    )
