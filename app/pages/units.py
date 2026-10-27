import reflex as rx

from app.components.layout import context_selector, error_banner, shell
from app.components.unit_views import (
    empty,
    evidence_panel,
    fault_row,
    history_pager,
    prediction_card,
    risk_badge,
    service_row,
    telemetry_row,
    warranty_row,
)
from app.states.access_state import AccessState
from app.states.units_state import UnitsState
from app.i18n import translate


def filter_select(
    label: str, name: str, options: list[dict[str, str]], default: rx.Var
) -> rx.Component:
    return rx.el.div(
        rx.el.label(
            translate(label),
            html_for=name,
            class_name="mb-2 block text-xs font-medium text-gray-600",
        ),
        rx.el.div(
            rx.el.select(
                rx.foreach(
                    options,
                    lambda option: rx.el.option(
                        translate(option["label"]), value=option["value"]
                    ),
                ),
                id=name,
                name=name,
                default_value=default,
                key=default,
                class_name="w-full appearance-none rounded-lg border border-gray-200 bg-white py-2.5 pl-3 pr-9 text-xs text-[#182321] focus:outline-2 focus:outline-[#187C72]",
            ),
            rx.icon(
                "chevron-down",
                class_name="pointer-events-none absolute right-3 top-3 h-4 w-4 text-gray-500",
            ),
            class_name="relative",
        ),
        class_name="min-w-0",
    )


def filters() -> rx.Component:
    return rx.el.form(
        rx.el.div(
            rx.el.label(
                translate("Buscar unidad, VIN, placa o modelo"),
                html_for="unit-search",
                class_name="mb-2 block text-xs font-medium text-gray-600",
            ),
            rx.el.input(
                id="unit-search",
                name="search",
                placeholder=translate("Ej. 1001 o Cascadia"),
                default_value=UnitsState.search,
                key=UnitsState.search,
                max_length=100,
                class_name="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-xs text-[#182321] placeholder:text-gray-400 focus:outline-2 focus:outline-[#187C72]",
            ),
            class_name="min-w-0 md:col-span-2 xl:col-span-1",
        ),
        rx.el.div(
            rx.el.label(
                translate("Flota"),
                html_for="fleet",
                class_name="mb-2 block text-xs font-medium text-gray-600",
            ),
            rx.el.div(
                rx.el.select(
                    rx.el.option(translate("Todas las flotas"), value=""),
                    rx.foreach(
                        UnitsState.fleets,
                        lambda f: rx.el.option(f["name"], value=f["id"]),
                    ),
                    id="fleet",
                    name="fleet",
                    default_value=UnitsState.fleet_filter,
                    key=UnitsState.fleet_filter,
                    class_name="w-full appearance-none rounded-lg border border-gray-200 bg-white py-2.5 pl-3 pr-9 text-xs text-[#182321] focus:outline-2 focus:outline-[#187C72]",
                ),
                rx.icon(
                    "chevron-down",
                    class_name="pointer-events-none absolute right-3 top-3 h-4 w-4 text-gray-500",
                ),
                class_name="relative",
            ),
        ),
        filter_select(
            "Riesgo máximo vigente",
            "risk",
            [
                {"label": "Todos los riesgos", "value": ""},
                {"label": "Crítico", "value": "critical"},
                {"label": "Alto", "value": "high"},
                {"label": "Medio", "value": "medium"},
                {"label": "Bajo", "value": "low"},
                {"label": "Sin inferencia vigente", "value": "unknown"},
            ],
            UnitsState.risk_filter,
        ),
        filter_select(
            "Estado contractual",
            "warranty",
            [
                {"label": "Todos los contratos", "value": ""},
                {"label": "Contrato vigente", "value": "covered"},
                {"label": "Sin contrato vigente", "value": "uncovered"},
            ],
            UnitsState.warranty_filter,
        ),
        rx.el.button(
            rx.icon("search", class_name="h-4 w-4"),
            translate("Filtrar"),
            type="submit",
            disabled=UnitsState.loading,
            class_name="flex items-center justify-center gap-2 self-end rounded-lg bg-[#187C72] px-4 py-2.5 text-xs font-semibold text-white hover:bg-[#12665e] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#187C72] disabled:opacity-50",
        ),
        on_submit=UnitsState.filters,
        class_name="mt-6 grid grid-cols-1 gap-4 rounded-xl border border-gray-200 bg-white p-5 md:grid-cols-2 xl:grid-cols-[minmax(180px,1.5fr)_minmax(120px,1fr)_minmax(120px,1fr)_minmax(150px,1fr)_auto]",
    )


def unit_row(u: dict[str, str]) -> rx.Component:
    return rx.el.tr(
        rx.el.td(
            rx.el.a(
                u["number"],
                rx.icon("arrow-up-right", class_name="h-3 w-3"),
                href=f"/units/{u['id']}",
                class_name="flex w-fit items-center gap-2 text-sm font-semibold text-[#187C72] hover:underline focus-visible:outline-2 focus-visible:outline-[#187C72]",
            ),
            rx.el.p(u["plate"], class_name="mt-1 text-xs text-gray-500"),
            class_name="px-4 py-4",
        ),
        rx.el.td(
            rx.el.p(
                u["model"], class_name="text-xs font-medium text-[#182321]"
            ),
            rx.el.p(u["vin"], class_name="mt-1 text-[10px] text-gray-500"),
            class_name="px-4 py-4",
        ),
        rx.el.td(
            rx.el.p(u["fleet"], class_name="text-xs text-gray-700"),
            rx.el.p(u["client"], class_name="mt-1 text-[10px] text-gray-500"),
            class_name="px-4 py-4",
        ),
        rx.el.td(
            rx.el.p(
                u["mileage"],
                class_name="whitespace-nowrap text-xs text-gray-700",
            ),
            rx.el.p(
                translate(u["status"]),
                class_name="mt-1 text-[10px] text-gray-500",
            ),
            class_name="px-4 py-4",
        ),
        rx.el.td(
            risk_badge(u["risk"], u["risk_key"]),
            rx.el.p(
                rx.cond(
                    AccessState.language == "en",
                    f"Max P30 {u['p30']}",
                    f"P30 máx. {u['p30']}",
                ),
                class_name="mt-2 whitespace-nowrap text-[10px] text-gray-500",
            ),
            class_name="px-4 py-4",
        ),
        rx.el.td(
            translate(u["warranty"]),
            class_name="px-4 py-4 text-xs leading-5 text-gray-600",
        ),
        key=u["id"],
        class_name="border-t border-gray-100 bg-white hover:bg-gray-50 even:bg-gray-50/40",
    )


def inventory_table() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.h2(
                translate("Inventario de flota"),
                class_name="text-base font-semibold text-[#182321]",
            ),
            rx.el.p(
                rx.cond(
                    AccessState.language == "en",
                    f"{UnitsState.total} matching units · 25 per page",
                    f"{UnitsState.total} unidades coincidentes · 25 por página",
                ),
                class_name="mt-1 text-xs text-gray-500",
            ),
            class_name="p-5",
        ),
        rx.cond(
            UnitsState.rows.length() > 0,
            rx.el.div(
                rx.el.table(
                    rx.el.thead(
                        rx.el.tr(
                            rx.foreach(
                                [
                                    "Unidad / placa",
                                    "Modelo / VIN",
                                    "Flota / cliente",
                                    "Uso / estado",
                                    "Riesgo",
                                    "Garantía",
                                ],
                                lambda label: rx.el.th(
                                    translate(label),
                                    class_name="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wide text-gray-500",
                                ),
                            ),
                            class_name="bg-gray-50",
                        )
                    ),
                    rx.el.tbody(rx.foreach(UnitsState.rows, unit_row)),
                    class_name="table-auto w-full min-w-[950px]",
                ),
                class_name="w-full overflow-x-auto",
            ),
            rx.el.div(
                empty("No se encontraron unidades con estos filtros."),
                class_name="px-5 pb-5",
            ),
        ),
        rx.el.div(
            rx.el.p(
                rx.cond(
                    AccessState.language == "en",
                    f"Page {UnitsState.page} of {UnitsState.page_count}",
                    f"Página {UnitsState.page} de {UnitsState.page_count}",
                ),
                class_name="text-xs text-gray-600",
            ),
            rx.el.div(
                rx.el.button(
                    translate("Anterior"),
                    on_click=lambda: UnitsState.paginate(-1),
                    disabled=(UnitsState.page <= 1) | UnitsState.loading,
                    class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#182321] hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
                ),
                rx.el.button(
                    translate("Siguiente"),
                    on_click=lambda: UnitsState.paginate(1),
                    disabled=(UnitsState.page >= UnitsState.page_count)
                    | UnitsState.loading,
                    class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#182321] hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
                ),
                class_name="flex gap-2",
            ),
            class_name="flex items-center justify-between gap-3 border-t border-gray-100 p-5",
        ),
        class_name="mt-6 w-full overflow-hidden rounded-xl border border-gray-200 bg-white",
    )


def feedback() -> rx.Component:
    return rx.el.div(
        rx.cond(UnitsState.error != "", error_banner(UnitsState.error)),
        rx.cond(
            UnitsState.success != "",
            rx.el.p(
                translate(UnitsState.success),
                role="status",
                class_name="rounded-lg border border-[#187C72]/20 bg-[#187C72]/10 p-4 text-sm text-[#187C72]",
            ),
        ),
        rx.cond(
            UnitsState.busy,
            rx.el.p(
                translate("Procesando operación…"),
                role="status",
                class_name="text-xs text-gray-600",
            ),
        ),
        class_name="mt-5 flex flex-col gap-3",
    )


def page_header(title: str, description: str) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.p(
                translate("FLOTA · ACCESO POR ORGANIZACIÓN"),
                class_name="text-[10px] font-semibold tracking-[0.15em] text-[#187C72]",
            ),
            rx.el.h1(
                translate(title),
                class_name="mt-2 text-2xl font-semibold tracking-tight text-[#182321]",
            ),
            rx.el.p(
                translate(description), class_name="mt-2 text-sm text-gray-600"
            ),
        ),
        rx.el.div(
            rx.cond(AccessState.role == "admin", context_selector()),
            rx.el.button(
                rx.icon("refresh-cw", class_name="h-4 w-4"),
                translate("Actualizar"),
                on_click=UnitsState.refresh,
                disabled=UnitsState.loading | UnitsState.busy,
                class_name="flex w-fit items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-medium text-[#187C72] hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
            ),
            class_name="flex flex-col gap-3",
        ),
        class_name="flex flex-col justify-between gap-5 xl:flex-row xl:items-start",
    )


def loading() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            class_name="h-32 w-full animate-pulse rounded-xl bg-gray-200"
        ),
        rx.el.p(
            translate("Verificando propiedad y cargando datos…"),
            role="status",
            class_name="mt-3 text-xs text-gray-600",
        ),
        class_name="mt-6 w-full",
    )


def units_page() -> rx.Component:
    return shell(
        rx.el.div(
            page_header(
                "Unidades",
                "Consulta inventario, salud por sistema y recomendaciones de mantenimiento.",
            ),
            feedback(),
            rx.cond(
                UnitsState.ready & (UnitsState.context == AccessState.context),
                rx.fragment(
                    filters(),
                    inventory_table(),
                    rx.el.p(
                        translate(
                            "Riesgo: máximo de las cinco inferencias entrenadas vigentes. Contrato vigente considera estado, fechas, km y horas; no garantiza cobertura del componente. Búsqueda y paginación en base de datos, sin cargar toda la flota al navegador."
                        ),
                        class_name="mt-4 text-xs leading-6 text-gray-500",
                    ),
                ),
                rx.cond(
                    UnitsState.loading,
                    loading(),
                    empty(
                        "Utiliza Actualizar para cargar la flota del contexto seleccionado."
                    ),
                ),
            ),
            class_name="w-full min-w-0",
        )
    )


def unit_details() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.p(
                    UnitsState.unit["model"],
                    class_name="text-lg font-semibold text-[#182321]",
                ),
                rx.el.p(
                    rx.cond(
                        AccessState.language == "en",
                        f"VIN {UnitsState.unit['vin']} · Plate {UnitsState.unit['plate']}",
                        f"VIN {UnitsState.unit['vin']} · Placa {UnitsState.unit['plate']}",
                    ),
                    class_name="mt-2 text-xs text-gray-600",
                ),
                rx.el.p(
                    f"{UnitsState.unit['fleet']} · {translate(UnitsState.unit['status'])}",
                    class_name="mt-2 text-xs text-gray-500",
                ),
            ),
            rx.el.div(
                rx.el.p(
                    f"{UnitsState.unit['mileage']} · {UnitsState.unit['hours']}",
                    class_name="text-sm font-semibold text-[#182321]",
                ),
                rx.el.p(
                    rx.cond(
                        AccessState.language == "en",
                        f"{UnitsState.unit['active_faults']} active / intermittent DTC",
                        f"{UnitsState.unit['active_faults']} DTC activos / intermitentes",
                    ),
                    class_name="mt-2 text-xs text-gray-600",
                ),
            ),
            class_name="mt-6 flex flex-wrap items-start justify-between gap-4 rounded-xl border border-gray-200 bg-white p-5",
        ),
        rx.el.section(
            rx.el.h2(
                translate("Salud y probabilidades de fallo · cinco sistemas"),
                class_name="text-lg font-semibold text-[#182321]",
            ),
            rx.el.p(
                translate(
                    "Motor, frenos, postratamiento, eléctrico y neumáticos. XGBoost CPU entrenado y calibrado sobre degradación sintética; las antiguas cifras de escenario demo no se muestran como inferencias entrenadas. No usar para decisiones de seguridad sin inspección profesional."
                ),
                class_name="mt-2 text-xs leading-6 text-gray-600",
            ),
            rx.cond(
                UnitsState.predictions.length() > 0,
                rx.el.div(
                    rx.foreach(UnitsState.predictions, prediction_card),
                    class_name="mt-4 grid w-full grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-3",
                ),
                empty(
                    "No hay inferencias del modelo entrenado para esta unidad. La generación automática inicial se limita a las unidades sintéticas existentes."
                ),
            ),
            class_name="mt-6 w-full",
        ),
        rx.el.section(
            rx.el.h2(
                translate("Última telemetría"),
                class_name="text-base font-semibold text-[#182321]",
            ),
            rx.el.p(
                f"{translate(UnitsState.unit['observed'])} · {translate(UnitsState.unit['source'])}",
                class_name="mt-2 text-xs text-gray-500",
            ),
            rx.cond(
                UnitsState.latest.length() > 0,
                rx.el.div(
                    rx.foreach(
                        UnitsState.latest,
                        lambda v: rx.el.div(
                            rx.el.p(
                                translate(v["label"]),
                                class_name="text-xs text-gray-500",
                            ),
                            rx.el.p(
                                translate(v["value"]),
                                class_name="mt-2 text-sm font-semibold text-[#182321]",
                            ),
                            class_name="rounded-lg border border-gray-200 bg-gray-50 p-3",
                        ),
                    ),
                    class_name="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7",
                ),
                empty("Sin lecturas disponibles."),
            ),
            rx.el.p(
                translate(
                    "Temperaturas disponibles: refrigerante y aceite. No hay sensor de temperatura de freno ni presión diferencial DPF en este esquema; no se inventan lecturas."
                ),
                class_name="mt-3 text-xs leading-5 text-gray-500",
            ),
            class_name="mt-6 rounded-xl border border-gray-200 bg-white p-5",
        ),
        rx.el.div(
            rx.el.section(
                rx.el.h2(
                    translate("Historial de telemetría"),
                    class_name="text-base font-semibold text-[#182321]",
                ),
                rx.cond(
                    UnitsState.telemetry.length() > 0,
                    rx.el.div(rx.foreach(UnitsState.telemetry, telemetry_row)),
                    empty("Sin telemetría histórica."),
                ),
                history_pager(
                    "telemetry",
                    UnitsState.telemetry_page,
                    UnitsState.telemetry_total,
                ),
                class_name="min-w-0 rounded-xl border border-gray-200 bg-white p-5",
            ),
            rx.el.section(
                rx.el.h2(
                    translate("DTC · activos e historial"),
                    class_name="text-base font-semibold text-[#182321]",
                ),
                rx.el.p(
                    translate(
                        "Activos primero. SYN identifica ocurrencias simuladas, no diagnósticos de vehículos reales."
                    ),
                    class_name="mt-2 text-xs leading-5 text-gray-500",
                ),
                rx.cond(
                    UnitsState.faults.length() > 0,
                    rx.el.div(rx.foreach(UnitsState.faults, fault_row)),
                    empty("Sin fallas DTC registradas."),
                ),
                history_pager(
                    "fault", UnitsState.fault_page, UnitsState.fault_total
                ),
                class_name="min-w-0 rounded-xl border border-gray-200 bg-white p-5",
            ),
            rx.el.section(
                rx.el.h2(
                    translate("Línea de tiempo de servicios"),
                    class_name="text-base font-semibold text-[#182321]",
                ),
                rx.cond(
                    UnitsState.services.length() > 0,
                    rx.el.div(rx.foreach(UnitsState.services, service_row)),
                    empty("Sin registros de servicio."),
                ),
                history_pager(
                    "service", UnitsState.service_page, UnitsState.service_total
                ),
                class_name="min-w-0 rounded-xl border border-gray-200 bg-white p-5",
            ),
            rx.el.section(
                rx.el.h2(
                    translate("Garantía de la unidad"),
                    class_name="text-base font-semibold text-[#182321]",
                ),
                rx.el.p(
                    translate(
                        "El estado del contrato no confirma elegibilidad. Revisión exacta por componente en cada recomendación."
                    ),
                    class_name="mt-2 text-xs leading-5 text-gray-500",
                ),
                rx.cond(
                    UnitsState.warranties.length() > 0,
                    rx.el.div(rx.foreach(UnitsState.warranties, warranty_row)),
                    empty("Sin contratos de garantía registrados."),
                ),
                class_name="min-w-0 rounded-xl border border-gray-200 bg-white p-5",
            ),
            class_name="mt-6 grid w-full min-w-0 grid-cols-1 items-start gap-6 xl:grid-cols-2",
        ),
        evidence_panel(),
        class_name="w-full min-w-0",
    )


def unit_page() -> rx.Component:
    return shell(
        rx.el.div(
            rx.el.a(
                rx.icon("arrow-left", class_name="h-4 w-4"),
                translate("Volver al inventario"),
                href="/units",
                class_name="mb-5 flex w-fit items-center gap-2 text-xs font-medium text-[#187C72] hover:underline focus-visible:outline-2 focus-visible:outline-[#187C72]",
            ),
            page_header(
                rx.cond(
                    AccessState.language == "en",
                    f"Unit {UnitsState.unit['number']}",
                    f"Unidad {UnitsState.unit['number']}",
                ),
                "Diagnóstico, evidencia y acciones dentro de tu contexto de acceso.",
            ),
            feedback(),
            rx.cond(
                UnitsState.ready & (UnitsState.context == AccessState.context),
                unit_details(),
                rx.cond(
                    UnitsState.loading,
                    loading(),
                    empty(
                        "Unidad no cargada o no disponible. Cambia de contexto o utiliza Actualizar."
                    ),
                ),
            ),
            class_name="w-full min-w-0",
        )
    )
