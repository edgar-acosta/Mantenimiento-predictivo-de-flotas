import reflex as rx

from app.states.units_state import UnitsState
from app.states.access_state import AccessState
from app.i18n import translate


def risk_badge(label: str, key: str) -> rx.Component:
    return rx.el.span(
        translate(label),
        class_name=rx.cond(
            key == "critical",
            "inline-flex w-fit rounded-md bg-red-50 px-2 py-1 text-xs font-semibold text-red-700",
            rx.cond(
                key == "high",
                "inline-flex w-fit rounded-md bg-[#E5A547]/15 px-2 py-1 text-xs font-semibold text-[#805410]",
                "inline-flex w-fit rounded-md bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700",
            ),
        ),
    )


def empty(message: str) -> rx.Component:
    return rx.el.p(
        translate(message),
        class_name="rounded-lg border border-dashed border-gray-200 bg-gray-50 p-6 text-sm text-gray-600",
    )


def prediction_card(p: dict[str, str]) -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.h3(
                translate(p["system"]),
                class_name="text-base font-semibold text-[#182321]",
            ),
            risk_badge(p["risk"], p["risk_key"]),
            class_name="flex flex-wrap items-center justify-between gap-2",
        ),
        rx.el.p(
            translate(p["component"]), class_name="mt-1 text-xs text-gray-500"
        ),
        rx.el.div(
            rx.el.div(
                rx.el.p(
                    translate("30 días"), class_name="text-xs text-gray-500"
                ),
                rx.el.p(
                    p["p30"],
                    class_name="mt-1 text-2xl font-semibold text-[#182321]",
                ),
            ),
            rx.el.div(
                rx.el.p(
                    translate("90 días"), class_name="text-xs text-gray-500"
                ),
                rx.el.p(
                    p["p90"],
                    class_name="mt-1 text-2xl font-semibold text-[#182321]",
                ),
            ),
            rx.el.div(
                rx.el.p(
                    translate("Índice de salud"),
                    class_name="text-xs text-gray-500",
                ),
                rx.el.p(
                    p["health"],
                    class_name="mt-1 text-lg font-semibold text-[#187C72]",
                ),
            ),
            class_name="mt-4 grid grid-cols-3 gap-3 rounded-lg bg-[#F6F5F1] p-3",
        ),
        rx.el.p(
            translate(
                "Índice = 100 × (1 − P90); no es una inspección mecánica."
            ),
            class_name="mt-2 text-[10px] leading-4 text-gray-500",
        ),
        rx.el.p(
            translate(p["action"]),
            class_name="mt-4 text-sm font-medium leading-6 text-[#182321]",
        ),
        rx.el.div(
            rx.icon(
                "calendar-clock", class_name="h-4 w-4 shrink-0 text-[#187C72]"
            ),
            rx.el.div(
                rx.el.p(
                    translate(p["window"]),
                    class_name="text-xs font-semibold text-[#182321]",
                ),
                rx.el.p(
                    rx.cond(
                        AccessState.language == "en",
                        f"Target date: {p['due']}",
                        f"Fecha objetivo: {p['due']}",
                    ),
                    class_name="mt-1 text-xs text-gray-600",
                ),
            ),
            class_name="mt-4 flex items-start gap-2",
        ),
        rx.el.p(
            rx.cond(
                AccessState.language == "en",
                f"{p['cost']} · {p['downtime']} estimated downtime",
                f"{p['cost']} · {p['downtime']} de paro estimado",
            ),
            class_name="mt-3 text-xs font-medium text-gray-700",
        ),
        rx.el.details(
            rx.el.summary(
                translate("Cobertura y condiciones"),
                class_name="cursor-pointer text-xs font-semibold text-[#187C72] focus-visible:outline-2 focus-visible:outline-[#187C72]",
            ),
            rx.el.p(
                translate(p["warranty"]),
                class_name="mt-2 text-xs leading-6 text-gray-600",
            ),
            class_name="mt-4 rounded-lg border border-gray-200 bg-white p-3",
        ),
        rx.el.details(
            rx.el.summary(
                translate("Modelo, evaluación y procedencia"),
                class_name="cursor-pointer text-xs font-semibold text-[#187C72] focus-visible:outline-2 focus-visible:outline-[#187C72]",
            ),
            rx.el.p(
                translate(p["provenance"]),
                class_name="mt-2 break-words text-xs leading-5 text-gray-600",
            ),
            rx.el.p(
                translate(p["metrics"]),
                class_name="mt-2 text-xs leading-5 text-gray-600",
            ),
            rx.el.p(
                f"SHA256: {p['artifact']}",
                class_name="mt-2 break-all text-[10px] text-gray-500",
            ),
            rx.el.p(
                translate(
                    "5,000 ejemplos sintéticos; 3,750 de entrenamiento con calibración sigmoide de 3 pliegues, 1,250 de test independiente. Clases: fallo ≤30, 31–90, >90 días. P90 incluye P30. Evaluación sólo sintética, no validada con fallos reales; datos faltantes imputados a valores nominales. Estimación de diagnóstico, no garantía de seguridad."
                ),
                class_name="mt-2 text-xs leading-5 text-gray-600",
            ),
            class_name="mt-3",
        ),
        rx.cond(
            p["order"] != "",
            rx.el.p(
                rx.cond(
                    AccessState.language == "en",
                    f"Active order: {p['order']}",
                    f"Orden activa: {p['order']}",
                ),
                role="status",
                class_name="mt-4 rounded-lg bg-[#187C72]/10 p-3 text-xs font-medium text-[#187C72]",
            ),
            rx.el.button(
                rx.icon("wrench", class_name="h-4 w-4"),
                rx.cond(
                    p["valid"] == "yes",
                    translate("Crear orden de servicio"),
                    translate("Inferencia vencida"),
                ),
                on_click=lambda: UnitsState.create_order(p["id"]),
                disabled=UnitsState.busy
                | UnitsState.loading
                | (p["valid"] != "yes"),
                class_name="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-[#187C72] px-3 py-3 text-xs font-semibold text-white hover:bg-[#12665e] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#187C72] disabled:opacity-50",
            ),
        ),
        rx.el.p(
            translate(
                "Orden en borrador; no reserva taller. Costos orientativos sin cotización."
            ),
            class_name="mt-2 text-[10px] leading-4 text-gray-500",
        ),
        key=p["id"],
        class_name="min-w-0 rounded-xl border border-gray-200 bg-white p-5",
    )


def history_pager(section: str, page: rx.Var, total: rx.Var) -> rx.Component:
    return rx.el.div(
        rx.el.span(
            rx.cond(
                AccessState.language == "en",
                f"Page {page} · {total} records · 20 per page",
                f"Página {page} · {total} registros · 20 por página",
            ),
            class_name="text-xs text-gray-500",
        ),
        rx.el.div(
            rx.el.button(
                translate("Anterior"),
                on_click=lambda: UnitsState.history_page(section, -1),
                disabled=(page <= 1) | UnitsState.loading,
                class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#182321] hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
            ),
            rx.el.button(
                translate("Siguiente"),
                on_click=lambda: UnitsState.history_page(section, 1),
                disabled=(page * 20 >= total) | UnitsState.loading,
                class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#182321] hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
            ),
            class_name="flex gap-2",
        ),
        class_name="mt-4 flex flex-wrap items-center justify-between gap-3",
    )


def telemetry_row(t: dict[str, str]) -> rx.Component:
    return rx.el.details(
        rx.el.summary(
            rx.el.span(t["date"], class_name="font-medium text-[#182321]"),
            rx.el.span(t["usage"], class_name="ml-3 text-gray-600"),
            class_name="cursor-pointer text-xs focus-visible:outline-2 focus-visible:outline-[#187C72]",
        ),
        rx.el.p(t["source"], class_name="mt-2 text-xs text-[#187C72]"),
        rx.el.p(t["values"], class_name="mt-2 text-xs leading-6 text-gray-600"),
        key=t["id"],
        class_name="border-b border-gray-100 py-4 last:border-0",
    )


def fault_row(f: dict[str, str]) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.p(
                f"{f['code']} · {translate(f['system'])}",
                class_name="text-sm font-semibold text-[#182321]",
            ),
            risk_badge(
                f["status"], rx.cond(f["status"] == "active", "high", "low")
            ),
            class_name="flex flex-wrap items-center justify-between gap-2",
        ),
        rx.el.p(
            translate(f["description"]), class_name="mt-2 text-xs text-gray-600"
        ),
        rx.el.p(
            rx.cond(
                AccessState.language == "en",
                f"{f['count']} occurrences · severity {translate(f['severity'])} · {f['source']}",
                f"{f['count']} ocurrencias · severidad {translate(f['severity'])} · {f['source']}",
            ),
            class_name="mt-2 text-xs text-gray-500",
        ),
        rx.el.details(
            rx.el.summary(
                translate("Fechas del diagnóstico"),
                class_name="mt-2 cursor-pointer text-xs text-[#187C72] focus-visible:outline-2 focus-visible:outline-[#187C72]",
            ),
            rx.el.p(
                rx.cond(
                    AccessState.language == "en",
                    f"First: {f['first']} · Last: {f['last']} · Cleared: {f['cleared']}",
                    f"Primera: {f['first']} · Última: {f['last']} · Resuelta: {f['cleared']}",
                ),
                class_name="mt-2 break-words text-xs leading-5 text-gray-600",
            ),
        ),
        key=f["id"],
        class_name="border-b border-gray-100 py-4 last:border-0",
    )


def service_row(s: dict[str, str]) -> rx.Component:
    return rx.el.div(
        rx.el.p(s["date"], class_name="text-xs font-medium text-[#187C72]"),
        rx.el.p(
            translate(s["description"]),
            class_name="mt-2 text-sm font-semibold text-[#182321]",
        ),
        rx.el.p(
            f"{translate(s['status'])} · {s['usage']} · {s['cost']}",
            class_name="mt-2 text-xs text-gray-600",
        ),
        rx.el.p(
            rx.foreach(
                s["details"].split(" · "),
                lambda detail: rx.el.span(translate(detail), " · "),
            ),
            class_name="mt-2 text-xs leading-5 text-gray-500",
        ),
        rx.el.p(
            rx.cond(
                AccessState.language == "en",
                f"Next service: {translate(s['next'])}",
                f"Próximo servicio: {s['next']}",
            ),
            class_name="mt-2 text-xs text-gray-600",
        ),
        key=s["id"],
        class_name="border-b border-gray-100 py-4 last:border-0",
    )


def warranty_row(w: dict[str, str]) -> rx.Component:
    return rx.el.div(
        rx.el.p(
            f"{w['contract']} · {translate(w['status'])}",
            class_name="text-sm font-semibold text-[#182321]",
        ),
        rx.el.p(w["provider"], class_name="mt-2 text-xs text-gray-600"),
        rx.el.p(
            f"{w['dates']} · {translate(w['limits'])}",
            class_name="mt-2 text-xs text-gray-600",
        ),
        rx.el.p(
            rx.cond(
                AccessState.language == "en",
                f"Components: {translate(w['components'])}",
                f"Componentes: {w['components']}",
            ),
            class_name="mt-2 text-xs font-medium text-[#187C72]",
        ),
        rx.el.p(
            rx.foreach(
                w["terms"].split(" · "),
                lambda term: rx.el.span(translate(term), " · "),
            ),
            class_name="mt-2 text-xs leading-5 text-gray-500",
        ),
        key=w["id"],
        class_name="border-b border-gray-100 py-4 last:border-0",
    )


def evidence_row(e: dict[str, str]) -> rx.Component:
    return rx.el.div(
        rx.icon("file-image", class_name="h-5 w-5 shrink-0 text-[#187C72]"),
        rx.el.div(
            rx.el.p(
                e["name"],
                class_name="break-all text-sm font-medium text-[#182321]",
            ),
            rx.el.p(
                f"{translate(e['type'])} · {translate(e['status'])} · {e['size']}",
                class_name="mt-1 text-xs text-gray-500",
            ),
            rx.el.p(
                translate(e["caption"]), class_name="mt-1 text-xs text-gray-600"
            ),
            rx.el.p(
                e["date"],
                class_name="mt-1 break-words text-[10px] text-gray-500",
            ),
            class_name="min-w-0 flex-1",
        ),
        rx.el.button(
            translate("Abrir"),
            on_click=lambda: UnitsState.view_evidence(e["id"]),
            disabled=UnitsState.busy | (e["status"] != "available"),
            aria_label=rx.cond(
                AccessState.language == "en",
                f"Open evidence {e['name']}",
                f"Abrir evidencia {e['name']}",
            ),
            class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-medium text-[#187C72] hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-40",
        ),
        key=e["id"],
        class_name="flex items-start gap-3 border-b border-gray-100 py-4 last:border-0",
    )


def evidence_panel() -> rx.Component:
    return rx.el.section(
        rx.el.h2(
            translate("Evidencia privada · foto / video"),
            class_name="text-base font-semibold text-[#182321]",
        ),
        rx.el.p(
            translate(
                "Sólo archivos reales aportados por usuarios autorizados. JPEG/PNG y MP4; un archivo, máximo 8 MB. Imágenes normalizadas sin metadatos; video conservado. Almacenamiento privado en base de datos, sin enlaces públicos. No se verifica la fecha de captura."
            ),
            class_name="mt-2 text-xs leading-6 text-gray-600",
        ),
        rx.cond(
            UnitsState.evidence.length() > 0,
            rx.el.div(rx.foreach(UnitsState.evidence, evidence_row)),
            empty("Sin fotos ni videos disponibles para esta unidad."),
        ),
        history_pager(
            "evidence", UnitsState.evidence_page, UnitsState.evidence_total
        ),
        rx.upload.root(
            rx.icon("upload", class_name="h-5 w-5 text-[#187C72]"),
            rx.el.p(
                translate("Seleccionar foto o video"),
                class_name="text-sm font-medium text-[#182321]",
            ),
            rx.foreach(
                rx.selected_files("unit-evidence"),
                lambda name: rx.el.p(
                    name, class_name="break-all text-xs text-gray-600"
                ),
            ),
            id="unit-evidence",
            max_files=1,
            max_size=8388608,
            multiple=False,
            accept={
                "image/jpeg": [".jpg", ".jpeg"],
                "image/png": [".png"],
                "video/mp4": [".mp4"],
            },
            disabled=UnitsState.busy | UnitsState.loading,
            class_name="mt-5 flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed border-gray-300 bg-gray-50 p-5 focus-within:outline-2 focus-within:outline-[#187C72]",
        ),
        rx.el.button(
            translate("Guardar evidencia"),
            on_click=UnitsState.upload(
                rx.upload_files(upload_id="unit-evidence")
            ),
            disabled=UnitsState.busy | UnitsState.loading,
            class_name="mt-3 rounded-lg bg-[#187C72] px-4 py-2 text-xs font-semibold text-white hover:bg-[#12665e] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#187C72] disabled:opacity-50",
        ),
        rx.cond(
            UnitsState.media_src != "",
            rx.el.div(
                rx.el.div(
                    rx.el.h3(
                        UnitsState.media_name,
                        class_name="break-all text-sm font-semibold text-[#182321]",
                    ),
                    rx.el.button(
                        translate("Cerrar"),
                        on_click=UnitsState.close_media,
                        class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#182321] focus-visible:outline-2 focus-visible:outline-[#187C72]",
                    ),
                    class_name="mb-3 flex items-center justify-between gap-3",
                ),
                rx.cond(
                    UnitsState.media_type == "photo",
                    rx.el.img(
                        src=UnitsState.media_src,
                        alt=UnitsState.media_name,
                        class_name="max-h-[520px] w-full rounded-lg bg-gray-50 object-contain",
                    ),
                    rx.el.video(
                        src=UnitsState.media_src,
                        controls=True,
                        preload="metadata",
                        aria_label=UnitsState.media_name,
                        class_name="max-h-[520px] w-full rounded-lg bg-[#182321]",
                    ),
                ),
                class_name="mt-5 rounded-lg border border-gray-200 bg-white p-4",
            ),
        ),
        class_name="mt-6 w-full min-w-0 rounded-xl border border-gray-200 bg-white p-5",
    )
