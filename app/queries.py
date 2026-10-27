import reflex as rx

from datetime import datetime, timedelta, timezone
from typing import TypedDict
from zoneinfo import ZoneInfo
from sqlalchemy import select, func, or_
from app.models import (
    AppUser,
    ClientOrganization,
    Fleet,
    Unit,
    ComponentPrediction,
    ServiceOrder,
    ServiceRecord,
)
from app.security import authorize, scope_id


class Summary(TypedDict):
    name: str
    role: str
    context: str
    title: str
    clients: list[dict[str, str]]
    accounts: list[dict[str, str]]
    active: int
    high_risk: int
    overdue: int
    cost: float
    unit_count: int
    actions: list[dict[str, str]]
    dates: list[str]
    risk30: list[float]
    risk90: list[float]
    updated: str
    language: str
    theme: str


def load_summary(user_id: int, expires: float, context: str) -> Summary:
    now = datetime.now(timezone.utc)
    with rx.session() as session:
        user = authorize(session, user_id, expires)
        client_id = scope_id(session, user, context)
        org_query = select(ClientOrganization).where(
            ClientOrganization.status == "active"
        )
        if client_id:
            org_query = org_query.where(ClientOrganization.id == client_id)
        orgs = session.scalars(
            org_query.order_by(ClientOrganization.display_name)
        ).all()
        org_ids = [org.id for org in orgs]
        local_now = now.astimezone(
            ZoneInfo(orgs[0].timezone if orgs else "America/Mexico_City")
        )
        owned_query = (
            select(Unit.id)
            .join(Fleet, Unit.fleet_id == Fleet.id)
            .where(Fleet.client_id.in_(org_ids))
        )
        owned_ids = list(session.scalars(owned_query))
        unit_ids = list(
            session.scalars(owned_query.where(Unit.status != "retired"))
        )
        active = (
            session.scalar(
                select(func.count(Unit.id)).where(
                    Unit.id.in_(unit_ids), Unit.status == "active"
                )
            )
            or 0
        )
        overdue = (
            session.scalar(
                select(func.count(ServiceOrder.id)).where(
                    ServiceOrder.unit_id.in_(owned_ids),
                    ServiceOrder.status.not_in(["completed", "cancelled"]),
                    or_(
                        ServiceOrder.due_on < local_now.date(),
                        ServiceOrder.scheduled_start_at < now,
                    ),
                )
            )
            or 0
        )
        # Service records are the accounting source; linked orders are not counted twice.
        month_start = local_now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ).astimezone(timezone.utc)
        cost = session.scalar(
            select(
                func.coalesce(
                    func.sum(
                        ServiceRecord.labor_cost
                        + ServiceRecord.parts_cost
                        + ServiceRecord.other_cost
                    ),
                    0,
                )
            ).where(
                ServiceRecord.unit_id.in_(owned_ids),
                ServiceRecord.status.in_(["completed", "verified"]),
                ServiceRecord.performed_at >= month_start,
                ServiceRecord.performed_at <= now,
                ServiceRecord.currency == "MXN",
            )
        )
        latest = (
            select(
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
            )
            .where(
                ComponentPrediction.unit_id.in_(unit_ids),
                ComponentPrediction.predicted_at <= now,
            )
            .subquery()
        )
        prediction_query = (
            select(
                ComponentPrediction,
                Unit.unit_number,
                ClientOrganization.display_name,
            )
            .join(latest, latest.c.id == ComponentPrediction.id)
            .join(Unit, Unit.id == ComponentPrediction.unit_id)
            .join(Fleet, Fleet.id == Unit.fleet_id)
            .join(ClientOrganization, ClientOrganization.id == Fleet.client_id)
            .where(
                latest.c.rank == 1,
                or_(
                    ComponentPrediction.valid_until.is_(None),
                    ComponentPrediction.valid_until >= now,
                ),
            )
            .order_by(ComponentPrediction.failure_probability_30d.desc())
        )
        rows = session.execute(prediction_query).all()
        high_risk = len(
            {
                p.unit_id
                for p, _, _ in rows
                if p.risk_level in ("high", "critical")
            }
        )
        actions = []
        for prediction, number, org in rows:
            if prediction.risk_level not in ("high", "critical"):
                continue
            actions.append(
                {
                    "id": str(prediction.id),
                    "unit": number or str(prediction.unit_id),
                    "organization": org,
                    "action": (
                        prediction.recommended_action_en
                        if user.preferred_language == "en"
                        else prediction.recommended_action_es
                    )
                    or (
                        "Schedule component inspection"
                        if user.preferred_language == "en"
                        else "Programar revisión de componente"
                    ),
                    "risk": "Crítico"
                    if prediction.risk_level == "critical"
                    else "Alto",
                    "probability": f"{float(prediction.failure_probability_30d) * 100:.1f}%",
                    "due": prediction.recommended_by.strftime("%d/%m/%Y")
                    if prediction.recommended_by
                    else "Sin fecha",
                    "cost": f"${float(prediction.estimated_repair_cost or 0):,.2f}",
                    "url": f"/units/{prediction.unit_id}",
                }
            )
        dates, risk30, risk90 = [], [], []
        for week in range(8):
            cutoff = now - timedelta(weeks=7 - week)
            ranked = (
                select(
                    ComponentPrediction.failure_probability_30d.label("p30"),
                    ComponentPrediction.failure_probability_90d.label("p90"),
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
                )
                .where(
                    ComponentPrediction.unit_id.in_(unit_ids),
                    ComponentPrediction.predicted_at <= cutoff,
                )
                .subquery()
            )
            average = session.execute(
                select(func.avg(ranked.c.p30), func.avg(ranked.c.p90)).where(
                    ranked.c.rank == 1
                )
            ).one()
            if average[0] is not None:
                dates.append(cutoff.strftime("%d/%m"))
                risk30.append(round(float(average[0]) * 100, 2))
                risk90.append(round(float(average[1]) * 100, 2))
        clients, accounts = [], []
        if user.role == "admin":
            clients = [
                {"id": str(org.id), "name": org.display_name}
                for org in session.scalars(
                    select(ClientOrganization)
                    .where(ClientOrganization.status == "active")
                    .order_by(ClientOrganization.display_name)
                )
            ]
            account_query = (
                select(AppUser, ClientOrganization.display_name)
                .join(
                    ClientOrganization,
                    AppUser.client_id == ClientOrganization.id,
                )
                .where(
                    AppUser.role == "client", ClientOrganization.id.in_(org_ids)
                )
            )
            accounts = [
                {
                    "id": str(account.id),
                    "name": account.display_name,
                    "email": account.email or "",
                    "organization": org_name,
                    "status": "Activa" if account.is_active else "Suspendida",
                }
                for account, org_name in session.execute(
                    account_query.order_by(AppUser.created_at.desc())
                )
            ]
        return {
            "language": user.preferred_language,
            "theme": user.preferred_theme,
            "name": user.display_name,
            "role": user.role,
            "context": str(client_id) if client_id else "network",
            "title": orgs[0].display_name
            if client_id and orgs
            else "Resumen de la red",
            "clients": clients,
            "accounts": accounts,
            "active": active,
            "high_risk": high_risk,
            "overdue": overdue,
            "cost": float(cost or 0),
            "unit_count": len(unit_ids),
            "actions": actions[:8],
            "dates": dates,
            "risk30": risk30,
            "risk90": risk90,
            "updated": now.strftime("%d/%m/%Y · %H:%M UTC"),
        }
