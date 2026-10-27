import reflex as rx

from app.components.layout import shell
from app.components.operations_ui import (
    choice,
    empty_message,
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
from app.states.orders_state import OrdersState

ORDER_COSTS = [
    {"label": "Mano de obra estimada", "key": "estimated_labor_cost"},
    {"label": "Piezas estimadas", "key": "estimated_parts_cost"},
    {"label": "Otros estimados", "key": "estimated_other_cost"},
    {"label": "Mano de obra real", "key": "actual_labor_cost"},
    {"label": "Piezas reales", "key": "actual_parts_cost"},
    {"label": "Otros reales", "key": "actual_other_cost"},
]
PART_QUANTITIES = [
    {"label": "Cantidad requerida", "key": "quantity_required"},
    {"label": "Cantidad pedida", "key": "quantity_ordered"},
    {"label": "Cantidad recibida", "key": "quantity_received"},
    {"label": "Cantidad instalada", "key": "quantity_installed"},
]


def calendar_day(d: dict[str, str]) -> rx.Component:
    return rx.el.div(
        rx.el.p(
            d["number"],
            class_name=rx.cond(
                d["today"] == "yes",
                "mb-2 flex h-6 w-6 items-center justify-center rounded-full bg-[#187C72] text-xs font-bold text-white",
                "mb-2 text-xs text-gray-500",
            ),
        ),
        rx.foreach(
            OrdersState.calendar_orders,
            lambda order: rx.cond(
                order["day"] == d["date"],
                rx.el.button(
                    rx.el.p(
                        f"{order['time']} · {order['unit']}",
                        class_name="font-semibold",
                    ),
                    rx.el.p(order["order_number"], class_name="truncate"),
                    rx.el.p(translate(order["status"])),
                    on_click=lambda: OrdersState.select_order(order["id"]),
                    key=order["id"],
                    class_name="mb-1 w-full min-w-0 rounded-md border border-[#187C72]/20 bg-[#187C72]/10 px-2 py-1.5 text-left text-[10px] text-[#187C72] hover:bg-[#187C72]/20 focus-visible:outline-2 focus-visible:outline-[#187C72]",
                ),
            ),
        ),
        key=d["date"],
        class_name=rx.cond(
            d["current"] == "yes",
            "min-h-28 min-w-0 border-b border-r border-gray-200 bg-white p-2",
            "min-h-28 min-w-0 border-b border-r border-gray-200 bg-gray-50 p-2",
        ),
    )


def service_calendar() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.h2(
                translate("Calendario · UTC"),
                class_name="text-base font-semibold text-[#182321]",
            ),
            rx.el.div(
                rx.el.button(
                    rx.icon("chevron-left", class_name="h-4 w-4"),
                    aria_label=translate("Anterior"),
                    on_click=lambda: OrdersState.move_month(-1),
                    disabled=OrdersState.loading,
                    class_name="rounded-lg border border-gray-200 bg-white p-2 text-[#182321] focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
                ),
                rx.el.form(
                    field("Mes", "month", OrdersState.month, "month", True),
                    save_button("Ver mes", OrdersState.loading),
                    on_submit=OrdersState.change_month,
                    class_name="flex items-end gap-2",
                ),
                rx.el.button(
                    rx.icon("chevron-right", class_name="h-4 w-4"),
                    aria_label=translate("Siguiente"),
                    on_click=lambda: OrdersState.move_month(1),
                    disabled=OrdersState.loading,
                    class_name="rounded-lg border border-gray-200 bg-white p-2 text-[#182321] focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
                ),
                class_name="flex items-end gap-2",
            ),
            class_name="flex flex-wrap items-center justify-between gap-4 p-5",
        ),
        rx.el.div(
            rx.el.div(
                rx.foreach(
                    ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
                    lambda label: rx.el.p(
                        translate(label),
                        class_name="bg-gray-50 px-2 py-3 text-xs font-medium text-gray-500",
                    ),
                ),
                rx.foreach(OrdersState.days, calendar_day),
                class_name="grid min-w-[720px] grid-cols-7 border-l border-t border-gray-200",
            ),
            class_name="w-full overflow-x-auto",
        ),
        rx.cond(
            OrdersState.calendar_total == 0,
            rx.el.div(
                empty_message("No hay servicios programados en este mes."),
                class_name="p-4",
            ),
        ),
        rx.el.p(
            rx.cond(
                AccessState.language == "en",
                f"{OrdersState.calendar_total} scheduled services · UTC · 500 per page",
                f"{OrdersState.calendar_total} servicios programados · UTC · 500 por página",
            ),
            class_name="p-4 text-xs text-gray-500",
        ),
        rx.cond(
            OrdersState.calendar_pages > 1,
            rx.el.div(
                rx.el.button(
                    translate("Anterior"),
                    on_click=lambda: OrdersState.paginate("calendar", -1),
                    disabled=(OrdersState.calendar_page <= 1)
                    | OrdersState.loading,
                    class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#182321] focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
                ),
                rx.el.span(
                    f"{OrdersState.calendar_page} / {OrdersState.calendar_pages}",
                    class_name="text-xs text-gray-500",
                ),
                rx.el.button(
                    translate("Siguiente"),
                    on_click=lambda: OrdersState.paginate("calendar", 1),
                    disabled=(
                        OrdersState.calendar_page >= OrdersState.calendar_pages
                    )
                    | OrdersState.loading,
                    class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#182321] focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
                ),
                class_name="flex items-center justify-between gap-3 px-4 pb-4",
            ),
        ),
        class_name="w-full rounded-xl border border-gray-200 bg-white",
    )


def order_card(order: dict[str, str]) -> rx.Component:
    return rx.el.button(
        rx.el.p(
            order["order_number"],
            class_name="text-xs font-semibold text-[#187C72]",
        ),
        rx.el.p(
            translate(order["title"]),
            class_name="mt-2 text-sm font-medium text-[#182321]",
        ),
        rx.el.p(
            f"{order['unit']} · {order['client']}",
            class_name="mt-2 text-xs text-gray-600",
        ),
        rx.el.div(
            status_badge(order["priority"]),
            rx.el.span(
                f"{order['progress_percent']}%",
                class_name="text-xs text-gray-600",
            ),
            class_name="mt-3 flex items-center justify-between gap-2",
        ),
        rx.el.p(
            translate("Fecha límite"),
            ": ",
            order["due_on"],
            class_name="mt-2 text-xs text-gray-500",
        ),
        rx.el.p(
            order["scheduled_start_at"], class_name="mt-1 text-xs text-gray-500"
        ),
        on_click=lambda: OrdersState.select_order(order["id"]),
        key=order["id"],
        class_name=rx.cond(
            OrdersState.selected.to_string() == order["id"],
            "w-full rounded-lg border-2 border-[#187C72] bg-white p-4 text-left focus-visible:outline-2 focus-visible:outline-[#187C72]",
            "w-full rounded-lg border border-gray-200 bg-white p-4 text-left hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-[#187C72]",
        ),
    )


def board_column(column: dict[str, str]) -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.h3(
                translate(column["status"]),
                class_name="text-xs font-semibold text-[#182321]",
            ),
            rx.el.span(
                column["count"],
                class_name="w-fit rounded-md bg-white px-2 py-1 text-xs text-gray-600",
            ),
            class_name="mb-3 flex items-center justify-between gap-2",
        ),
        rx.cond(
            OrdersState.cards_by_status[column["status"]].length() > 0,
            rx.el.div(
                rx.foreach(
                    OrdersState.cards_by_status[column["status"]], order_card
                ),
                class_name="flex flex-col gap-3",
            ),
            empty_message("No hay órdenes en esta columna."),
        ),
        class_name="min-w-0 rounded-xl border border-gray-200 bg-gray-50 p-3",
    )


def status_board() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.h2(
                translate("Tablero de estado"),
                class_name="text-base font-semibold text-[#182321]",
            ),
            rx.el.a(
                translate("Unidades"),
                href="/units",
                class_name="text-xs text-[#187C72] hover:underline focus-visible:outline-2 focus-visible:outline-[#187C72]",
            ),
            class_name="mb-3 flex justify-between",
        ),
        rx.el.p(
            translate(
                "Las órdenes se crean desde una recomendación en la unidad."
            ),
            class_name="mb-4 text-xs text-gray-500",
        ),
        rx.el.div(
            rx.foreach(OrdersState.columns, board_column),
            class_name="grid w-full grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5",
        ),
        rx.el.div(
            rx.el.button(
                "Anterior",
                on_click=lambda: OrdersState.paginate("board", -1),
                disabled=(OrdersState.page <= 1) | OrdersState.loading,
                class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#182321] focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
            ),
            rx.el.p(
                rx.cond(
                    AccessState.language == "en",
                    f"{OrdersState.page} / {OrdersState.board_pages} · 15 cards per column",
                    f"{OrdersState.page} / {OrdersState.board_pages} · 15 órdenes por columna",
                ),
                class_name="text-xs text-gray-500",
            ),
            rx.el.button(
                "Siguiente",
                on_click=lambda: OrdersState.paginate("board", 1),
                disabled=(OrdersState.page >= OrdersState.board_pages)
                | OrdersState.loading,
                class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#182321] focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
            ),
            class_name="mt-4 flex items-center justify-between gap-3",
        ),
        class_name="mt-6 w-full min-w-0",
    )


def part_card(p: dict[str, str]) -> rx.Component:
    return rx.el.article(
        rx.el.div(
            rx.el.p(
                f"{p['line_number']} · {p['part_number']} · {p['description']}",
                class_name="text-sm font-medium text-[#182321]",
            ),
            status_badge(p["status"]),
            rx.el.button(
                translate("Editar"),
                on_click=lambda: OrdersState.edit_part(p["id"]),
                disabled=OrdersState.busy
                | (OrdersState.detail["status"] == "completed")
                | (OrdersState.detail["status"] == "cancelled"),
                class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#187C72] focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
            ),
            class_name="flex flex-wrap items-center justify-between gap-3",
        ),
        rx.el.dl(
            rx.foreach(
                PART_QUANTITIES, lambda f: fact(f["label"], p[f["key"]])
            ),
            class_name="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4",
        ),
        rx.el.p(p["supplier_name"], class_name="mt-3 text-xs text-gray-600"),
        rx.el.dl(
            fact("Costo unitario estimado", p["estimated_unit_cost"]),
            fact("Costo unitario real", p["actual_unit_cost"]),
            fact("Fecha esperada", p["expected_on"]),
            class_name="mt-3 grid grid-cols-3 gap-3",
        ),
        rx.el.p(p["notes"], class_name="mt-2 text-xs text-gray-500"),
        key=p["id"],
        class_name="rounded-lg border border-gray-200 bg-gray-50 p-4",
    )


def part_editor() -> rx.Component:
    return rx.el.form(
        field(
            "Número de pieza",
            "part_number",
            OrdersState.part_draft["part_number"],
            required=True,
        ),
        field(
            "Descripción",
            "description",
            OrdersState.part_draft["description"],
            required=True,
        ),
        field(
            "Proveedor",
            "supplier_name",
            OrdersState.part_draft["supplier_name"],
        ),
        field(
            "Componente",
            "component_code",
            OrdersState.part_draft["component_code"],
        ),
        rx.foreach(
            PART_QUANTITIES,
            lambda f: field(
                f["label"],
                f["key"],
                OrdersState.part_draft[f["key"]],
                "number",
                True,
                "0.001",
            ),
        ),
        field(
            "Costo unitario estimado",
            "estimated_unit_cost",
            OrdersState.part_draft["estimated_unit_cost"],
            "number",
            True,
        ),
        field(
            "Costo unitario real",
            "actual_unit_cost",
            OrdersState.part_draft["actual_unit_cost"],
            "number",
        ),
        field(
            "Fecha esperada",
            "expected_on",
            OrdersState.part_draft["expected_on"],
            "date",
        ),
        choice(
            "Estado",
            "status",
            [
                "needed",
                "ordered",
                "partially_received",
                "received",
                "installed",
                "cancelled",
            ],
            OrdersState.part_draft["status"],
            "part",
        ),
        notes_field("Notas", "notes", OrdersState.part_draft["notes"]),
        rx.el.p(
            translate(
                "Pedido ≥ recibido ≥ instalado. El estado debe coincidir con las cantidades."
            ),
            class_name="text-xs text-gray-500 md:col-span-2",
        ),
        rx.el.div(
            save_button(
                "Guardar pieza", OrdersState.busy | OrdersState.loading
            ),
            rx.el.button(
                translate("Cancelar edición"),
                type="button",
                on_click=OrdersState.close_part,
                class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#182321] focus-visible:outline-2 focus-visible:outline-[#187C72]",
            ),
            class_name="flex gap-3 md:col-span-2",
        ),
        on_submit=OrdersState.submit_part,
        key=f"part-{OrdersState.part_id}",
        class_name="mt-5 grid grid-cols-1 gap-4 rounded-xl border border-[#187C72]/30 bg-white p-5 md:grid-cols-2",
    )


def parts_panel() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.h2(
                translate("Piezas de la orden"),
                class_name="text-base font-semibold text-[#182321]",
            ),
            rx.el.button(
                translate("Agregar pieza"),
                on_click=OrdersState.new_part,
                disabled=OrdersState.busy
                | (OrdersState.detail["status"] == "completed")
                | (OrdersState.detail["status"] == "cancelled"),
                class_name="rounded-lg bg-[#187C72] px-3 py-2 text-xs font-semibold text-white focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
            ),
            class_name="mb-4 flex justify-between gap-3",
        ),
        rx.cond(
            OrdersState.parts.length() > 0,
            rx.el.div(
                rx.foreach(OrdersState.parts, part_card),
                class_name="flex flex-col gap-3",
            ),
            empty_message("Sin piezas registradas."),
        ),
        rx.el.div(
            rx.el.button(
                "Anterior",
                on_click=lambda: OrdersState.paginate("parts", -1),
                disabled=(OrdersState.part_page <= 1) | OrdersState.loading,
                class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#182321] focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
            ),
            rx.el.span(
                f"{OrdersState.part_page} · {OrdersState.part_total}",
                class_name="text-xs text-gray-500",
            ),
            rx.el.button(
                "Siguiente",
                on_click=lambda: OrdersState.paginate("parts", 1),
                disabled=(OrdersState.part_page * 20 >= OrdersState.part_total)
                | OrdersState.loading,
                class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#182321] focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
            ),
            class_name="mt-4 flex items-center justify-between",
        ),
        rx.cond(OrdersState.editing_part, part_editor()),
        class_name="mt-5 rounded-xl border border-gray-200 bg-white p-5",
    )


def order_detail() -> rx.Component:
    return rx.el.div(
        rx.el.section(
            rx.el.div(
                rx.el.h2(
                    OrdersState.detail["order_number"],
                    class_name="text-lg font-semibold text-[#182321]",
                ),
                status_badge(OrdersState.detail["status"]),
                class_name="flex flex-wrap items-center justify-between gap-3",
            ),
            rx.el.p(
                translate(OrdersState.detail["title"]),
                class_name="mt-2 text-sm text-gray-600",
            ),
            rx.el.a(
                OrdersState.detail["unit"],
                href=f"/units/{OrdersState.detail['unit_id']}",
                class_name="mt-2 inline-flex text-sm text-[#187C72] hover:underline focus-visible:outline-2 focus-visible:outline-[#187C72]",
            ),
            rx.el.p(
                translate(OrdersState.detail["description"]),
                class_name="mt-3 text-sm text-gray-600",
            ),
            rx.el.dl(
                fact(
                    "Costo estimado",
                    f"{OrdersState.detail['estimated']} {OrdersState.detail['currency']}",
                ),
                fact(
                    "Costo real",
                    f"{OrdersState.detail['actual']} {OrdersState.detail['currency']}",
                ),
                class_name="my-5 grid grid-cols-2 gap-4",
            ),
            rx.el.form(
                rx.el.input(
                    type="hidden",
                    name="progress_saved_at",
                    default_value=OrdersState.detail["progress_saved_at"],
                    key=OrdersState.detail["progress_saved_at"],
                ),
                choice(
                    "Estado",
                    "status",
                    OrdersState.order_status_options,
                    OrdersState.detail["status"],
                ),
                field(
                    "Avance (%)",
                    "progress_percent",
                    OrdersState.detail["progress_percent"],
                    "number",
                    True,
                    "1",
                ),
                field(
                    "Programado inicio (UTC)",
                    "scheduled_start_at",
                    OrdersState.detail["scheduled_start_at"],
                    "datetime-local",
                ),
                field(
                    "Programado fin (UTC)",
                    "scheduled_end_at",
                    OrdersState.detail["scheduled_end_at"],
                    "datetime-local",
                ),
                field(
                    "Fecha límite",
                    "due_on",
                    OrdersState.detail["due_on"],
                    "date",
                ),
                field(
                    "Técnico",
                    "assigned_technician",
                    OrdersState.detail["assigned_technician"],
                ),
                field(
                    "Taller",
                    "workshop_name",
                    OrdersState.detail["workshop_name"],
                ),
                field(
                    "Paso actual",
                    "current_step",
                    OrdersState.detail["current_step"],
                ),
                rx.foreach(
                    ORDER_COSTS,
                    lambda f: field(
                        f["label"],
                        f["key"],
                        OrdersState.detail[f["key"]],
                        "number",
                        True,
                    ),
                ),
                notes_field(
                    "Notas de avance",
                    "progress_notes",
                    OrdersState.detail["progress_notes"],
                ),
                notes_field("Motivo de cancelación", "cancellation_reason"),
                save_button(
                    "Guardar avance", OrdersState.busy | OrdersState.loading
                ),
                on_submit=OrdersState.submit_order,
                key=f"order-{OrdersState.selected}-{OrdersState.detail['progress_saved_at']}",
                class_name="grid grid-cols-1 gap-4 md:grid-cols-2",
            ),
            rx.el.p(
                rx.cond(
                    AccessState.language == "en",
                    f"Last saved (UTC): {OrdersState.detail['progress_saved_at']}",
                    f"Guardado (UTC): {OrdersState.detail['progress_saved_at']}",
                ),
                class_name="mt-4 text-xs text-gray-500",
            ),
            class_name="rounded-xl border border-gray-200 bg-white p-5",
        ),
        rx.el.section(
            rx.el.h2(
                translate("Predicción vinculada"),
                class_name="text-base font-semibold text-[#182321]",
            ),
            rx.cond(
                OrdersState.detail["prediction"] != "",
                rx.el.p(
                    translate(OrdersState.detail["prediction"]),
                    class_name="mt-3 text-xs leading-6 text-gray-600",
                ),
                empty_message("Sin predicción vinculada."),
            ),
            rx.el.h3(
                translate("Contratos de la unidad"),
                class_name="mb-3 mt-5 text-sm font-semibold text-[#182321]",
            ),
            status_badge(OrdersState.detail["warranty_eligibility"]),
            rx.el.p(
                translate(OrdersState.detail["warranty_review_notes"]),
                class_name="my-3 text-xs leading-6 text-gray-600",
            ),
            rx.el.p(
                translate(
                    "La cobertura potencial no es una reclamación aprobada. Verifica exclusiones, mantenimiento y autorización del proveedor."
                ),
                class_name="my-3 text-xs leading-6 text-gray-500",
            ),
            rx.cond(
                OrdersState.warranties.length() > 0,
                rx.el.div(
                    rx.foreach(
                        OrdersState.warranties,
                        lambda c: rx.el.a(
                            c["contract_number"],
                            status_badge(c["status"]),
                            href=f"/warranty?contract={c['id']}",
                            class_name="flex w-fit items-center gap-3 rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#187C72] hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-[#187C72]",
                        ),
                    ),
                    class_name="flex flex-wrap gap-3",
                ),
                empty_message("Sin contratos de garantía registrados."),
            ),
            rx.el.h3(
                translate("Reclamaciones de esta orden"),
                class_name="mb-3 mt-5 text-sm font-semibold text-[#182321]",
            ),
            rx.cond(
                OrdersState.claims.length() > 0,
                rx.el.div(
                    rx.foreach(
                        OrdersState.claims,
                        lambda c: rx.el.a(
                            rx.el.span(c["claim_number"]),
                            status_badge(c["status"]),
                            rx.el.span(
                                translate("Aprobado"),
                                ": ",
                                c["approved_amount"],
                                " · ",
                                translate("Pagado"),
                                ": ",
                                c["paid_amount"],
                            ),
                            href=f"/warranty?contract={c['warranty_contract_id']}",
                            class_name="flex flex-wrap items-center gap-3 rounded-lg border border-gray-200 bg-white p-3 text-xs text-[#187C72] focus-visible:outline-2 focus-visible:outline-[#187C72]",
                        ),
                    ),
                    class_name="flex flex-col gap-3",
                ),
                empty_message("Sin reclamaciones vinculadas."),
            ),
            class_name="mt-5 rounded-xl border border-gray-200 bg-white p-5",
        ),
        parts_panel(),
        class_name="mt-6 w-full min-w-0",
    )


def orders_page() -> rx.Component:
    return shell(
        rx.el.div(
            workspace_header(
                "Órdenes de servicio",
                "Calendario y tablero de servicio",
                OrdersState.refresh,
                OrdersState.loading | OrdersState.busy,
            ),
            workspace_feedback(
                OrdersState.error,
                OrdersState.success,
                OrdersState.loading | OrdersState.busy,
            ),
            rx.cond(
                OrdersState.ready
                & (OrdersState.context == AccessState.context),
                rx.fragment(
                    service_calendar(),
                    status_board(),
                    rx.cond(
                        OrdersState.selected > 0,
                        order_detail(),
                        rx.el.div(
                            empty_message(
                                "Selecciona una orden del calendario o tablero para guardar su avance."
                            ),
                            class_name="mt-6",
                        ),
                    ),
                ),
                rx.cond(
                    OrdersState.loading,
                    rx.el.div(
                        class_name="h-32 animate-pulse rounded-xl bg-gray-200"
                    ),
                    empty_message("Utiliza Actualizar para reintentar."),
                ),
            ),
            class_name="w-full min-w-0",
        )
    )
