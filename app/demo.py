import reflex as rx

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text
from app.models import (
    ClientOrganization,
    Fleet,
    Unit,
    TelemetrySnapshot,
    ComponentPrediction,
    ServiceOrder,
    ServiceRecord,
    WarrantyContract,
    WarrantyCoverage,
    OrderPart,
)


def seed_demo() -> None:
    try:
        with rx.session() as session:
            session.execute(text("SELECT pg_advisory_xact_lock(70421901)"))
            now = datetime.now(timezone.utc).replace(
                minute=0, second=0, microsecond=0
            )
            names = [
                ("SYN-NORTE", "Transportes del Norte", "Monterrey · Norte"),
                ("SYN-BAJIO", "Logística del Bajío", "León · Bajío"),
                (
                    "SYN-PACIFICO",
                    "Carga del Pacífico",
                    "Guadalajara · Occidente",
                ),
                ("SYN-CENTRO", "Distribución Centro", "Querétaro · Centro"),
                ("SYN-SUR", "Rutas del Sureste", "Mérida · Sureste"),
            ]
            for ci, (code, name, region) in enumerate(names):
                if session.scalar(
                    select(ClientOrganization.id).where(
                        ClientOrganization.code == code
                    )
                ):
                    continue
                client = ClientOrganization(
                    code=code,
                    legal_name=f"{name} — organización sintética",
                    display_name=name,
                    contact_name="Coordinación de flota (sintético)",
                )
                session.add(client)
                session.flush()
                fleet = Fleet(
                    client_id=client.id,
                    code="PRINCIPAL",
                    name=f"Flota {name}",
                    operating_region=region,
                    depot_name=region,
                    notes="SYNTHETIC · Datos de demostración, no corresponden a una empresa real.",
                )
                session.add(fleet)
                session.flush()
                for ui in range(12 + ci * 2):
                    number = f"{ci + 1}{ui + 1:03d}"
                    mileage = 85000 + ui * 17500 + ci * 8300
                    unit = Unit(
                        fleet_id=fleet.id,
                        unit_number=number,
                        vin=f"SYN{ci + 1:02d}{ui + 1:012d}",
                        registration_plate=f"SYN-{number}",
                        manufacturer="Freightliner",
                        model="Cascadia" if ui % 3 else "M2 106",
                        model_year=2021 + ui % 4,
                        odometer_km=Decimal(mileage),
                        engine_hours=Decimal(mileage // 48),
                        status="in_service" if ui % 9 == 8 else "active",
                        typical_route=region,
                        commissioned_on=now.date() - timedelta(days=650),
                        notes="SYNTHETIC · Unidad ficticia",
                    )
                    session.add(unit)
                    session.flush()
                    base = 0.12 + (ui % 6) * 0.12 + ci * 0.015
                    latest = None
                    for week in range(8):
                        observed = now - timedelta(weeks=7 - week)
                        trend = [
                            0.02,
                            0.035,
                            0.025,
                            0.055,
                            0.075,
                            0.06,
                            0.04,
                            0.03,
                        ][week]
                        p30 = min(0.94, base + trend)
                        p90 = min(0.98, p30 + 0.19)
                        telemetry = TelemetrySnapshot(
                            unit_id=unit.id,
                            observed_at=observed,
                            source_record_id=f"demo-v1-{week}",
                            generator_version="demo-v1",
                            quality_status="validated",
                            odometer_km=Decimal(
                                max(0, mileage - (7 - week) * 2100)
                            ),
                            engine_hours=Decimal(
                                mileage // 48 - (7 - week) * 40
                            ),
                            distance_km=Decimal(2100 + ui * 20),
                            driving_hours=Decimal(40),
                            average_speed_kph=Decimal(58),
                            max_speed_kph=Decimal(93),
                            idle_percent=Decimal(12 + ui % 8),
                            urban_percent=Decimal(25),
                            highway_percent=Decimal(70),
                            fuel_consumed_liters=Decimal(650 + ui * 8),
                            coolant_temperature_c=Decimal(87 + ui % 12),
                            brake_wear_percent=Decimal(25 + ui * 3),
                            battery_voltage=Decimal("24.6"),
                            harsh_braking_events=ui % 5,
                        )
                        session.add(telemetry)
                        session.flush()
                        latest = ComponentPrediction(
                            unit_id=unit.id,
                            telemetry_snapshot_id=telemetry.id,
                            system="brakes",
                            component_code="brake_pads",
                            predicted_at=observed,
                            valid_until=observed + timedelta(days=14),
                            failure_probability_30d=Decimal(str(p30)),
                            failure_probability_90d=Decimal(str(p90)),
                            confidence=Decimal("0.84"),
                            risk_level="critical"
                            if p30 >= 0.75
                            else "high"
                            if p30 >= 0.55
                            else "medium"
                            if p30 >= 0.3
                            else "low",
                            model_name="SYNTHETIC demo scenario (not trained)",
                            model_version="demo-v1",
                            training_dataset_version="synthetic-demo-v1",
                            explanation_es="Escenario sintético basado en uso y desgaste; no es una inferencia de un modelo entrenado.",
                            recommended_action_es="Inspeccionar frenos y verificar desgaste de pastillas",
                            recommended_by=observed.date()
                            + timedelta(days=3 if p30 >= 0.55 else 14),
                            estimated_repair_cost=Decimal(4500 + ui * 320),
                            estimated_downtime_hours=Decimal(4),
                            currency="MXN",
                        )
                        session.add(latest)
                    session.flush()
                    contract = WarrantyContract(
                        unit_id=unit.id,
                        contract_number=f"SYN-W-{number}",
                        provider_name="Garantía fabricante · demo",
                        starts_on=now.date() - timedelta(days=650),
                        ends_on=now.date() + timedelta(days=180 + ui * 12),
                        mileage_limit_km=Decimal(500000),
                        status="active",
                        terms="Contrato sintético de demostración",
                    )
                    session.add(contract)
                    session.flush()
                    session.add(
                        WarrantyCoverage(
                            warranty_contract_id=contract.id,
                            system="engine",
                            component_code="engine",
                            parts_coverage_percent=Decimal(100),
                            labor_coverage_percent=Decimal(100),
                        )
                    )
                    completed = now - timedelta(
                        days=min(ui % 12, now.day - 1), hours=ui % 3
                    )
                    order = ServiceOrder(
                        unit_id=unit.id,
                        order_number=f"SYN-C-{number}",
                        title="Mantenimiento preventivo realizado",
                        status="completed",
                        progress_percent=100,
                        started_at=completed - timedelta(hours=5),
                        completed_at=completed,
                        actual_labor_cost=Decimal(1800 + ui * 85),
                        actual_parts_cost=Decimal(2700 + ui * 110),
                        actual_other_cost=Decimal(200),
                        actual_downtime_hours=Decimal(5),
                        workshop_name="Taller regional · sintético",
                        progress_notes="Servicio documentado",
                        progress_saved_at=completed,
                    )
                    session.add(order)
                    session.flush()
                    session.add(
                        ServiceRecord(
                            unit_id=unit.id,
                            service_order_id=order.id,
                            performed_at=completed,
                            description="Cambio de aceite y filtros; inspección de frenos",
                            odometer_km=Decimal(mileage),
                            engine_hours=Decimal(mileage // 48),
                            labor_cost=order.actual_labor_cost,
                            parts_cost=order.actual_parts_cost,
                            other_cost=order.actual_other_cost,
                            status="verified",
                            next_service_on=now.date() + timedelta(days=60),
                            invoice_reference=f"SYN-INV-{number}",
                        )
                    )
                    if ui % 3 == 0:
                        pending = ServiceOrder(
                            unit_id=unit.id,
                            prediction_id=latest.id,
                            order_number=f"SYN-O-{number}",
                            title="Inspección del sistema de frenos",
                            component_code="brake_pads",
                            priority="high",
                            status="awaiting_parts" if ui % 2 else "scheduled",
                            progress_percent=25 if ui % 2 else 0,
                            due_on=now.date() - timedelta(days=ui % 4 + 1),
                            scheduled_start_at=now - timedelta(days=2),
                            estimated_labor_cost=Decimal(1800),
                            estimated_parts_cost=Decimal(3400),
                            workshop_name="Taller regional · sintético",
                            warranty_eligibility="unchecked",
                        )
                        session.add(pending)
                        session.flush()
                        session.add(
                            OrderPart(
                                service_order_id=pending.id,
                                part_number="SYN-BRAKE-01",
                                description="Juego de pastillas · demo",
                                estimated_unit_cost=Decimal(3400),
                                quantity_ordered=Decimal(1),
                                status="ordered",
                                expected_on=now.date() + timedelta(days=2),
                            )
                        )
            session.commit()
    except Exception as e:
        logging.exception(f"Error: {e}")
        raise


async def seed_startup() -> None:
    from app.prediction_engine import prediction_startup

    await asyncio.to_thread(seed_demo)
    await prediction_startup()
