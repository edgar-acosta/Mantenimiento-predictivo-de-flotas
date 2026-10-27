import reflex as rx

from app.components.layout import shell
from app.components.operations_ui import (
    choice,
    empty_message,
    entity_choice,
    fact,
    field,
    notes_field,
    save_button,
    status_badge,
    workspace_feedback,
    workspace_header,
)
from app.i18n import translate
from app.states.access_state import AccessState
from app.states.warranty_state import WarrantyState

CONTRACT_FACTS = [
    {"label": "Inicio", "key": "starts_on"},
    {"label": "Fin", "key": "ends_on"},
    {"label": "Km iniciales", "key": "starting_odometer_km"},
    {"label": "Límite km", "key": "mileage_limit_km"},
    {"label": "Horas iniciales", "key": "starting_engine_hours"},
    {"label": "Límite horas", "key": "engine_hours_limit"},
    {"label": "Kilometraje", "key": "mileage"},
    {"label": "Horas motor", "key": "hours"},
    {"label": "Deducible", "key": "deductible"},
    {"label": "Límite de reclamación", "key": "total_claim_limit"},
]
COVERAGE_FACTS = [
    {"label": "Inicio", "key": "starts_on"},
    {"label": "Fin", "key": "ends_on"},
    {"label": "Límite km", "key": "mileage_limit_km"},
    {"label": "Límite horas", "key": "engine_hours_limit"},
    {"label": "Piezas (%)", "key": "parts_coverage_percent"},
    {"label": "Mano de obra (%)", "key": "labor_coverage_percent"},
    {"label": "Deducible", "key": "deductible"},
    {"label": "Límite de reclamación", "key": "claim_limit"},
]
CLAIM_AMOUNTS = [
    {"label": "Solicitado", "key": "requested_amount"},
    {"label": "Aprobado", "key": "approved_amount"},
    {"label": "Pagado", "key": "paid_amount"},
    {"label": "Deducible", "key": "deductible_amount"},
    {"label": "Kilometraje", "key": "odometer_km"},
    {"label": "Horas motor", "key": "engine_hours"},
]


def contract_card(c: dict[str, str]) -> rx.Component:
    return rx.el.button(
        rx.el.div(
            rx.el.span(
                c["contract_number"], class_name="font-semibold text-[#182321]"
            ),
            status_badge(c["status"]),
            class_name="flex flex-wrap items-center justify-between gap-2",
        ),
        rx.el.p(
            f"{c['unit']} · {c['client']}",
            class_name="mt-2 text-xs text-gray-600",
        ),
        rx.el.p(c["provider_name"], class_name="mt-1 text-xs text-gray-500"),
        rx.el.p(
            f"{c['starts_on']} → {c['ends_on']}",
            class_name="mt-2 text-xs text-gray-600",
        ),
        on_click=lambda: WarrantyState.select_contract(c["id"]),
        key=c["id"],
        class_name=rx.cond(
            WarrantyState.selected.to_string() == c["id"],
            "w-full rounded-lg border-2 border-[#187C72] bg-white p-4 text-left focus-visible:outline-2 focus-visible:outline-[#187C72]",
            "w-full rounded-lg border border-gray-200 bg-white p-4 text-left hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-[#187C72]",
        ),
    )


def contract_list() -> rx.Component:
    return rx.el.section(
        rx.el.form(
            field(
                "Buscar unidad, contrato o proveedor",
                "search",
                WarrantyState.search,
            ),
            choice(
                "Estado",
                "status",
                ["", "pending", "active", "expired", "void", "cancelled"],
                WarrantyState.status,
                "contracts",
            ),
            field(
                "Vence antes de", "expiration", WarrantyState.expiration, "date"
            ),
            save_button("Filtrar", WarrantyState.loading | WarrantyState.busy),
            on_submit=WarrantyState.filter_contracts,
            class_name="mb-4 flex flex-col gap-3 rounded-xl border border-gray-200 bg-white p-4",
        ),
        rx.el.p(
            rx.cond(
                AccessState.language == "en",
                f"{WarrantyState.total} contracts · 25 per page",
                f"{WarrantyState.total} contratos · 25 por página",
            ),
            class_name="mb-3 text-xs text-gray-500",
        ),
        rx.cond(
            WarrantyState.rows.length() > 0,
            rx.el.div(
                rx.foreach(WarrantyState.rows, contract_card),
                class_name="flex flex-col gap-3",
            ),
            empty_message("No hay contratos con estos filtros."),
        ),
        rx.el.div(
            rx.el.button(
                translate("Anterior"),
                on_click=lambda: WarrantyState.paginate("contracts", -1),
                disabled=(WarrantyState.page <= 1) | WarrantyState.loading,
                class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#182321] focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
            ),
            rx.el.span(
                f"{WarrantyState.page} / {WarrantyState.page_count}",
                class_name="text-xs text-gray-500",
            ),
            rx.el.button(
                translate("Siguiente"),
                on_click=lambda: WarrantyState.paginate("contracts", 1),
                disabled=(WarrantyState.page >= WarrantyState.page_count)
                | WarrantyState.loading,
                class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#182321] focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
            ),
            class_name="mt-4 flex items-center justify-between gap-2",
        ),
        class_name="w-full min-w-0",
    )


def coverage_card(c: dict[str, str]) -> rx.Component:
    return rx.el.article(
        rx.el.div(
            rx.el.h3(
                translate(c["component_code"]),
                class_name="text-sm font-semibold text-[#182321]",
            ),
            rx.el.span(
                rx.cond(
                    c["eligible"] == "yes",
                    translate("Cobertura potencial"),
                    translate("No elegible al uso/fecha actual"),
                ),
                class_name="w-fit rounded-md bg-[#E5A547]/15 px-2 py-1 text-xs text-[#805410]",
            ),
            class_name="flex flex-wrap justify-between gap-2",
        ),
        rx.el.dl(
            rx.foreach(COVERAGE_FACTS, lambda f: fact(f["label"], c[f["key"]])),
            class_name="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4",
        ),
        rx.el.p(
            translate("Autorización previa"),
            ": ",
            rx.cond(
                c["requires_preapproval"] == "yes",
                translate("Sí"),
                translate("No"),
            ),
            class_name="mt-3 text-xs text-gray-600",
        ),
        rx.el.p(
            translate("Requisitos de mantenimiento"),
            ": ",
            translate(c["maintenance_requirements"]),
            class_name="mt-2 text-xs text-gray-600",
        ),
        rx.el.p(
            translate("Exclusiones"),
            ": ",
            translate(c["exclusions"]),
            class_name="mt-2 text-xs text-gray-500",
        ),
        key=c["id"],
        class_name="rounded-lg border border-gray-200 bg-gray-50 p-4",
    )


def claim_card(c: dict[str, str]) -> rx.Component:
    return rx.el.article(
        rx.el.div(
            rx.el.h3(
                c["claim_number"],
                class_name="text-sm font-semibold text-[#182321]",
            ),
            status_badge(c["status"]),
            rx.el.button(
                translate("Editar"),
                on_click=lambda: WarrantyState.edit_claim(c["id"]),
                disabled=WarrantyState.busy,
                class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#187C72] focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
            ),
            class_name="flex flex-wrap items-center gap-3",
        ),
        rx.el.p(
            f"{c['component_code']} · {c['failure_on']}",
            class_name="mt-2 text-xs text-gray-500",
        ),
        rx.el.p(
            translate(c["failure_description"]),
            class_name="mt-2 text-sm text-gray-600",
        ),
        rx.el.dl(
            fact("Solicitado", f"{c['requested_amount']} {c['currency']}"),
            fact("Aprobado", f"{c['approved_amount']} {c['currency']}"),
            fact("Pagado", f"{c['paid_amount']} {c['currency']}"),
            class_name="mt-3 grid grid-cols-3 gap-3",
        ),
        rx.el.div(
            rx.el.p(translate("Enviado (UTC)"), ": ", c["submitted_at"]),
            rx.el.p(translate("Decidido (UTC)"), ": ", c["decided_at"]),
            rx.el.p(translate("Pagado (UTC)"), ": ", c["paid_at"]),
            class_name="mt-3 flex flex-wrap gap-3 text-xs text-gray-500",
        ),
        rx.el.p(
            translate(c["decision_reason"]),
            class_name="mt-2 text-xs text-gray-600",
        ),
        rx.el.p(translate(c["notes"]), class_name="mt-2 text-xs text-gray-500"),
        rx.cond(
            c["service_order_id"] != "",
            rx.el.a(
                translate("Orden vinculada"),
                href=f"/orders?order={c['service_order_id']}",
                class_name="mt-3 inline-flex text-xs text-[#187C72] hover:underline focus-visible:outline-2 focus-visible:outline-[#187C72]",
            ),
        ),
        key=c["id"],
        class_name="rounded-lg border border-gray-200 bg-white p-4",
    )


def claim_editor() -> rx.Component:
    return rx.el.section(
        rx.el.h3(
            rx.cond(
                WarrantyState.claim_id == 0,
                translate("Nueva reclamación"),
                translate("Editar reclamación"),
            ),
            class_name="mb-4 text-base font-semibold text-[#182321]",
        ),
        rx.el.form(
            rx.el.input(
                type="hidden",
                name="updated_at",
                default_value=WarrantyState.draft["updated_at"],
                key=WarrantyState.draft["updated_at"],
            ),
            entity_choice(
                "Componente",
                "warranty_coverage_id",
                WarrantyState.coverage,
                "component_code",
                WarrantyState.draft["warranty_coverage_id"],
                True,
            ),
            entity_choice(
                "Orden vinculada",
                "service_order_id",
                WarrantyState.orders,
                "order_number",
                WarrantyState.draft["service_order_id"],
            ),
            choice(
                "Estado",
                "status",
                WarrantyState.claim_status_options,
                WarrantyState.draft["status"],
                "claim",
            ),
            field(
                "Fecha de fallo",
                "failure_on",
                WarrantyState.draft["failure_on"],
                "date",
                True,
            ),
            field(
                "Referencia del proveedor",
                "provider_reference",
                WarrantyState.draft["provider_reference"],
            ),
            rx.foreach(
                CLAIM_AMOUNTS,
                lambda f: field(
                    f["label"],
                    f["key"],
                    WarrantyState.draft[f["key"]],
                    "number",
                ),
            ),
            field(
                "Enviado (UTC)",
                "submitted_at",
                WarrantyState.draft["submitted_at"],
                "datetime-local",
            ),
            field(
                "Decidido (UTC)",
                "decided_at",
                WarrantyState.draft["decided_at"],
                "datetime-local",
            ),
            field(
                "Pagado (UTC)",
                "paid_at",
                WarrantyState.draft["paid_at"],
                "datetime-local",
            ),
            notes_field(
                "Descripción del fallo",
                "failure_description",
                WarrantyState.draft["failure_description"],
                True,
            ),
            notes_field(
                "Diagnóstico", "diagnosis", WarrantyState.draft["diagnosis"]
            ),
            notes_field(
                "Decisión del proveedor / motivo",
                "decision_reason",
                WarrantyState.draft["decision_reason"],
            ),
            notes_field("Notas", "notes", WarrantyState.draft["notes"]),
            rx.el.div(
                save_button(
                    "Guardar reclamación",
                    WarrantyState.busy | WarrantyState.loading,
                ),
                rx.el.button(
                    translate("Cancelar edición"),
                    type="button",
                    on_click=WarrantyState.close_editor,
                    class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#182321] focus-visible:outline-2 focus-visible:outline-[#187C72]",
                ),
                class_name="flex flex-wrap gap-3 md:col-span-2",
            ),
            on_submit=WarrantyState.submit_claim,
            key=f"claim-{WarrantyState.claim_id}",
            class_name="grid grid-cols-1 gap-4 md:grid-cols-2",
        ),
        class_name="mt-5 rounded-xl border border-[#187C72]/30 bg-white p-5",
    )


def contract_detail() -> rx.Component:
    return rx.el.div(
        rx.el.section(
            rx.el.div(
                rx.el.h2(
                    WarrantyState.detail["contract_number"],
                    class_name="text-lg font-semibold text-[#182321]",
                ),
                status_badge(WarrantyState.detail["status"]),
                class_name="flex flex-wrap items-center justify-between gap-3",
            ),
            rx.el.p(
                WarrantyState.detail["provider_name"],
                class_name="mt-2 text-sm text-gray-600",
            ),
            rx.el.a(
                WarrantyState.detail["unit"],
                href=f"/units/{WarrantyState.detail['unit_id']}",
                class_name="mt-2 inline-flex text-sm font-medium text-[#187C72] hover:underline focus-visible:outline-2 focus-visible:outline-[#187C72]",
            ),
            rx.el.dl(
                rx.foreach(
                    CONTRACT_FACTS,
                    lambda f: fact(f["label"], WarrantyState.detail[f["key"]]),
                ),
                class_name="mt-5 grid grid-cols-2 gap-4 lg:grid-cols-3",
            ),
            rx.el.p(
                rx.cond(
                    WarrantyState.detail["eligible"] == "yes",
                    translate("Cobertura potencial"),
                    translate("No elegible al uso/fecha actual"),
                ),
                class_name="mt-5 font-medium text-[#805410]",
            ),
            rx.el.p(
                translate(
                    "La cobertura potencial no es una reclamación aprobada. Verifica exclusiones, mantenimiento y autorización del proveedor."
                ),
                class_name="mt-2 text-xs leading-6 text-gray-600",
            ),
            rx.el.dl(
                fact("Términos", WarrantyState.detail["terms"]),
                fact("Exclusiones", WarrantyState.detail["exclusions"]),
                class_name="mt-4 flex flex-col gap-3",
            ),
            class_name="rounded-xl border border-gray-200 bg-white p-5",
        ),
        rx.el.section(
            rx.el.h2(
                translate("Componentes cubiertos"),
                class_name="mb-4 text-base font-semibold text-[#182321]",
            ),
            rx.cond(
                WarrantyState.coverage.length() > 0,
                rx.el.div(
                    rx.foreach(WarrantyState.coverage, coverage_card),
                    class_name="flex flex-col gap-3",
                ),
                empty_message("Sin componentes documentados."),
            ),
            class_name="mt-5 rounded-xl border border-gray-200 bg-white p-5",
        ),
        rx.el.section(
            rx.el.div(
                rx.el.h2(
                    translate("Reclamaciones"),
                    class_name="text-base font-semibold text-[#182321]",
                ),
                rx.el.button(
                    translate("Nueva reclamación"),
                    on_click=WarrantyState.new_claim,
                    disabled=WarrantyState.busy
                    | (WarrantyState.coverage.length() == 0),
                    class_name="rounded-lg bg-[#187C72] px-3 py-2 text-xs font-semibold text-white hover:bg-[#12645C] focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
                ),
                class_name="mb-4 flex items-center justify-between gap-3",
            ),
            rx.cond(
                WarrantyState.claims.length() > 0,
                rx.el.div(
                    rx.foreach(WarrantyState.claims, claim_card),
                    class_name="flex flex-col gap-3",
                ),
                empty_message("Sin reclamaciones para este contrato."),
            ),
            rx.el.div(
                rx.el.button(
                    "Anterior",
                    on_click=lambda: WarrantyState.paginate("claims", -1),
                    disabled=(WarrantyState.claim_page <= 1)
                    | WarrantyState.loading,
                    class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#182321] focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
                ),
                rx.el.span(
                    f"{WarrantyState.claim_page} · {WarrantyState.claim_total}",
                    class_name="text-xs text-gray-500",
                ),
                rx.el.button(
                    "Siguiente",
                    on_click=lambda: WarrantyState.paginate("claims", 1),
                    disabled=(
                        WarrantyState.claim_page * 20
                        >= WarrantyState.claim_total
                    )
                    | WarrantyState.loading,
                    class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#182321] focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
                ),
                class_name="mt-4 flex items-center justify-between",
            ),
            class_name="mt-5 rounded-xl border border-gray-200 bg-white p-5",
        ),
        rx.cond(WarrantyState.editing, claim_editor()),
        class_name="w-full min-w-0",
    )


def warranty_page() -> rx.Component:
    return shell(
        rx.el.div(
            workspace_header(
                "Garantías",
                "Contratos y reclamaciones",
                WarrantyState.refresh,
                WarrantyState.loading | WarrantyState.busy,
            ),
            workspace_feedback(
                WarrantyState.error,
                WarrantyState.success,
                WarrantyState.loading | WarrantyState.busy,
            ),
            rx.cond(
                WarrantyState.ready
                & (WarrantyState.context == AccessState.context),
                rx.el.div(
                    contract_list(),
                    rx.cond(
                        WarrantyState.selected > 0,
                        contract_detail(),
                        empty_message(
                            "Selecciona un contrato para ver cobertura y reclamaciones."
                        ),
                    ),
                    class_name="grid w-full min-w-0 grid-cols-1 items-start gap-6 xl:grid-cols-[320px_minmax(0,1fr)]",
                ),
                rx.cond(
                    WarrantyState.loading,
                    rx.el.div(
                        class_name="h-32 animate-pulse rounded-xl bg-gray-200"
                    ),
                    empty_message("Utiliza Actualizar para reintentar."),
                ),
            ),
            class_name="w-full min-w-0",
        )
    )
