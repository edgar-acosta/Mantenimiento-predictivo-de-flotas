import reflex as rx

import calendar
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import TypedDict
from sqlalchemy import func, or_, select
from app.models import (
    ClientOrganization,
    ComponentPrediction,
    Fleet,
    OrderPart,
    ServiceOrder,
    Unit,
    WarrantyClaim,
    WarrantyContract,
    WarrantyCoverage,
)
from app.security import AccessDenied, authorize, scope_id
from app.unit_queries import owned_unit, warranty_review

ORDER_STATES = [
    "draft",
    "scheduled",
    "in_progress",
    "awaiting_parts",
    "completed",
]
ORDER_TRANSITIONS = {
    "draft": {"scheduled", "cancelled"},
    "scheduled": {"draft", "in_progress", "cancelled"},
    "in_progress": {"awaiting_parts", "completed", "cancelled"},
    "awaiting_parts": {"in_progress", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}
CLAIM_STATES = [
    "draft",
    "submitted",
    "under_review",
    "approved",
    "partially_approved",
    "rejected",
    "paid",
    "withdrawn",
]
CLAIM_TRANSITIONS = {
    "draft": {"submitted", "withdrawn"},
    "submitted": {"under_review", "withdrawn"},
    "under_review": {"approved", "partially_approved", "rejected", "withdrawn"},
    "approved": {"paid"},
    "partially_approved": {"paid"},
    "rejected": {"draft"},
    "paid": set(),
    "withdrawn": {"draft"},
}


class WarrantyData(TypedDict):
    rows: list[dict[str, str]]
    total: int
    detail: dict[str, str]
    coverage: list[dict[str, str]]
    claims: list[dict[str, str]]
    claim_total: int
    orders: list[dict[str, str]]


class OrdersData(TypedDict):
    columns: list[dict[str, str]]
    cards: list[dict[str, str]]
    days: list[dict[str, str]]
    calendar_orders: list[dict[str, str]]
    calendar_total: int
    detail: dict[str, str]
    parts: list[dict[str, str]]
    part_total: int
    warranties: list[dict[str, str]]
    claims: list[dict[str, str]]


def money(value: object, label: str = "Amount", places: int = 2) -> Decimal:
    try:
        result = Decimal(str(value or "0"))
    except (InvalidOperation, ValueError):
        raise ValueError(
            f"{label}: invalid number / número inválido."
        ) from None
    if (
        not result.is_finite()
        or result < 0
        or result >= Decimal("1000000000000")
    ):
        raise ValueError(
            f"{label}: must be a finite nonnegative amount / importe no negativo."
        )
    quantum = Decimal("0.01") if places == 2 else Decimal("0.001")
    if result != result.quantize(quantum):
        raise ValueError(
            f"{label}: maximum {places} decimals / decimales máximos."
        )
    return result.quantize(quantum)


def day(value: object) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValueError("Invalid date / Fecha inválida.") from None


def moment(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        result = datetime.fromisoformat(raw)
        return (
            result.replace(tzinfo=timezone.utc)
            if result.tzinfo is None
            else result.astimezone(timezone.utc)
        )
    except ValueError:
        raise ValueError(
            "Invalid date/time / Fecha y hora inválidas."
        ) from None


def text_value(
    data: dict[str, str], key: str, limit: int = 4000, required: bool = False
) -> str:
    value = str(data.get(key, "")).strip()
    if len(value) > limit or (required and not value):
        raise ValueError(
            f"{key}: required, maximum {limit} characters / obligatorio, caracteres máximos."
        )
    return value


def serialize(model: object, fields: list[str]) -> dict[str, str]:
    result = {}
    for field in fields:
        value = getattr(model, field)
        if value is None:
            result[field] = ""
        elif isinstance(value, datetime):
            result[field] = (
                value.astimezone(timezone.utc).isoformat()
                if field in ("updated_at", "progress_saved_at")
                else value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")
            )
        elif isinstance(value, date):
            result[field] = value.isoformat()
        elif isinstance(value, bool):
            result[field] = "yes" if value else "no"
        elif isinstance(value, Decimal):
            result[field] = (
                f"{value:.3f}"
                if field.startswith("quantity_")
                else f"{value:.2f}"
            )
        else:
            result[field] = str(value)
    return result


CONTRACT_FIELDS = [
    "id",
    "unit_id",
    "contract_number",
    "provider_name",
    "status",
    "starts_on",
    "ends_on",
    "starting_odometer_km",
    "mileage_limit_km",
    "starting_engine_hours",
    "engine_hours_limit",
    "deductible",
    "total_claim_limit",
    "currency",
    "terms",
    "exclusions",
]
COVERAGE_FIELDS = [
    "id",
    "component_code",
    "system",
    "starts_on",
    "ends_on",
    "mileage_limit_km",
    "engine_hours_limit",
    "parts_coverage_percent",
    "labor_coverage_percent",
    "deductible",
    "claim_limit",
    "requires_preapproval",
    "maintenance_requirements",
    "exclusions",
]
CLAIM_FIELDS = [
    "id",
    "unit_id",
    "warranty_contract_id",
    "warranty_coverage_id",
    "service_order_id",
    "claim_number",
    "provider_reference",
    "component_code",
    "failure_on",
    "failure_description",
    "diagnosis",
    "odometer_km",
    "engine_hours",
    "status",
    "submitted_at",
    "decided_at",
    "paid_at",
    "requested_amount",
    "approved_amount",
    "paid_amount",
    "deductible_amount",
    "currency",
    "decision_reason",
    "notes",
    "updated_at",
]
ORDER_FIELDS = [
    "id",
    "unit_id",
    "prediction_id",
    "order_number",
    "title",
    "description",
    "component_code",
    "status",
    "priority",
    "progress_percent",
    "current_step",
    "progress_notes",
    "progress_saved_at",
    "workshop_name",
    "assigned_technician",
    "due_on",
    "scheduled_start_at",
    "scheduled_end_at",
    "started_at",
    "completed_at",
    "estimated_labor_cost",
    "estimated_parts_cost",
    "estimated_other_cost",
    "actual_labor_cost",
    "actual_parts_cost",
    "actual_other_cost",
    "currency",
    "warranty_eligibility",
    "warranty_review_notes",
]
PART_FIELDS = [
    "id",
    "line_number",
    "part_number",
    "description",
    "component_code",
    "supplier_name",
    "quantity_required",
    "quantity_ordered",
    "quantity_received",
    "quantity_installed",
    "estimated_unit_cost",
    "actual_unit_cost",
    "status",
    "expected_on",
    "notes",
]


def contract_owned(
    session,
    uid: int,
    expires: float,
    context: str,
    target: int,
    lock: bool = False,
):
    authorize(session, uid, expires)
    contract = session.scalar(
        select(WarrantyContract).where(WarrantyContract.id == target)
    )
    if not contract:
        raise AccessDenied("Contract unavailable / Contrato no disponible.")
    unit = owned_unit(
        session, uid, expires, context, contract.unit_id, lock=lock
    )
    if lock:
        contract = session.scalar(
            select(WarrantyContract)
            .where(WarrantyContract.id == target)
            .with_for_update()
        )
    return contract, unit


def order_owned(
    session,
    uid: int,
    expires: float,
    context: str,
    target: int,
    lock: bool = False,
):
    authorize(session, uid, expires)
    order = session.scalar(
        select(ServiceOrder).where(ServiceOrder.id == target)
    )
    if not order:
        raise AccessDenied("Order unavailable / Orden no disponible.")
    unit = owned_unit(session, uid, expires, context, order.unit_id, lock=lock)
    if lock:
        order = session.scalar(
            select(ServiceOrder)
            .where(ServiceOrder.id == target)
            .with_for_update()
        )
    return order, unit


def scoped_units(session, uid: int, expires: float, context: str):
    owner = scope_id(session, authorize(session, uid, expires), context)
    query = (
        select(Unit.id)
        .join(Fleet, Unit.fleet_id == Fleet.id)
        .join(ClientOrganization, Fleet.client_id == ClientOrganization.id)
        .where(ClientOrganization.status == "active")
    )
    if owner:
        query = query.where(Fleet.client_id == owner)
    return query


def eligibility(contract, unit, coverage=None) -> bool:
    entries = [contract] if coverage is None else [contract, coverage]
    return (
        contract.status == "active"
        and all(
            (entry.starts_on is None or entry.starts_on <= date.today())
            and (entry.ends_on is None or entry.ends_on >= date.today())
            and (
                entry.mileage_limit_km is None
                or unit.odometer_km <= entry.mileage_limit_km
            )
            and (
                entry.engine_hours_limit is None
                or unit.engine_hours <= entry.engine_hours_limit
            )
            for entry in entries
        )
        and (
            contract.starting_odometer_km is None
            or unit.odometer_km >= contract.starting_odometer_km
        )
        and (
            contract.starting_engine_hours is None
            or unit.engine_hours >= contract.starting_engine_hours
        )
    )


def load_warranty(
    uid: int,
    expires: float,
    context: str,
    search: str,
    status: str,
    expiration: str,
    page: int,
    target: int,
    claim_page: int,
) -> WarrantyData:
    with rx.session() as session:
        owned = scoped_units(session, uid, expires, context)
        query = (
            select(
                WarrantyContract,
                Unit.unit_number,
                ClientOrganization.display_name,
            )
            .join(Unit, WarrantyContract.unit_id == Unit.id)
            .join(Fleet, Unit.fleet_id == Fleet.id)
            .join(ClientOrganization, Fleet.client_id == ClientOrganization.id)
            .where(Unit.id.in_(owned))
        )
        if search.strip():
            term = f"%{search.strip()[:100]}%"
            query = query.where(
                or_(
                    Unit.unit_number.ilike(term),
                    Unit.vin.ilike(term),
                    WarrantyContract.contract_number.ilike(term),
                    WarrantyContract.provider_name.ilike(term),
                )
            )
        if status:
            query = query.where(WarrantyContract.status == status)
        cutoff = day(expiration)
        if cutoff:
            query = query.where(WarrantyContract.ends_on <= cutoff)
        total = int(
            session.scalar(select(func.count()).select_from(query.subquery()))
            or 0
        )
        rows = []
        for c, number, client in session.execute(
            query.order_by(
                WarrantyContract.ends_on.asc().nulls_last(), WarrantyContract.id
            )
            .offset((max(1, page) - 1) * 25)
            .limit(25)
        ):
            row = serialize(c, CONTRACT_FIELDS)
            row.update(unit=number or str(c.unit_id), client=client)
            rows.append(row)
        result: WarrantyData = {
            "rows": rows,
            "total": total,
            "detail": {},
            "coverage": [],
            "claims": [],
            "claim_total": 0,
            "orders": [],
        }
        if not target:
            return result
        c, unit = contract_owned(session, uid, expires, context, target)
        detail = serialize(c, CONTRACT_FIELDS)
        detail.update(
            unit=unit.unit_number or str(unit.id),
            mileage=str(unit.odometer_km),
            hours=str(unit.engine_hours),
            eligible="yes" if eligibility(c, unit) else "no",
        )
        result["detail"] = detail
        for coverage in session.scalars(
            select(WarrantyCoverage)
            .where(WarrantyCoverage.warranty_contract_id == c.id)
            .order_by(WarrantyCoverage.component_code)
            .limit(100)
        ):
            row = serialize(coverage, COVERAGE_FIELDS)
            row["eligible"] = (
                "yes"
                if eligibility(c, unit, coverage)
                and (
                    coverage.parts_coverage_percent > 0
                    or coverage.labor_coverage_percent > 0
                )
                else "no"
            )
            result["coverage"].append(row)
        claims = select(WarrantyClaim).where(
            WarrantyClaim.warranty_contract_id == c.id,
            WarrantyClaim.unit_id == unit.id,
        )
        result["claim_total"] = int(
            session.scalar(select(func.count()).select_from(claims.subquery()))
            or 0
        )
        result["claims"] = [
            serialize(claim, CLAIM_FIELDS)
            for claim in session.scalars(
                claims.order_by(
                    WarrantyClaim.updated_at.desc(), WarrantyClaim.id.desc()
                )
                .offset((max(1, claim_page) - 1) * 20)
                .limit(20)
            )
        ]
        recent_order_ids = (
            select(ServiceOrder.id)
            .where(ServiceOrder.unit_id == unit.id)
            .order_by(ServiceOrder.id.desc())
            .limit(200)
        )
        linked_order_ids = [
            int(claim["service_order_id"])
            for claim in result["claims"]
            if claim["service_order_id"]
        ]
        result["orders"] = [
            serialize(order, ["id", "order_number", "status", "component_code"])
            for order in session.scalars(
                select(ServiceOrder)
                .where(
                    ServiceOrder.unit_id == unit.id,
                    or_(
                        ServiceOrder.id.in_(recent_order_ids),
                        ServiceOrder.id.in_(linked_order_ids),
                    ),
                )
                .order_by(ServiceOrder.id.desc())
                .limit(220)
            )
        ]
        return result


def save_claim(
    uid: int,
    expires: float,
    context: str,
    contract_id: int,
    claim_id: int,
    data: dict[str, str],
) -> int:
    with rx.session() as session:
        contract, unit = contract_owned(
            session, uid, expires, context, contract_id, lock=True
        )
        claim = None
        if claim_id:
            claim = session.scalar(
                select(WarrantyClaim)
                .where(
                    WarrantyClaim.id == claim_id,
                    WarrantyClaim.unit_id == unit.id,
                    WarrantyClaim.warranty_contract_id == contract.id,
                )
                .with_for_update()
            )
            if not claim:
                raise AccessDenied(
                    "Claim unavailable / Reclamación no disponible."
                )
        old_status = claim.status if claim else "draft"
        if (
            claim
            and data.get("updated_at")
            != serialize(claim, ["updated_at"])["updated_at"]
        ):
            raise ValueError(
                "Claim changed. Reload before saving / Reclamación modificada. Recarga antes de guardar."
            )
        status = text_value(data, "status", 30, True)
        if status not in CLAIM_STATES or (
            status != old_status and status not in CLAIM_TRANSITIONS[old_status]
        ):
            raise ValueError(
                "Invalid claim transition / Transición de reclamación inválida."
            )
        requested = money(
            data.get("requested_amount"), "Requested / Solicitado"
        )
        approved = money(data.get("approved_amount"), "Approved / Aprobado")
        paid = money(data.get("paid_amount"), "Paid / Pagado")
        deductible = money(
            data.get("deductible_amount"), "Deductible / Deducible"
        )
        if not paid <= approved <= requested or deductible > requested:
            raise ValueError(
                "Paid ≤ approved ≤ requested; deductible ≤ requested / Pagado ≤ aprobado ≤ solicitado; deducible ≤ solicitado."
            )
        if status in (
            "draft",
            "submitted",
            "under_review",
            "rejected",
            "withdrawn",
        ) and (approved or paid):
            raise ValueError(
                "Unapproved claim cannot have approved/paid amounts / Sin aprobación no hay importes aprobados o pagados."
            )
        if status == "approved" and (approved <= 0 or approved != requested):
            raise ValueError(
                "Full approval requires requested amount / Aprobación total requiere importe solicitado."
            )
        if status == "partially_approved" and not 0 < approved < requested:
            raise ValueError(
                "Partial approval requires 0 < approved < requested / Aprobación parcial inválida."
            )
        if status == "paid" and (paid <= 0 or paid != approved):
            raise ValueError(
                "Paid status requires full approved payment / Estado pagado requiere pago aprobado completo."
            )
        failure = day(data.get("failure_on"))
        if not failure or failure > date.today():
            raise ValueError(
                "Failure date required, not in future / Fecha de fallo requerida, no futura."
            )
        submitted, decided, paid_at = (
            moment(data.get("submitted_at")),
            moment(data.get("decided_at")),
            moment(data.get("paid_at")),
        )
        now = datetime.now(timezone.utc)
        if old_status != status:
            if status == "submitted":
                submitted = submitted or now
            elif status in ("approved", "partially_approved", "rejected"):
                decided = decided or now
            elif status == "paid":
                paid_at = paid_at or now
            elif status == "draft":
                submitted = decided = paid_at = None
        if (
            status
            in (
                "submitted",
                "under_review",
                "approved",
                "partially_approved",
                "rejected",
                "paid",
            )
            and not submitted
        ):
            raise ValueError(
                "Submission date required / Fecha de envío requerida."
            )
        if (
            status in ("approved", "partially_approved", "rejected", "paid")
            and not decided
        ):
            raise ValueError(
                "Decision date required / Fecha de decisión requerida."
            )
        if status == "paid" and not paid_at:
            raise ValueError("Payment date required / Fecha de pago requerida.")
        if (
            any(
                v and (v > now or v.date() < failure)
                for v in (submitted, decided, paid_at)
            )
            or (decided and (not submitted or decided < submitted))
            or (paid_at and (not decided or paid_at < decided))
        ):
            raise ValueError(
                "Dates must follow failure → submission → decision → payment, not future / Fechas fuera de secuencia."
            )
        coverage_id = int(data.get("warranty_coverage_id") or 0)
        coverage = (
            session.scalar(
                select(WarrantyCoverage).where(
                    WarrantyCoverage.id == coverage_id,
                    WarrantyCoverage.warranty_contract_id == contract.id,
                )
            )
            if coverage_id
            else None
        )
        if not coverage:
            raise ValueError(
                "Select a component on this contract / Selecciona componente de este contrato."
            )
        order_id = int(data.get("service_order_id") or 0)
        if order_id:
            order, _ = order_owned(session, uid, expires, context, order_id)
            if order.unit_id != unit.id or (
                order.component_code
                and order.component_code != coverage.component_code
            ):
                raise ValueError(
                    "Order must match unit and component / Orden debe corresponder a unidad y componente."
                )
        description = text_value(data, "failure_description", required=True)
        reason = text_value(data, "decision_reason")
        if (
            status in ("approved", "partially_approved", "rejected", "paid")
            and not reason
        ):
            raise ValueError(
                "Document provider decision/reference; possible coverage is not approval / Documenta decisión del proveedor."
            )
        mileage = money(
            data.get("odometer_km") or unit.odometer_km, "Mileage / Kilometraje"
        )
        hours = money(
            data.get("engine_hours") or unit.engine_hours, "Hours / Horas"
        )
        if not claim:
            claim = WarrantyClaim(
                unit_id=unit.id,
                warranty_contract_id=contract.id,
                claim_number=f"CL-{unit.id}-{now.strftime('%Y%m%d%H%M%S%f')}",
                currency=contract.currency,
            )
            session.add(claim)
        claim.warranty_coverage_id = coverage.id
        claim.component_code = coverage.component_code
        claim.service_order_id = order_id or None
        claim.failure_on = failure
        claim.failure_description = description
        claim.diagnosis = text_value(data, "diagnosis")
        claim.provider_reference = text_value(data, "provider_reference", 100)
        claim.notes = text_value(data, "notes")
        claim.decision_reason = reason
        claim.odometer_km, claim.engine_hours = mileage, hours
        claim.status = status
        (
            claim.requested_amount,
            claim.approved_amount,
            claim.paid_amount,
            claim.deductible_amount,
        ) = requested, approved, paid, deductible
        claim.submitted_at, claim.decided_at, claim.paid_at = (
            submitted,
            decided,
            paid_at,
        )
        session.flush()
        target = claim.id
        session.commit()
        return target


def load_orders(
    uid: int,
    expires: float,
    context: str,
    month: str,
    page: int,
    target: int,
    part_page: int,
    calendar_page: int = 1,
) -> OrdersData:
    first = day(f"{month}-01")
    if not first:
        raise ValueError("Select month / Selecciona mes.")
    next_month = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    start, end = (
        datetime.combine(first, datetime.min.time(), timezone.utc),
        datetime.combine(next_month, datetime.min.time(), timezone.utc),
    )
    with rx.session() as session:
        owned = scoped_units(session, uid, expires, context)
        query = (
            select(
                ServiceOrder, Unit.unit_number, ClientOrganization.display_name
            )
            .join(Unit, Unit.id == ServiceOrder.unit_id)
            .join(Fleet, Fleet.id == Unit.fleet_id)
            .join(ClientOrganization, ClientOrganization.id == Fleet.client_id)
            .where(Unit.id.in_(owned))
        )
        counts = dict(
            session.execute(
                select(ServiceOrder.status, func.count())
                .where(ServiceOrder.unit_id.in_(owned))
                .group_by(ServiceOrder.status)
            ).all()
        )
        ranked = (
            select(
                ServiceOrder.id,
                func.row_number()
                .over(
                    partition_by=ServiceOrder.status,
                    order_by=(
                        ServiceOrder.due_on.asc().nulls_last(),
                        ServiceOrder.id.desc(),
                    ),
                )
                .label("rank"),
            )
            .where(
                ServiceOrder.unit_id.in_(owned),
                ServiceOrder.status.in_(ORDER_STATES),
            )
            .subquery()
        )
        cards = []
        for order, number, client in session.execute(
            query.join(ranked, ranked.c.id == ServiceOrder.id)
            .where(
                ranked.c.rank > (max(1, page) - 1) * 15,
                ranked.c.rank <= max(1, page) * 15,
            )
            .order_by(ServiceOrder.status, ranked.c.rank)
        ):
            row = serialize(
                order,
                [
                    "id",
                    "unit_id",
                    "order_number",
                    "title",
                    "status",
                    "priority",
                    "due_on",
                    "scheduled_start_at",
                    "progress_percent",
                ],
            )
            row.update(unit=number or str(order.unit_id), client=client)
            cards.append(row)
        scheduled = query.where(
            ServiceOrder.scheduled_start_at >= start,
            ServiceOrder.scheduled_start_at < end,
            ServiceOrder.status != "cancelled",
        )
        calendar_total = int(
            session.scalar(
                select(func.count()).select_from(scheduled.subquery())
            )
            or 0
        )
        appointments = []
        for order, number, client in session.execute(
            scheduled.order_by(ServiceOrder.scheduled_start_at, ServiceOrder.id)
            .offset((max(1, calendar_page) - 1) * 500)
            .limit(500)
        ):
            row = serialize(
                order, ["id", "order_number", "status", "scheduled_start_at"]
            )
            row.update(
                unit=number or str(order.unit_id),
                client=client,
                day=order.scheduled_start_at.astimezone(timezone.utc)
                .date()
                .isoformat(),
                time=order.scheduled_start_at.astimezone(timezone.utc).strftime(
                    "%H:%M"
                ),
            )
            appointments.append(row)
        days = []
        for week in calendar.Calendar(firstweekday=0).monthdatescalendar(
            first.year, first.month
        ):
            for d in week:
                days.append(
                    {
                        "date": d.isoformat(),
                        "number": str(d.day),
                        "current": "yes" if d.month == first.month else "no",
                        "today": "yes" if d == date.today() else "no",
                    }
                )
        result: OrdersData = {
            "columns": [
                {"status": s, "count": str(counts.get(s, 0))}
                for s in ORDER_STATES
            ],
            "cards": cards,
            "days": days,
            "calendar_orders": appointments,
            "calendar_total": calendar_total,
            "detail": {},
            "parts": [],
            "part_total": 0,
            "warranties": [],
            "claims": [],
        }
        if not target:
            return result
        order, unit = order_owned(session, uid, expires, context, target)
        detail = serialize(order, ORDER_FIELDS)
        user = authorize(session, uid, expires)
        detail["warranty_eligibility"], detail["warranty_review_notes"] = (
            warranty_review(
                session,
                unit,
                order.component_code or "",
                "",
                order.due_on
                or (
                    order.scheduled_start_at.date()
                    if order.scheduled_start_at
                    else date.today()
                ),
                user.preferred_language,
            )
        )
        detail.update(
            unit=unit.unit_number or str(unit.id),
            estimated=f"{order.estimated_labor_cost + order.estimated_parts_cost + order.estimated_other_cost:.2f}",
            actual=f"{order.actual_labor_cost + order.actual_parts_cost + order.actual_other_cost:.2f}",
            prediction="",
        )
        if order.prediction_id:
            prediction = session.scalar(
                select(ComponentPrediction).where(
                    ComponentPrediction.id == order.prediction_id,
                    ComponentPrediction.unit_id == unit.id,
                )
            )
            if prediction:
                detail["prediction"] = (
                    f"{prediction.component_code} · P30 {float(prediction.failure_probability_30d) * 100:.1f}% / P90 {float(prediction.failure_probability_90d) * 100:.1f}% · {prediction.model_name} · {prediction.predicted_at.isoformat()}"
                )
        result["detail"] = detail
        part_query = select(OrderPart).where(
            OrderPart.service_order_id == order.id
        )
        result["part_total"] = int(
            session.scalar(
                select(func.count()).select_from(part_query.subquery())
            )
            or 0
        )
        result["parts"] = [
            serialize(part, PART_FIELDS)
            for part in session.scalars(
                part_query.order_by(OrderPart.line_number)
                .offset((max(1, part_page) - 1) * 20)
                .limit(20)
            )
        ]
        result["warranties"] = [
            serialize(c, ["id", "contract_number", "status"])
            for c in session.scalars(
                select(WarrantyContract)
                .where(WarrantyContract.unit_id == unit.id)
                .limit(100)
            )
        ]
        result["claims"] = [
            serialize(
                c,
                [
                    "id",
                    "claim_number",
                    "status",
                    "warranty_contract_id",
                    "approved_amount",
                    "paid_amount",
                ],
            )
            for c in session.scalars(
                select(WarrantyClaim)
                .where(
                    WarrantyClaim.service_order_id == order.id,
                    WarrantyClaim.unit_id == unit.id,
                )
                .order_by(WarrantyClaim.id.desc())
                .limit(100)
            )
        ]
        return result


def save_order(
    uid: int, expires: float, context: str, target: int, data: dict[str, str]
) -> None:
    with rx.session() as session:
        order, unit = order_owned(
            session, uid, expires, context, target, lock=True
        )
        if (
            data.get("progress_saved_at", "")
            != serialize(order, ["progress_saved_at"])["progress_saved_at"]
        ):
            raise ValueError(
                "Order changed. Reload before saving / Orden modificada. Recarga antes de guardar."
            )
        status = text_value(data, "status", 30, True)
        if status not in ORDER_TRANSITIONS or (
            status != order.status
            and status not in ORDER_TRANSITIONS[order.status]
        ):
            raise ValueError(
                "Invalid order transition / Transición de orden inválida."
            )
        progress = int(data.get("progress_percent") or "0")
        if not 0 <= progress <= 100:
            raise ValueError("Progress must be 0–100 / Avance debe ser 0–100.")
        scheduled_start, scheduled_end = (
            moment(data.get("scheduled_start_at")),
            moment(data.get("scheduled_end_at")),
        )
        due = day(data.get("due_on"))
        if scheduled_end and (
            not scheduled_start or scheduled_end < scheduled_start
        ):
            raise ValueError(
                "Schedule end must follow start / Fin debe seguir inicio."
            )
        if due and scheduled_start and due < scheduled_start.date():
            raise ValueError(
                "Due date precedes scheduled service / Fecha límite anterior al servicio."
            )
        technician = text_value(data, "assigned_technician", 160)
        workshop = text_value(data, "workshop_name", 160)
        if status in (
            "scheduled",
            "in_progress",
            "awaiting_parts",
            "completed",
        ) and (not scheduled_start or not workshop or not technician):
            raise ValueError(
                "Schedule, workshop and technician required / Programa fecha, taller y técnico."
            )
        if status == "completed":
            if progress != 100:
                raise ValueError(
                    "Completion requires 100% progress / Completar requiere 100% de avance."
                )
            pending = session.scalar(
                select(func.count())
                .select_from(OrderPart)
                .where(
                    OrderPart.service_order_id == order.id,
                    OrderPart.status != "cancelled",
                    OrderPart.quantity_installed < OrderPart.quantity_required,
                )
            )
            if pending:
                raise ValueError(
                    "Install or cancel all required parts before completion / Instala o cancela piezas pendientes."
                )
        if (
            order.status in ("completed", "cancelled")
            and status != order.status
        ):
            raise ValueError("Closed order / Orden cerrada.")
        now = datetime.now(timezone.utc)
        if status == "in_progress" and not order.started_at:
            order.started_at = now
        if status == "completed":
            order.completed_at = order.completed_at or now
            if not order.started_at:
                order.started_at = now
        if status == "cancelled":
            reason = text_value(data, "cancellation_reason", required=True)
            order.cancelled_at, order.cancellation_reason = now, reason
        order.status, order.progress_percent = status, progress
        order.scheduled_start_at, order.scheduled_end_at, order.due_on = (
            scheduled_start,
            scheduled_end,
            due,
        )
        order.assigned_technician, order.workshop_name = technician, workshop
        order.current_step = text_value(data, "current_step", 160)
        order.progress_notes = text_value(data, "progress_notes")
        order.progress_saved_at = now
        for field in [
            "estimated_labor_cost",
            "estimated_parts_cost",
            "estimated_other_cost",
            "actual_labor_cost",
            "actual_parts_cost",
            "actual_other_cost",
        ]:
            setattr(order, field, money(data.get(field), field))
        if order.prediction_id and not session.scalar(
            select(ComponentPrediction.id).where(
                ComponentPrediction.id == order.prediction_id,
                ComponentPrediction.unit_id == unit.id,
            )
        ):
            raise AccessDenied(
                "Prediction does not belong to unit / Predicción ajena a unidad."
            )
        user = authorize(session, uid, expires)
        order.warranty_eligibility, order.warranty_review_notes = (
            warranty_review(
                session,
                unit,
                order.component_code or "",
                "",
                due
                or (
                    scheduled_start.date() if scheduled_start else date.today()
                ),
                user.preferred_language,
            )
        )
        session.commit()


def save_part(
    uid: int,
    expires: float,
    context: str,
    target: int,
    part_id: int,
    data: dict[str, str],
) -> None:
    with rx.session() as session:
        order, unit = order_owned(
            session, uid, expires, context, target, lock=True
        )
        if order.status in ("completed", "cancelled"):
            raise ValueError(
                "Closed order cannot change parts / Orden cerrada no permite cambios de piezas."
            )
        part = None
        if part_id:
            part = session.scalar(
                select(OrderPart)
                .where(
                    OrderPart.id == part_id,
                    OrderPart.service_order_id == order.id,
                )
                .with_for_update()
            )
            if not part:
                raise AccessDenied(
                    "Part unavailable on this order / Pieza ajena a orden."
                )
        quantities = {
            field: money(data.get(field), field, 3)
            for field in [
                "quantity_required",
                "quantity_ordered",
                "quantity_received",
                "quantity_installed",
            ]
        }
        if (
            quantities["quantity_required"] <= 0
            or not quantities["quantity_installed"]
            <= quantities["quantity_received"]
            <= quantities["quantity_ordered"]
        ):
            raise ValueError(
                "Required > 0; installed ≤ received ≤ ordered / Requerido > 0; instalado ≤ recibido ≤ pedido."
            )
        number = text_value(data, "part_number", 100, True)
        description = text_value(data, "description", 200, True)
        expected = day(data.get("expected_on"))
        estimated = money(data.get("estimated_unit_cost"))
        actual = (
            money(data.get("actual_unit_cost"))
            if data.get("actual_unit_cost", "").strip()
            else None
        )
        status = data.get("status", "needed")
        if status not in (
            "needed",
            "ordered",
            "partially_received",
            "received",
            "installed",
            "cancelled",
        ):
            raise ValueError("Invalid part status / Estado de pieza inválido.")
        required, ordered, received, installed = (
            quantities[k]
            for k in [
                "quantity_required",
                "quantity_ordered",
                "quantity_received",
                "quantity_installed",
            ]
        )
        inferred = (
            "installed"
            if installed >= required
            else "received"
            if received >= required
            else "partially_received"
            if received > 0
            else "ordered"
            if ordered > 0
            else "needed"
        )
        if status != "cancelled" and status != inferred:
            raise ValueError(
                f"Status must match quantities / Estado debe coincidir con cantidades: {inferred}."
            )
        now = datetime.now(timezone.utc)
        if not part:
            line = (
                int(
                    session.scalar(
                        select(
                            func.coalesce(func.max(OrderPart.line_number), 0)
                        ).where(OrderPart.service_order_id == order.id)
                    )
                    or 0
                )
                + 1
            )
            part = OrderPart(service_order_id=order.id, line_number=line)
            session.add(part)
        part.part_number, part.description = number, description
        part.supplier_name = text_value(data, "supplier_name", 160)
        part.component_code = (
            text_value(data, "component_code", 80) or order.component_code
        )
        part.notes = text_value(data, "notes")
        for field, value in quantities.items():
            setattr(part, field, value)
        part.estimated_unit_cost, part.actual_unit_cost = estimated, actual
        part.expected_on, part.status = expected, status
        if ordered:
            part.ordered_at = part.ordered_at or now
        if received:
            part.received_at = part.received_at or now
        if installed:
            part.installed_at = part.installed_at or now
        order.progress_saved_at = now
        session.commit()


def user_preferences(
    uid: int, expires: float, language: str = "", theme: str = ""
) -> tuple[str, str]:
    with rx.session() as session:
        user = authorize(session, uid, expires)
        if language or theme:
            if language not in ("es", "en") or theme not in ("light", "dark"):
                raise ValueError("Invalid preference / Preferencia inválida.")
            user.preferred_language, user.preferred_theme = language, theme
            session.commit()
        return user.preferred_language, user.preferred_theme
