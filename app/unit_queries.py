import reflex as rx

import base64
import hashlib
import io
import json
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TypedDict
from PIL import Image
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session
from app.models import (
    ClientOrganization,
    ComponentPrediction,
    DTCCode,
    Evidence,
    Fleet,
    ServiceOrder,
    ServiceRecord,
    TelemetrySnapshot,
    Unit,
    UnitFault,
    WarrantyContract,
    WarrantyCoverage,
)
from app.prediction_engine import VERSION
from app.i18n import TRANSLATIONS
from app.security import AccessDenied, authorize, scope_id

PAGE_SIZE = 25
MEDIA_LIMIT = 8 * 1024 * 1024
ACTIVE_ORDERS = ("draft", "scheduled", "in_progress", "awaiting_parts")
LABELS = {
    "engine": "Motor",
    "brakes": "Frenos",
    "aftertreatment": "Postratamiento",
    "electrical": "Eléctrico",
    "tires": "Neumáticos",
}
RISK_LABELS = {
    "critical": "Crítico",
    "high": "Alto",
    "medium": "Medio",
    "low": "Bajo",
    "unknown": "Sin inferencia vigente",
}


class Inventory(TypedDict):
    rows: list[dict[str, str]]
    fleets: list[dict[str, str]]
    total: int
    page: int
    context: str


class Detail(TypedDict):
    unit: dict[str, str]
    predictions: list[dict[str, str]]
    telemetry: list[dict[str, str]]
    latest: list[dict[str, str]]
    faults: list[dict[str, str]]
    services: list[dict[str, str]]
    warranties: list[dict[str, str]]
    evidence: list[dict[str, str]]
    telemetry_total: int
    fault_total: int
    service_total: int
    evidence_total: int
    context: str


def scope(session: Session, uid: int, expires: float, context: str) -> int:
    return scope_id(session, authorize(session, uid, expires), context)


def owned_unit(
    session: Session,
    uid: int,
    expires: float,
    context: str,
    unit_id: int,
    lock: bool = False,
) -> Unit:
    client = scope(session, uid, expires, context)
    query = (
        select(Unit)
        .join(Fleet, Unit.fleet_id == Fleet.id)
        .join(ClientOrganization, Fleet.client_id == ClientOrganization.id)
        .where(Unit.id == unit_id, ClientOrganization.status == "active")
    )
    if client:
        query = query.where(Fleet.client_id == client)
    if lock:
        query = query.with_for_update(of=Unit)
    unit = session.scalar(query)
    if not unit:
        raise AccessDenied("Unidad no disponible en este contexto.")
    return unit


def current_predictions(unit_ids=None):
    ranked_query = select(
        ComponentPrediction.id,
        func.row_number()
        .over(
            partition_by=(
                ComponentPrediction.unit_id,
                ComponentPrediction.component_code,
            ),
            order_by=(
                ComponentPrediction.predicted_at.desc(),
                ComponentPrediction.id.desc(),
            ),
        )
        .label("rank"),
    ).where(
        ComponentPrediction.model_version == VERSION,
        ComponentPrediction.model_artifact_sha256.is_not(None),
    )
    if unit_ids is not None:
        ranked_query = ranked_query.where(
            ComponentPrediction.unit_id.in_(unit_ids)
        )
    ranked = ranked_query.subquery()
    return (
        select(ComponentPrediction)
        .join(ranked, ranked.c.id == ComponentPrediction.id)
        .where(ranked.c.rank == 1)
    )


def active_contract_condition():
    today = date.today()
    return (
        (WarrantyContract.status == "active")
        & (
            or_(
                WarrantyContract.starts_on.is_(None),
                WarrantyContract.starts_on <= today,
            )
        )
        & (
            or_(
                WarrantyContract.ends_on.is_(None),
                WarrantyContract.ends_on >= today,
            )
        )
        & (
            or_(
                WarrantyContract.mileage_limit_km.is_(None),
                Unit.odometer_km <= WarrantyContract.mileage_limit_km,
            )
        )
        & (
            or_(
                WarrantyContract.engine_hours_limit.is_(None),
                Unit.engine_hours <= WarrantyContract.engine_hours_limit,
            )
        )
    )


def load_inventory(
    uid: int,
    expires: float,
    context: str,
    search: str,
    fleet: str,
    risk: str,
    warranty: str,
    page: int,
) -> Inventory:
    with rx.session() as session:
        client = scope(session, uid, expires, context)
        fleet_query = (
            select(Fleet)
            .join(ClientOrganization, Fleet.client_id == ClientOrganization.id)
            .where(ClientOrganization.status == "active")
        )
        if client:
            fleet_query = fleet_query.where(Fleet.client_id == client)
        fleets = [
            {"id": str(f.id), "name": f.name}
            for f in session.scalars(fleet_query.order_by(Fleet.name))
        ]
        owned = (
            select(Unit.id)
            .join(Fleet, Unit.fleet_id == Fleet.id)
            .join(ClientOrganization, Fleet.client_id == ClientOrganization.id)
            .where(ClientOrganization.status == "active")
        )
        if client:
            owned = owned.where(Fleet.client_id == client)
        predictions = current_predictions(owned).subquery()
        now = datetime.now(timezone.utc)
        aggregate = (
            select(
                predictions.c.unit_id,
                func.max(predictions.c.failure_probability_30d).label("p30"),
                func.max(predictions.c.failure_probability_90d).label("p90"),
                func.max(
                    case(
                        (predictions.c.risk_level == "critical", 4),
                        (predictions.c.risk_level == "high", 3),
                        (predictions.c.risk_level == "medium", 2),
                        else_=1,
                    )
                ).label("risk"),
            )
            .where(predictions.c.valid_until >= now)
            .group_by(predictions.c.unit_id)
            .subquery()
        )
        covered = (
            select(WarrantyContract.id)
            .where(
                WarrantyContract.unit_id == Unit.id, active_contract_condition()
            )
            .correlate(Unit)
            .exists()
        )
        query = (
            select(
                Unit,
                Fleet.name,
                ClientOrganization.display_name,
                aggregate.c.p30,
                aggregate.c.risk,
                covered,
            )
            .join(Fleet, Unit.fleet_id == Fleet.id)
            .join(ClientOrganization, Fleet.client_id == ClientOrganization.id)
            .outerjoin(aggregate, aggregate.c.unit_id == Unit.id)
            .where(Unit.id.in_(owned))
        )
        if search.strip():
            escaped = (
                search.strip()[:100]
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            term = f"%{escaped}%"
            query = query.where(
                or_(
                    Unit.unit_number.ilike(term, escape="\\"),
                    Unit.vin.ilike(term, escape="\\"),
                    Unit.registration_plate.ilike(term, escape="\\"),
                    Unit.model.ilike(term, escape="\\"),
                )
            )
        if fleet:
            if not fleet.isdigit():
                raise ValueError("Flota inválida.")
            query = query.where(Unit.fleet_id == int(fleet))
        risk_values = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        if risk == "unknown":
            query = query.where(aggregate.c.risk.is_(None))
        elif risk in risk_values:
            query = query.where(aggregate.c.risk == risk_values[risk])
        if warranty in ("covered", "uncovered"):
            query = query.where(covered if warranty == "covered" else ~covered)
        total = int(
            session.scalar(select(func.count()).select_from(query.subquery()))
            or 0
        )
        page = min(max(1, page), max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE))
        rows = []
        for u, fleet_name, client_name, p30, level, coverage in session.execute(
            query.order_by(Unit.unit_number, Unit.id)
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        ):
            risk_key = {4: "critical", 3: "high", 2: "medium", 1: "low"}.get(
                level, "unknown"
            )
            rows.append(
                {
                    "id": str(u.id),
                    "number": u.unit_number or str(u.id),
                    "vin": u.vin or "—",
                    "plate": u.registration_plate or "—",
                    "model": f"{u.manufacturer} {u.model}",
                    "fleet": fleet_name,
                    "client": client_name,
                    "mileage": f"{float(u.odometer_km):,.0f} km",
                    "risk": RISK_LABELS[risk_key],
                    "risk_key": risk_key,
                    "p30": f"{float(p30) * 100:.1f}%"
                    if p30 is not None
                    else "—",
                    "warranty": "Contrato vigente · verificar componentes"
                    if coverage
                    else "Sin contrato vigente",
                    "status": u.status,
                }
            )
        return {
            "rows": rows,
            "fleets": fleets,
            "total": total,
            "page": page,
            "context": str(client) if client else "network",
        }


def warranty_review(
    session: Session,
    unit: Unit,
    component: str,
    system: str,
    due: date,
    language: str = "es",
) -> tuple[str, str]:
    pairs = session.execute(
        select(WarrantyContract, WarrantyCoverage)
        .join(
            WarrantyCoverage,
            WarrantyCoverage.warranty_contract_id == WarrantyContract.id,
        )
        .where(
            WarrantyContract.unit_id == unit.id,
            WarrantyCoverage.component_code == component,
        )
    ).all()
    for contract, coverage in pairs:
        starts = [d for d in (contract.starts_on, coverage.starts_on) if d]
        ends = [d for d in (contract.ends_on, coverage.ends_on) if d]
        miles = [
            v
            for v in (contract.mileage_limit_km, coverage.mileage_limit_km)
            if v is not None
        ]
        hours = [
            v
            for v in (contract.engine_hours_limit, coverage.engine_hours_limit)
            if v is not None
        ]
        eligible = (
            contract.status == "active"
            and (
                coverage.parts_coverage_percent > 0
                or coverage.labor_coverage_percent > 0
            )
            and all(d <= due for d in starts)
            and all(d >= due for d in ends)
            and all(unit.odometer_km <= v for v in miles)
            and all(unit.engine_hours <= v for v in hours)
        )
        if eligible:
            expires = min(ends).isoformat() if ends else "sin fecha documentada"
            limit = (
                f"{float(min(miles)):,.0f} km"
                if miles
                else "sin límite documentado"
            )
            note = f"Cobertura potencial {component}: piezas {float(coverage.parts_coverage_percent):.0f}%, mano de obra {float(coverage.labor_coverage_percent):.0f}%; hasta {expires}, {limit}. Uso evaluado {float(unit.odometer_km):,.0f} km / {float(unit.engine_hours):,.0f} h, fecha objetivo {due.isoformat()}."
            if coverage.requires_preapproval:
                note = f"{note} Requiere autorización previa."
            note = f"{note} Verificar términos, exclusiones, historial de mantenimiento, deducible y kilometraje al servicio; no es aprobación de garantía. {coverage.maintenance_requirements or ''} {coverage.exclusions or contract.exclusions or ''}"
            if language == "en":
                expiry = min(ends).isoformat() if ends else "no documented date"
                mile_limit = (
                    f"{float(min(miles)):,.0f} km"
                    if miles
                    else "no documented limit"
                )
                preapproval = (
                    " Requires preapproval."
                    if coverage.requires_preapproval
                    else ""
                )
                note = f"Possible coverage for {component}: parts {float(coverage.parts_coverage_percent):.0f}%, labor {float(coverage.labor_coverage_percent):.0f}%; until {expiry}, {mile_limit}. Current usage {float(unit.odometer_km):,.0f} km / {float(unit.engine_hours):,.0f} h; target date {due.isoformat()}.{preapproval} Verify terms, exclusions, maintenance history, deductible and service mileage with the provider; this is NOT warranty approval. {coverage.maintenance_requirements or ''} {coverage.exclusions or contract.exclusions or ''}"
            return "potential", note
    if language == "en":
        return (
            "not_covered",
            f"No exact current coverage found for {component} ({system}) at target date {due.isoformat()} and current usage. Verify terms with provider; do not assume consumables are covered.",
        )
    return (
        "not_covered",
        f"No se encontró cobertura vigente exacta para {component} ({system}) a la fecha objetivo {due.isoformat()} y uso actual. Verificar términos con el proveedor; no asumir cobertura de consumibles.",
    )


def telemetry_values(
    t: TelemetrySnapshot, language: str = "es"
) -> list[dict[str, str]]:
    specs = (
        ("Kilometraje", "odometer_km", "km"),
        ("Horas motor", "engine_hours", "h"),
        ("Desgaste freno", "brake_wear_percent", "%"),
        ("Refrigerante", "coolant_temperature_c", "°C"),
        ("Aceite", "oil_temperature_c", "°C"),
        ("Batería", "battery_voltage", "V"),
        ("Neumáticos", "tire_pressure_kpa", "kPa"),
        ("Carga", "load_percent", "%"),
        ("Ralentí", "idle_percent", "%"),
        ("Frenadas bruscas", "harsh_braking_events", "eventos"),
        ("Aceleraciones bruscas", "harsh_acceleration_events", "eventos"),
        ("Excesos velocidad", "overspeed_events", "eventos"),
        ("Distancia ventana", "distance_km", "km"),
        ("Conducción ventana", "driving_hours", "h"),
    )
    return [
        {
            "label": TRANSLATIONS.get(label, label)
            if language == "en"
            else label,
            "value": f"{float(getattr(t, key)):.1f} {'events' if language == 'en' and suffix == 'eventos' else suffix}"
            if getattr(t, key) is not None
            else ("No sensor" if language == "en" else "Sin sensor"),
        }
        for label, key, suffix in specs
    ]


def load_detail(
    uid: int,
    expires: float,
    context: str,
    unit_id: int,
    telemetry_page: int = 1,
    fault_page: int = 1,
    service_page: int = 1,
    evidence_page: int = 1,
) -> Detail:
    with rx.session() as session:
        unit = owned_unit(session, uid, expires, context, unit_id)
        language = authorize(session, uid, expires).preferred_language
        client = scope(session, uid, expires, context)
        fleet = session.get(Fleet, unit.fleet_id)
        newest = session.scalar(
            select(TelemetrySnapshot)
            .where(TelemetrySnapshot.unit_id == unit.id)
            .order_by(
                TelemetrySnapshot.observed_at.desc(),
                TelemetrySnapshot.id.desc(),
            )
            .limit(1)
        )
        predictions = []
        for p in session.scalars(
            current_predictions([unit.id]).order_by(ComponentPrediction.system)
        ):
            due = p.recommended_by or date.today()
            _, review = warranty_review(
                session, unit, p.component_code, p.system, due, language
            )
            order = session.scalar(
                select(ServiceOrder)
                .where(
                    ServiceOrder.unit_id == unit.id,
                    ServiceOrder.prediction_id == p.id,
                    ServiceOrder.status.in_(ACTIVE_ORDERS),
                )
                .order_by(ServiceOrder.id)
                .limit(1)
            )
            metric_text = (
                "No documented evaluation"
                if language == "en"
                else "Sin evaluación documentada"
            )
            try:
                payload = json.loads(p.explanation_es or "{}")
                m = payload.get("holdout", {})
                metric_text = f"Test n={int(m['test_rows'])} · Brier 30/90: {m['brier30']:.3f}/{m['brier90']:.3f} · AUC 30/90: {m['auc30']:.3f}/{m['auc90']:.3f} · log-loss: {m['log_loss']:.3f}"
            except (ValueError, KeyError, TypeError) as e:
                logging.exception(f"Error: {e}")
                metric_text = (
                    "Evaluation unavailable for this inference"
                    if language == "en"
                    else "Evaluación no disponible para esta inferencia"
                )
            valid = bool(
                p.valid_until and p.valid_until >= datetime.now(timezone.utc)
            )
            predictions.append(
                {
                    "id": str(p.id),
                    "system": LABELS.get(p.system, p.system),
                    "component": p.component_code,
                    "risk": RISK_LABELS[p.risk_level],
                    "risk_key": p.risk_level,
                    "p30": f"{float(p.failure_probability_30d) * 100:.1f}%",
                    "p90": f"{float(p.failure_probability_90d) * 100:.1f}%",
                    "health": f"{(1 - float(p.failure_probability_90d)) * 100:.0f}/100",
                    "action": (p.recommended_action_en or "Inspect component")
                    if language == "en"
                    else (p.recommended_action_es or "Revisar componente"),
                    "due": due.isoformat(),
                    "window": {
                        "critical": "Antes de 24 h · no despachar sin revisión",
                        "high": "Dentro de 72 h",
                        "medium": "Dentro de 14 días",
                        "low": "Dentro de 30 días",
                    }[p.risk_level],
                    "cost": f"${float(p.estimated_repair_cost or 0):,.2f} MXN",
                    "downtime": f"{float(p.estimated_downtime_hours or 0):.1f} h",
                    "warranty": review,
                    "order": f"{order.order_number} · {order.status}"
                    if order
                    else "",
                    "valid": "yes" if valid else "no",
                    "provenance": f"{p.model_name} · {p.model_version} · {'data' if language == 'en' else 'datos'} {p.training_dataset_version} · {'inference' if language == 'en' else 'inferencia'} {p.predicted_at.isoformat()} · {'valid until' if language == 'en' else 'vigencia'} {p.valid_until.isoformat() if p.valid_until else ('not documented' if language == 'en' else 'no documentada')}",
                    "artifact": p.model_artifact_sha256 or "",
                    "metrics": metric_text,
                }
            )
        ts_query = select(TelemetrySnapshot).where(
            TelemetrySnapshot.unit_id == unit.id
        )
        telemetry_total = int(
            session.scalar(
                select(func.count()).select_from(ts_query.subquery())
            )
            or 0
        )
        telemetry = []
        for t in session.scalars(
            ts_query.order_by(
                TelemetrySnapshot.observed_at.desc(),
                TelemetrySnapshot.id.desc(),
            )
            .offset((max(1, telemetry_page) - 1) * 20)
            .limit(20)
        ):
            telemetry.append(
                {
                    "id": str(t.id),
                    "date": t.observed_at.strftime("%d/%m/%Y %H:%M UTC"),
                    "usage": f"{float(t.odometer_km):,.0f} km · {float(t.engine_hours):,.0f} h",
                    "values": " · ".join(
                        f"{v['label']}: {v['value']}"
                        for v in telemetry_values(t, language)
                    ),
                    "source": f"{'SYNTHETIC' if t.is_synthetic else t.source} · {t.generator_version or t.source} · {t.quality_status}",
                }
            )
        fault_query = (
            select(UnitFault, DTCCode)
            .join(DTCCode, UnitFault.dtc_code_id == DTCCode.id)
            .where(UnitFault.unit_id == unit.id)
        )
        fault_total = int(
            session.scalar(
                select(func.count()).select_from(fault_query.subquery())
            )
            or 0
        )
        faults = [
            {
                "id": str(f.id),
                "code": d.code or "—",
                "system": LABELS.get(d.system, d.system),
                "description": (d.description_en or d.description_es)
                if language == "en"
                else d.description_es,
                "status": f.status,
                "severity": d.severity,
                "first": f.first_seen_at.isoformat(),
                "last": f.last_seen_at.isoformat(),
                "cleared": f.cleared_at.isoformat() if f.cleared_at else "—",
                "count": str(f.occurrence_count),
                "source": f.source,
            }
            for f, d in session.execute(
                fault_query.order_by(
                    case(
                        (UnitFault.status == "active", 0),
                        (UnitFault.status == "intermittent", 1),
                        else_=2,
                    ),
                    UnitFault.last_seen_at.desc(),
                    UnitFault.id.desc(),
                )
                .offset((max(1, fault_page) - 1) * 20)
                .limit(20)
            )
        ]
        service_query = select(ServiceRecord).where(
            ServiceRecord.unit_id == unit.id
        )
        service_total = int(
            session.scalar(
                select(func.count()).select_from(service_query.subquery())
            )
            or 0
        )
        services = [
            {
                "id": str(s.id),
                "date": s.performed_at.isoformat(),
                "description": s.description,
                "status": s.status,
                "usage": f"{float(s.odometer_km):,.0f} km",
                "cost": f"${float(s.labor_cost + s.parts_cost + s.other_cost):,.2f} MXN",
                "details": f"{s.work_performed or s.findings or 'Sin notas adicionales'} · {s.workshop_name or 'Taller sin documentar'}",
                "next": s.next_service_on.isoformat()
                if s.next_service_on
                else "Sin fecha",
            }
            for s in session.scalars(
                service_query.order_by(
                    ServiceRecord.performed_at.desc(), ServiceRecord.id.desc()
                )
                .offset((max(1, service_page) - 1) * 20)
                .limit(20)
            )
        ]
        warranties = []
        for contract in session.scalars(
            select(WarrantyContract)
            .where(WarrantyContract.unit_id == unit.id)
            .order_by(WarrantyContract.id)
        ):
            components = session.scalars(
                select(WarrantyCoverage.component_code).where(
                    WarrantyCoverage.warranty_contract_id == contract.id
                )
            ).all()
            warranties.append(
                {
                    "id": str(contract.id),
                    "contract": contract.contract_number or "Sin número",
                    "provider": contract.provider_name,
                    "status": contract.status,
                    "dates": f"{contract.starts_on or '—'} → {contract.ends_on or '—'}",
                    "limits": f"{float(contract.mileage_limit_km):,.0f} km"
                    if contract.mileage_limit_km is not None
                    else "Sin límite km documentado",
                    "components": ", ".join(
                        c or "Sin componente" for c in components
                    )
                    or "Sin componentes documentados",
                    "terms": f"{contract.terms or 'Verificar términos'} · {contract.exclusions or 'Solicitar exclusiones'}",
                }
            )
        ev_query = select(
            Evidence.id,
            Evidence.original_filename,
            Evidence.media_type,
            Evidence.status,
            Evidence.uploaded_at,
            Evidence.caption,
            Evidence.byte_size,
        ).where(Evidence.unit_id == unit.id, Evidence.status != "deleted")
        evidence_total = int(
            session.scalar(
                select(func.count()).select_from(ev_query.subquery())
            )
            or 0
        )
        evidence = [
            {
                "id": str(e.id),
                "name": e.original_filename,
                "type": e.media_type,
                "status": e.status,
                "date": e.uploaded_at.isoformat(),
                "caption": e.caption or "Sin descripción",
                "size": f"{e.byte_size / 1024:.1f} KB",
            }
            for e in session.execute(
                ev_query.order_by(
                    Evidence.uploaded_at.desc(), Evidence.id.desc()
                )
                .offset((max(1, evidence_page) - 1) * 20)
                .limit(20)
            )
        ]
        return {
            "unit": {
                "id": str(unit.id),
                "number": unit.unit_number or str(unit.id),
                "vin": unit.vin or "—",
                "plate": unit.registration_plate or "—",
                "model": f"{unit.manufacturer} {unit.model} · {unit.model_year or '—'}",
                "fleet": fleet.name,
                "status": unit.status,
                "mileage": f"{float(unit.odometer_km):,.0f} km",
                "hours": f"{float(unit.engine_hours):,.0f} h",
                "observed": newest.observed_at.isoformat()
                if newest
                else "Sin telemetría",
                "source": f"{'SYNTHETIC' if newest and newest.is_synthetic else 'Medición'} · {newest.generator_version or newest.source}"
                if newest
                else "Sin datos",
                "active_faults": str(
                    session.scalar(
                        select(func.count())
                        .select_from(UnitFault)
                        .where(
                            UnitFault.unit_id == unit.id,
                            UnitFault.status.in_(["active", "intermittent"]),
                        )
                    )
                    or 0
                ),
            },
            "predictions": predictions,
            "telemetry": telemetry,
            "latest": telemetry_values(newest, language) if newest else [],
            "faults": faults,
            "services": services,
            "warranties": warranties,
            "evidence": evidence,
            "telemetry_total": telemetry_total,
            "fault_total": fault_total,
            "service_total": service_total,
            "evidence_total": evidence_total,
            "context": str(client) if client else "network",
        }


def create_service_order(
    uid: int, expires: float, context: str, unit_id: int, prediction_id: int
) -> str:
    with rx.session() as session:
        unit = owned_unit(session, uid, expires, context, unit_id, lock=True)
        p = session.scalar(
            current_predictions([unit.id]).where(
                ComponentPrediction.id == prediction_id
            )
        )
        now = datetime.now(timezone.utc)
        if not p or not p.valid_until or p.valid_until < now:
            raise ValueError(
                "La inferencia no está vigente o no pertenece a esta unidad."
            )
        existing = session.scalar(
            select(ServiceOrder).where(
                ServiceOrder.unit_id == unit.id,
                ServiceOrder.prediction_id == p.id,
                ServiceOrder.status.in_(ACTIVE_ORDERS),
            )
        )
        if existing:
            return f"Ya existe la orden activa {existing.order_number}."
        eligibility, review = warranty_review(
            session,
            unit,
            p.component_code,
            p.system,
            p.recommended_by or now.date(),
        )
        order = ServiceOrder(
            unit_id=unit.id,
            prediction_id=p.id,
            order_number=f"REC-{unit.id}-{p.id}-{now.strftime('%Y%m%d%H%M%S%f')}",
            title=f"{LABELS.get(p.system, p.system)} · revisión por riesgo {RISK_LABELS[p.risk_level]}",
            description=p.recommended_action_es,
            component_code=p.component_code,
            service_type="predictive",
            priority={
                "critical": "critical",
                "high": "high",
                "medium": "normal",
                "low": "low",
            }[p.risk_level],
            status="draft",
            requested_at=now,
            due_on=p.recommended_by,
            odometer_km=unit.odometer_km,
            engine_hours=unit.engine_hours,
            estimated_parts_cost=Decimal(p.estimated_repair_cost or 0)
            * Decimal("0.7"),
            estimated_labor_cost=Decimal(p.estimated_repair_cost or 0)
            * Decimal("0.3"),
            estimated_downtime_hours=p.estimated_downtime_hours or Decimal(0),
            warranty_eligibility=eligibility,
            warranty_review_notes=review,
            current_step="Confirmar diagnóstico y cotización; programar taller",
            progress_notes="Estimación orientativa; no se ha reservado taller ni aprobado garantía.",
        )
        session.add(order)
        session.commit()
        return f"Orden {order.order_number} guardada en borrador; confirmar diagnóstico y programar taller."


def validated_media(data: bytes) -> tuple[bytes, str, str]:
    if not data or len(data) > MEDIA_LIMIT:
        raise ValueError("Archivo vacío o mayor a 8 MB.")
    if data.startswith(b"\xff\xd8\xff") or data.startswith(
        b"\x89PNG\r\n\x1a\n"
    ):
        Image.MAX_IMAGE_PIXELS = 16_000_000
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 16_000_000:
                raise ValueError("Imagen demasiado grande.")
            clean = image.convert("RGB")
            clean.thumbnail((2400, 2400))
            output = io.BytesIO()
            clean.save(output, format="JPEG", quality=88)
        return output.getvalue(), "image/jpeg", "photo"
    if (
        len(data) >= 32
        and data[4:8] == b"ftyp"
        and data[8:12] in (b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"M4V ")
    ):
        box_size = int.from_bytes(data[:4], "big")
        if 16 <= box_size <= len(data) and b"mdat" in data and b"moov" in data:
            return data, "video/mp4", "video"
    raise ValueError(
        "Formato no admitido o archivo inválido. Utiliza JPEG, PNG o MP4 compatible con el navegador."
    )


def save_evidence(
    uid: int,
    expires: float,
    context: str,
    unit_id: int,
    data: bytes,
    filename: str,
) -> None:
    with rx.session() as session:
        owned_unit(session, uid, expires, context, unit_id)
    clean, mime, kind = validated_media(data)
    checksum = hashlib.sha256(clean).hexdigest()
    with rx.session() as session:
        owned_unit(session, uid, expires, context, unit_id, lock=True)
        if session.scalar(
            select(Evidence.id).where(
                Evidence.unit_id == unit_id,
                Evidence.sha256 == checksum,
                Evidence.status == "available",
            )
        ):
            return
        session.add(
            Evidence(
                unit_id=unit_id,
                media_type=kind,
                original_filename=filename.replace("\\", "/").rsplit("/", 1)[
                    -1
                ][:255],
                mime_type=mime,
                storage_key=f"inline-v1:{base64.b64encode(clean).decode('ascii')}",
                byte_size=len(clean),
                sha256=checksum,
                caption="Archivo aportado por usuario autorizado. Fecha de captura no verificada.",
                status="available",
            )
        )
        session.commit()


def read_evidence(
    uid: int, expires: float, context: str, unit_id: int, evidence_id: int
) -> tuple[str, str, str]:
    with rx.session() as session:
        owned_unit(session, uid, expires, context, unit_id)
        e = session.scalar(
            select(Evidence).where(
                Evidence.unit_id == unit_id,
                Evidence.id == evidence_id,
                Evidence.status == "available",
            )
        )
        if (
            not e
            or not e.storage_key
            or not e.storage_key.startswith("inline-v1:")
            or e.mime_type not in ("image/jpeg", "video/mp4")
        ):
            raise ValueError(
                "Evidencia no disponible en el almacenamiento privado."
            )
        encoded = e.storage_key.removeprefix("inline-v1:")
        data = base64.b64decode(encoded, validate=True)
        if (
            len(data) > MEDIA_LIMIT
            or hashlib.sha256(data).hexdigest() != e.sha256
        ):
            raise ValueError(
                "La integridad de la evidencia no pudo verificarse."
            )
        return (
            f"data:{e.mime_type};base64,{encoded}",
            e.media_type,
            e.original_filename,
        )
