import reflex as rx
import reflex_xy

from app.components.layout import shell, context_selector, error_banner
from app.states.access_state import AccessState
from app.i18n import translate


def metric(
    label: str, value: rx.Var | str, note: str, icon: str, accent: bool = False
) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.p(
                translate(label), class_name="text-xs font-medium text-gray-600"
            ),
            rx.el.div(
                rx.icon(icon, class_name="h-4 w-4"),
                class_name=rx.cond(
                    accent,
                    "flex h-8 w-8 items-center justify-center rounded-lg bg-[#E5A547]/15 text-[#805410]",
                    "flex h-8 w-8 items-center justify-center rounded-lg bg-[#187C72]/10 text-[#187C72]",
                ),
            ),
            class_name="flex items-center justify-between gap-2",
        ),
        rx.el.p(
            value,
            class_name="mt-3 break-words text-2xl font-semibold tracking-tight text-[#182321] xl:text-3xl",
        ),
        rx.el.p(
            translate(note),
            class_name="mt-2 text-[11px] leading-5 text-gray-500",
        ),
        class_name="w-full rounded-xl border border-gray-200 bg-white p-4 xl:p-5",
    )


def trend_chart() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.div(
                rx.el.h2(
                    translate("Evolución del riesgo"),
                    class_name="text-base font-semibold text-[#182321]",
                ),
                rx.el.p(
                    translate(
                        "Probabilidad media de fallo por componente · últimas 8 semanas"
                    ),
                    class_name="mt-1 text-xs text-gray-500",
                ),
            ),
            rx.el.span(
                translate("30 / 90 días"),
                class_name="w-fit shrink-0 rounded-md border border-gray-200 bg-gray-50 px-2 py-1 text-[10px] font-medium text-gray-600",
            ),
            class_name="flex items-start justify-between gap-3",
        ),
        rx.cond(
            AccessState.dates.length() > 0,
            rx.el.div(
                rx.cond(
                    AccessState.language == "en",
                    reflex_xy.chart(
                        reflex_xy.line(
                            "date",
                            "risk30",
                            name="30-day risk",
                            color="#187C72",
                            width=2.5,
                        ),
                        reflex_xy.line(
                            "date",
                            "risk90",
                            name="90-day risk",
                            color="#E5A547",
                            width=2.5,
                        ),
                        reflex_xy.x_axis(label="Observation date"),
                        reflex_xy.y_axis(label="Probability (%)"),
                        reflex_xy.legend(),
                        reflex_xy.modebar(False),
                        reflex_xy.interaction_config(navigation=False),
                        data=AccessState.trend,
                        height="310px",
                        class_name="w-full min-w-[300px]",
                    ),
                    reflex_xy.chart(
                        reflex_xy.line(
                            "date",
                            "risk30",
                            name="Riesgo a 30 días",
                            color="#187C72",
                            width=2.5,
                        ),
                        reflex_xy.line(
                            "date",
                            "risk90",
                            name="Riesgo a 90 días",
                            color="#E5A547",
                            width=2.5,
                        ),
                        reflex_xy.x_axis(label="Fecha de observación"),
                        reflex_xy.y_axis(label="Probabilidad (%)"),
                        reflex_xy.legend(),
                        reflex_xy.modebar(False),
                        reflex_xy.interaction_config(navigation=False),
                        data=AccessState.trend,
                        height="310px",
                        class_name="w-full min-w-[300px]",
                    ),
                ),
                class_name="mt-4 h-[310px] w-full shrink-0 overflow-x-auto",
            ),
            rx.el.div(
                rx.icon(
                    "chart-no-axes-combined", class_name="h-7 w-7 text-gray-400"
                ),
                rx.el.p(
                    translate("Sin predicciones para este contexto."),
                    class_name="text-sm text-gray-500",
                ),
                class_name="flex h-[310px] flex-col items-center justify-center gap-3 bg-white",
            ),
        ),
        rx.el.p(
            translate(
                "Historial sintético: escenarios demo antiguos (no entrenados) e inferencias XGBoost calibradas desde su entrenamiento inicial. Se utiliza la última cifra disponible por unidad y componente en cada fecha; no es validación sobre fallos reales."
            ),
            class_name="mt-3 border-t border-gray-100 pt-3 text-[11px] leading-5 text-gray-500",
        ),
        class_name="w-full min-w-0 rounded-xl border border-gray-200 bg-white p-5",
    )


def operation_notes() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.icon("clipboard-check", class_name="h-5 w-5 text-[#187C72]"),
            rx.el.h2(
                translate("Lectura operativa"),
                class_name="text-base font-semibold text-[#182321]",
            ),
            class_name="flex items-center gap-2",
        ),
        rx.el.div(
            rx.el.p(
                translate("01 · Prioriza la seguridad"),
                class_name="text-xs font-semibold text-[#182321]",
            ),
            rx.el.p(
                translate(
                    "El riesgo alto refleja la clasificación de la última predicción vigente. Revisa las acciones antes de asignar una ruta."
                ),
                class_name="mt-2 text-xs leading-6 text-gray-600",
            ),
            class_name="mt-5 border-b border-gray-100 pb-4",
        ),
        rx.el.div(
            rx.el.p(
                translate("02 · Atiende los vencimientos"),
                class_name="text-xs font-semibold text-[#182321]",
            ),
            rx.el.p(
                translate(
                    "Una orden abierta está vencida si su fecha límite o su inicio programado ya pasó. Las órdenes canceladas y terminadas se excluyen."
                ),
                class_name="mt-2 text-xs leading-6 text-gray-600",
            ),
            class_name="mt-4 border-b border-gray-100 pb-4",
        ),
        rx.el.div(
            rx.el.p(
                translate("03 · Costos reales, no estimados"),
                class_name="text-xs font-semibold text-[#182321]",
            ),
            rx.el.p(
                translate(
                    "El costo mensual suma mano de obra, piezas y otros gastos de registros de servicio realizados este mes en MXN, sin duplicar la orden asociada."
                ),
                class_name="mt-2 text-xs leading-6 text-gray-600",
            ),
            class_name="mt-4",
        ),
        class_name="w-full rounded-xl border border-gray-200 bg-white p-5",
    )


def action_row(action: dict[str, str], index: int) -> rx.Component:
    return rx.el.tr(
        rx.el.td(
            f"{index + 1}", class_name="w-10 px-4 py-4 text-xs text-gray-400"
        ),
        rx.el.td(
            rx.el.a(
                action["unit"],
                rx.icon("arrow-up-right", class_name="h-3 w-3"),
                href=action["url"],
                aria_label=rx.cond(
                    AccessState.language == "en",
                    f"View unit {action['unit']}",
                    f"Ver unidad {action['unit']}",
                ),
                class_name="flex w-fit items-center gap-2 font-semibold text-[#187C72] hover:underline focus-visible:outline-2 focus-visible:outline-[#187C72]",
            ),
            rx.el.p(
                action["organization"],
                class_name="mt-1 text-[10px] text-gray-500",
            ),
            class_name="px-3 py-4 text-xs",
        ),
        rx.el.td(
            rx.el.p(
                translate(action["action"]),
                class_name="max-w-sm text-xs font-medium leading-5 text-[#182321]",
            ),
            class_name="px-3 py-4",
        ),
        rx.el.td(
            rx.el.span(
                translate(action["risk"]),
                class_name=rx.cond(
                    action["risk"] == "Crítico",
                    "w-fit whitespace-nowrap rounded-md bg-red-50 px-2 py-1 text-[10px] font-semibold text-red-700",
                    "w-fit whitespace-nowrap rounded-md bg-[#E5A547]/15 px-2 py-1 text-[10px] font-semibold text-[#805410]",
                ),
            ),
            rx.el.p(
                rx.cond(
                    AccessState.language == "en",
                    f"{action['probability']} over 30 days",
                    f"{action['probability']} a 30 días",
                ),
                class_name="mt-2 whitespace-nowrap text-[10px] text-gray-500",
            ),
            class_name="px-3 py-4",
        ),
        rx.el.td(
            translate(action["due"]),
            class_name="whitespace-nowrap px-3 py-4 text-xs text-gray-600",
        ),
        rx.el.td(
            action["cost"],
            class_name="whitespace-nowrap px-4 py-4 text-right text-xs font-medium text-[#182321]",
        ),
        key=action["id"],
        class_name="border-t border-gray-100 bg-white hover:bg-gray-50 even:bg-gray-50/40",
    )


def priority_actions() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.div(
                rx.el.h2(
                    translate("Acciones prioritarias"),
                    class_name="text-base font-semibold text-[#182321]",
                ),
                rx.el.p(
                    translate(
                        "Riesgos altos y críticos · ordenados por probabilidad de fallo a 30 días"
                    ),
                    class_name="mt-1 text-xs text-gray-500",
                ),
            ),
            rx.el.span(
                rx.cond(
                    AccessState.language == "en",
                    f"{AccessState.actions.length()} actions",
                    f"{AccessState.actions.length()} acciones",
                ),
                class_name="w-fit shrink-0 rounded-md bg-gray-100 px-2 py-1 text-[10px] font-medium text-gray-600",
            ),
            class_name="flex items-start justify-between gap-3 p-5",
        ),
        rx.cond(
            AccessState.actions.length() > 0,
            rx.el.div(
                rx.el.table(
                    rx.el.thead(
                        rx.el.tr(
                            rx.el.th("#", class_name="px-4 py-3 text-left"),
                            rx.el.th(
                                translate("Unidad / cliente"),
                                class_name="px-3 py-3 text-left",
                            ),
                            rx.el.th(
                                translate("Acción recomendada"),
                                class_name="px-3 py-3 text-left",
                            ),
                            rx.el.th(
                                translate("Riesgo"),
                                class_name="px-3 py-3 text-left",
                            ),
                            rx.el.th(
                                translate("Atender antes de"),
                                class_name="px-3 py-3 text-left",
                            ),
                            rx.el.th(
                                translate("Estimado · MXN"),
                                class_name="px-4 py-3 text-right",
                            ),
                            class_name="border-t border-gray-100 bg-gray-50 text-[10px] font-medium uppercase tracking-wide text-gray-500",
                        )
                    ),
                    rx.el.tbody(rx.foreach(AccessState.actions, action_row)),
                    class_name="table-auto w-full min-w-[740px]",
                ),
                class_name="w-full overflow-x-auto",
            ),
            rx.el.div(
                rx.icon("circle-check", class_name="h-7 w-7 text-[#187C72]"),
                rx.el.p(
                    translate("Sin acciones de alto riesgo"),
                    class_name="text-sm font-medium text-[#182321]",
                ),
                rx.el.p(
                    translate(
                        "No hay predicciones vigentes de riesgo alto o crítico en este contexto."
                    ),
                    class_name="text-xs text-gray-500",
                ),
                class_name="flex flex-col items-center gap-3 border-t border-gray-100 bg-white px-5 py-10 text-center",
            ),
        ),
        rx.el.p(
            translate(
                "Máximo 8 acciones. Consulta en la unidad la procedencia de la inferencia y crea una orden en borrador. Los importes son estimados, no cargos reales; la cobertura requiere revisión."
            ),
            class_name="border-t border-gray-100 p-4 text-[11px] leading-5 text-gray-500",
        ),
        class_name="mt-6 w-full overflow-hidden rounded-xl border border-gray-200 bg-white",
    )


def summary_page() -> rx.Component:
    return shell(
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.el.p(
                        translate("VISIÓN GENERAL"),
                        class_name="text-[10px] font-semibold tracking-[0.15em] text-[#187C72]",
                    ),
                    rx.el.h1(
                        translate("Resumen de mantenimiento"),
                        class_name="mt-2 text-2xl font-semibold tracking-tight text-[#182321]",
                    ),
                    rx.el.p(
                        translate(
                            "Anticipa riesgos. Ordena prioridades. Mantén tu flota en movimiento."
                        ),
                        class_name="mt-2 text-sm text-gray-600",
                    ),
                ),
                rx.cond(AccessState.role == "admin", context_selector()),
                class_name="flex flex-col justify-between gap-5 xl:flex-row xl:items-center",
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.span(
                        "SYNTHETIC",
                        class_name="w-fit rounded-md border border-[#E5A547]/30 bg-[#E5A547]/10 px-2 py-1 text-[10px] font-semibold text-[#805410]",
                    ),
                    rx.el.p(
                        rx.cond(
                            AccessState.language == "en",
                            f"{AccessState.unit_count} non-retired units · {AccessState.updated}",
                            f"{AccessState.unit_count} unidades no retiradas · {AccessState.updated}",
                        ),
                        class_name="text-[11px] text-gray-500",
                    ),
                    class_name="flex flex-wrap items-center gap-3",
                ),
                rx.el.button(
                    rx.icon(
                        "refresh-cw",
                        class_name=rx.cond(
                            AccessState.loading,
                            "h-3.5 w-3.5 animate-spin",
                            "h-3.5 w-3.5",
                        ),
                    ),
                    translate("Actualizar"),
                    on_click=AccessState.load,
                    disabled=AccessState.loading | AccessState.busy,
                    class_name="flex shrink-0 items-center gap-2 rounded-md px-2 py-2 text-xs font-medium text-[#187C72] hover:bg-[#187C72]/5 focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-50",
                ),
                class_name="my-6 flex items-center justify-between gap-3",
            ),
            rx.cond(
                AccessState.error != "",
                rx.el.div(error_banner(AccessState.error), class_name="mb-5"),
            ),
            rx.cond(
                AccessState.loading,
                rx.el.div(
                    rx.icon(
                        "loader-circle",
                        class_name="h-4 w-4 animate-spin text-[#187C72]",
                    ),
                    translate("Actualizando el resumen…"),
                    role="status",
                    class_name="mb-4 flex items-center gap-2 text-xs text-gray-600",
                ),
            ),
            rx.cond(
                (AccessState.unit_count == 0) & ~AccessState.loading,
                rx.el.div(
                    rx.icon("truck", class_name="h-5 w-5 text-gray-500"),
                    rx.el.p(
                        translate(
                            "Esta organización aún no tiene unidades. Los indicadores permanecerán en cero hasta que se incorporen datos."
                        ),
                        class_name="text-sm text-gray-600",
                    ),
                    class_name="mb-5 flex items-center gap-3 rounded-xl border border-gray-200 bg-white p-5",
                ),
            ),
            rx.el.div(
                metric(
                    "Unidades activas",
                    AccessState.active.to_string(),
                    "En operación · excluye unidades en taller",
                    "truck",
                ),
                metric(
                    "Unidades de alto riesgo",
                    AccessState.high_risk.to_string(),
                    "Predicción vigente · alto o crítico",
                    "triangle-alert",
                    True,
                ),
                metric(
                    "Órdenes vencidas",
                    AccessState.overdue.to_string(),
                    "Abiertas y fuera de fecha",
                    "calendar-clock",
                    True,
                ),
                metric(
                    "Costo real del mes",
                    f"${AccessState.cost:,.2f}",
                    "MXN · registros de servicio del mes",
                    "wallet",
                ),
                class_name="grid w-full grid-cols-2 gap-4 xl:grid-cols-4",
            ),
            rx.el.div(
                trend_chart(),
                operation_notes(),
                class_name="mt-6 grid w-full min-w-0 grid-cols-1 items-stretch gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]",
            ),
            priority_actions(),
            rx.el.p(
                translate(
                    "Información de demostración · Acceso limitado a tu organización · Todos los importes en MXN"
                ),
                class_name="mt-6 text-[10px] text-gray-500",
            ),
            class_name="w-full min-w-0",
        )
    )
