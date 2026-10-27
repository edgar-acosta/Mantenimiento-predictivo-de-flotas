import reflex as rx

from app.states.access_state import AccessState
from app.i18n import themed, translate


def brand() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon("truck", class_name="h-6 w-6 text-[#E5A547]"),
            class_name="flex h-11 w-11 items-center justify-center rounded-lg border border-white/20 bg-[#182321]",
        ),
        rx.el.div(
            rx.el.p(
                "DAIMLER",
                class_name="text-sm font-semibold tracking-[0.2em] text-white",
            ),
            rx.el.p("Fleet maintenance", class_name="text-xs text-white/60"),
        ),
        class_name="flex items-center gap-3",
    )


def nav_link(label: str, icon: str, href: str) -> rx.Component:
    return rx.el.a(
        rx.icon(icon, class_name="h-4 w-4 shrink-0"),
        rx.el.span(translate(label)),
        href=href,
        class_name="flex items-center gap-3 rounded-lg px-3 py-3 text-sm text-white/70 hover:bg-white/10 hover:text-white focus-visible:outline-2 focus-visible:outline-[#E5A547]",
    )


def sidebar() -> rx.Component:
    return rx.el.aside(
        rx.el.div(brand(), class_name="shrink-0 px-6 py-8"),
        rx.el.nav(
            rx.el.p(
                translate("OPERACIÓN"),
                class_name="mb-3 px-3 text-[10px] font-semibold tracking-[0.15em] text-white/40",
            ),
            rx.el.a(
                rx.icon("layout-dashboard", class_name="h-4 w-4"),
                translate("Resumen"),
                href="/summary",
                class_name="flex items-center gap-3 rounded-lg border border-white/10 bg-white/10 px-3 py-3 text-sm font-medium text-white focus-visible:outline-2 focus-visible:outline-[#E5A547]",
            ),
            nav_link("Unidades", "truck", "/units"),
            nav_link("Garantías", "shield-check", "/warranty"),
            nav_link("Órdenes de servicio", "wrench", "/orders"),
            rx.cond(
                AccessState.role == "admin",
                rx.el.div(
                    rx.el.p(
                        translate("ADMINISTRACIÓN"),
                        class_name="mb-3 mt-8 px-3 text-[10px] font-semibold tracking-[0.15em] text-white/40",
                    ),
                    rx.el.a(
                        rx.icon("users", class_name="h-4 w-4"),
                        translate("Cuentas de clientes"),
                        href="/admin/accounts",
                        class_name="flex items-center gap-3 rounded-lg px-3 py-3 text-sm text-white/70 hover:bg-white/10 hover:text-white focus-visible:outline-2 focus-visible:outline-[#E5A547]",
                    ),
                ),
            ),
            class_name="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto px-4",
        ),
        rx.el.div(
            rx.el.div(
                rx.icon("flask-conical", class_name="h-4 w-4 text-[#E5A547]"),
                translate("Entorno sintético"),
                class_name="flex items-center gap-2 text-xs font-medium text-white/80",
            ),
            rx.el.p(
                translate(
                    "Datos de demostración. No usar para decisiones de seguridad."
                ),
                class_name="mt-2 text-xs leading-5 text-white/50",
            ),
            class_name="m-4 shrink-0 rounded-lg border border-white/10 bg-white/5 p-4",
        ),
        class_name="hidden h-full w-64 shrink-0 flex-col bg-[#182321] text-white lg:flex",
    )


def mobile_nav() -> rx.Component:
    return rx.el.nav(
        rx.el.a(
            translate("Resumen"),
            href="/summary",
            class_name="shrink-0 text-[#187C72]",
        ),
        rx.el.a(
            translate("Unidades"),
            href="/units",
            class_name="shrink-0 text-gray-600",
        ),
        rx.el.a(
            translate("Garantías"),
            href="/warranty",
            class_name="shrink-0 text-gray-600",
        ),
        rx.el.a(
            translate("Órdenes"),
            href="/orders",
            class_name="shrink-0 text-gray-600",
        ),
        rx.cond(
            AccessState.role == "admin",
            rx.el.a(
                translate("Cuentas"),
                href="/admin/accounts",
                class_name="shrink-0 text-gray-600",
            ),
        ),
        aria_label=rx.cond(
            AccessState.language == "en",
            "Mobile navigation",
            "Navegación móvil",
        ),
        class_name="flex shrink-0 gap-5 overflow-x-auto border-b border-gray-200 bg-white px-5 py-3 text-xs font-medium lg:hidden",
    )


def context_selector() -> rx.Component:
    return rx.el.form(
        rx.el.label(
            translate("Contexto de operación"),
            html_for="context",
            class_name="text-xs font-medium text-gray-500",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.select(
                    rx.el.option(
                        translate("Toda la red · 5 clientes"), value="network"
                    ),
                    rx.foreach(
                        AccessState.clients,
                        lambda c: rx.el.option(c["name"], value=c["id"]),
                    ),
                    id="context",
                    name="context",
                    default_value=AccessState.context,
                    key=AccessState.context,
                    class_name="w-full appearance-none rounded-lg border border-gray-200 bg-white py-2 pl-3 pr-9 text-sm text-[#182321] focus:outline-2 focus:outline-[#187C72]",
                ),
                rx.icon(
                    "chevron-down",
                    class_name="pointer-events-none absolute right-3 top-3 h-4 w-4 text-gray-500",
                ),
                class_name="relative min-w-0 flex-1",
            ),
            rx.el.button(
                translate("Aplicar"),
                type="submit",
                disabled=AccessState.loading | AccessState.busy,
                class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-medium text-[#182321] hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-50",
            ),
            class_name="mt-1 flex gap-2",
        ),
        on_submit=AccessState.switch_context,
        class_name="w-full sm:w-80",
    )


def preference_controls() -> rx.Component:
    return rx.el.div(
        rx.el.button(
            rx.icon("languages", class_name="h-4 w-4"),
            rx.el.span(rx.cond(AccessState.language == "es", "EN", "ES")),
            on_click=AccessState.toggle_language,
            disabled=AccessState.preferences_busy,
            aria_label=rx.cond(
                AccessState.language == "es",
                "Cambiar a inglés",
                "Switch to Spanish",
            ),
            class_name="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-medium text-[#182321] hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-50",
        ),
        rx.el.button(
            rx.cond(
                AccessState.theme == "light",
                rx.icon("moon", class_name="h-4 w-4"),
                rx.icon("sun", class_name="h-4 w-4"),
            ),
            on_click=AccessState.toggle_theme,
            disabled=AccessState.preferences_busy,
            aria_label=rx.cond(
                AccessState.language == "es",
                "Cambiar tema claro/oscuro",
                "Toggle light/dark theme",
            ),
            class_name="rounded-lg border border-gray-200 bg-white p-2 text-[#182321] hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-50",
        ),
        class_name="flex items-center gap-2",
    )


def shell(content: rx.Component) -> rx.Component:
    return themed(
        rx.el.div(
            rx.cond(
                AccessState.authenticated,
                rx.fragment(
                    sidebar(),
                    rx.el.div(
                        rx.el.header(
                            rx.el.div(
                                rx.el.p(
                                    translate("CENTRO DE CONTROL"),
                                    class_name="text-[10px] font-semibold tracking-[0.15em] text-gray-500",
                                ),
                                rx.el.p(
                                    translate(AccessState.title),
                                    class_name="mt-1 text-sm font-semibold text-[#182321]",
                                ),
                            ),
                            rx.el.div(
                                rx.el.div(
                                    rx.el.p(
                                        AccessState.name,
                                        class_name="text-right text-sm font-medium text-[#182321]",
                                    ),
                                    rx.el.p(
                                        rx.cond(
                                            AccessState.role == "admin",
                                            translate("Administrador de red"),
                                            translate("Acceso de cliente"),
                                        ),
                                        class_name="text-right text-xs text-gray-500",
                                    ),
                                    class_name="hidden sm:block",
                                ),
                                preference_controls(),
                                rx.el.button(
                                    rx.icon("log-out", class_name="h-4 w-4"),
                                    rx.el.span(
                                        translate("Salir"), class_name="text-xs"
                                    ),
                                    on_click=AccessState.logout,
                                    aria_label=translate("Cerrar sesión"),
                                    class_name="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-[#182321] hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-[#187C72]",
                                ),
                                class_name="flex items-center gap-4",
                            ),
                            class_name="flex shrink-0 flex-wrap items-center justify-between gap-4 border-b border-gray-200 bg-white px-5 py-4 sm:flex-nowrap lg:px-8",
                        ),
                        mobile_nav(),
                        rx.el.main(
                            content,
                            class_name="min-h-0 w-full min-w-0 flex-1 overflow-y-auto px-5 py-7 lg:px-8",
                        ),
                        class_name="flex min-h-0 w-full min-w-0 flex-1 flex-col",
                    ),
                ),
                rx.el.main(
                    rx.el.div(
                        rx.icon(
                            "loader-circle",
                            class_name="h-6 w-6 animate-spin text-[#187C72]",
                        ),
                        rx.el.p(
                            translate("Verificando acceso…"),
                            class_name="text-sm text-gray-600",
                        ),
                        class_name="flex items-center gap-3",
                    ),
                    class_name="flex w-full items-center justify-center bg-[#F6F5F1]",
                ),
            ),
            class_name="flex h-dvh w-full overflow-hidden bg-[#F6F5F1] font-['Inter'] text-[#182321]",
        )
    )


def error_banner(message: rx.Var | str) -> rx.Component:
    return rx.el.div(
        rx.icon("circle-alert", class_name="h-4 w-4 shrink-0"),
        rx.el.p(translate(message)),
        role="alert",
        class_name="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700",
    )
