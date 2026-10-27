import reflex as rx

from app.components.layout import shell, context_selector, error_banner
from app.states.access_state import AccessState
from app.i18n import translate


def account_field(
    label: str, name: str, field_type: str, placeholder: str
) -> rx.Component:
    return rx.el.div(
        rx.el.label(
            translate(label),
            html_for=f"account-{name}",
            class_name="mb-2 block text-xs font-medium text-[#182321]",
        ),
        rx.el.input(
            id=f"account-{name}",
            name=name,
            type=field_type,
            required=True,
            placeholder=translate(placeholder),
            auto_complete=rx.cond(
                field_type == "password", "new-password", "off"
            ),
            min_length=rx.cond(field_type == "password", 12, 1),
            max_length=rx.match(
                field_type, ("password", 128), ("email", 254), 160
            ),
            class_name="w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-[#182321] placeholder:text-gray-400 focus:outline-2 focus:outline-[#187C72]",
        ),
    )


def account_row(account: dict[str, str]) -> rx.Component:
    return rx.el.tr(
        rx.el.td(
            rx.el.p(
                account["name"], class_name="text-sm font-medium text-[#182321]"
            ),
            rx.el.p(account["email"], class_name="mt-1 text-xs text-gray-500"),
            class_name="px-5 py-4",
        ),
        rx.el.td(
            account["organization"],
            class_name="px-4 py-4 text-xs text-gray-600",
        ),
        rx.el.td(
            rx.el.span(
                translate(account["status"]),
                class_name=rx.cond(
                    account["status"] == "Activa",
                    "w-fit rounded-md bg-green-50 px-2 py-1 text-[10px] font-semibold text-green-700",
                    "w-fit rounded-md bg-gray-100 px-2 py-1 text-[10px] font-semibold text-gray-600",
                ),
            ),
            class_name="px-4 py-4",
        ),
        rx.el.td(
            rx.el.button(
                rx.cond(
                    account["status"] == "Activa",
                    translate("Suspender acceso"),
                    translate("Activar acceso"),
                ),
                on_click=lambda: AccessState.toggle_account(account["id"]),
                disabled=AccessState.busy | AccessState.loading,
                aria_label=rx.cond(
                    AccessState.language == "en",
                    f"Change access for {account['name']}",
                    f"Cambiar acceso de {account['name']}",
                ),
                class_name="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-medium text-[#182321] hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-50",
            ),
            class_name="px-5 py-4 text-right",
        ),
        key=account["id"],
        class_name="border-t border-gray-100 bg-white even:bg-gray-50/50 hover:bg-gray-50",
    )


def account_form() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.h2(
                translate("Crear acceso de cliente"),
                class_name="text-base font-semibold text-[#182321]",
            ),
            rx.el.p(
                translate(
                    "Cada cuenta pertenece a una única organización. No se conceden permisos de administrador desde este formulario."
                ),
                class_name="mt-2 text-xs leading-5 text-gray-600",
            ),
            class_name="border-b border-gray-100 p-5",
        ),
        rx.el.form(
            account_field(
                "Nombre completo", "name", "text", "Nombre y apellido"
            ),
            account_field(
                "Correo electrónico", "email", "email", "nombre@empresa.com"
            ),
            rx.el.div(
                rx.el.label(
                    translate("Organización asignada"),
                    html_for="account-client",
                    class_name="mb-2 block text-xs font-medium text-[#182321]",
                ),
                rx.el.div(
                    rx.el.select(
                        rx.el.option(
                            translate("Selecciona una organización"),
                            value="",
                            disabled=True,
                        ),
                        rx.foreach(
                            AccessState.clients,
                            lambda c: rx.el.option(c["name"], value=c["id"]),
                        ),
                        id="account-client",
                        name="client",
                        required=True,
                        default_value=rx.cond(
                            AccessState.context == "network",
                            "",
                            AccessState.context,
                        ),
                        key=AccessState.context,
                        class_name="w-full appearance-none rounded-lg border border-gray-300 bg-white py-2.5 pl-3 pr-9 text-sm text-[#182321] focus:outline-2 focus:outline-[#187C72]",
                    ),
                    rx.icon(
                        "chevron-down",
                        class_name="pointer-events-none absolute right-3 top-3 h-4 w-4 text-gray-500",
                    ),
                    class_name="relative",
                ),
            ),
            account_field(
                "Contraseña inicial",
                "password",
                "password",
                "Entre 12 y 128 caracteres",
            ),
            rx.el.p(
                translate(
                    "Entrega la contraseña por un canal seguro. No se mostrará ni se guardará en el resumen de cuentas."
                ),
                class_name="text-xs leading-5 text-gray-500",
            ),
            rx.el.button(
                rx.cond(
                    AccessState.busy,
                    rx.icon("loader-circle", class_name="h-4 w-4 animate-spin"),
                    rx.icon("user-plus", class_name="h-4 w-4"),
                ),
                rx.cond(
                    AccessState.busy,
                    translate("Procesando…"),
                    translate("Crear cuenta de cliente"),
                ),
                type="submit",
                disabled=AccessState.busy | AccessState.loading,
                class_name="flex w-full items-center justify-center gap-2 rounded-lg bg-[#187C72] px-4 py-3 text-sm font-semibold text-white hover:bg-[#12645C] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#187C72] disabled:opacity-50",
            ),
            on_submit=AccessState.create_account,
            reset_on_submit=True,
            class_name="flex flex-col gap-5 p-5",
        ),
        class_name="w-full rounded-xl border border-gray-200 bg-white",
    )


def accounts_page() -> rx.Component:
    return shell(
        rx.cond(
            AccessState.role == "admin",
            rx.el.div(
                rx.el.div(
                    rx.el.div(
                        rx.el.p(
                            translate("ADMINISTRACIÓN DE RED"),
                            class_name="text-[10px] font-semibold tracking-[0.15em] text-[#187C72]",
                        ),
                        rx.el.h1(
                            translate("Cuentas de clientes"),
                            class_name="mt-2 text-2xl font-semibold tracking-tight text-[#182321]",
                        ),
                        rx.el.p(
                            translate(
                                "Controla quién accede a cada flota. Sin registro público ni selección libre de organización."
                            ),
                            class_name="mt-2 text-sm text-gray-600",
                        ),
                    ),
                    context_selector(),
                    class_name="mb-6 flex flex-col justify-between gap-5 xl:flex-row xl:items-center",
                ),
                rx.cond(
                    AccessState.error != "",
                    rx.el.div(
                        error_banner(AccessState.error), class_name="mb-4"
                    ),
                ),
                rx.cond(
                    AccessState.account_error != "",
                    rx.el.div(
                        error_banner(AccessState.account_error),
                        class_name="mb-4",
                    ),
                ),
                rx.cond(
                    AccessState.account_success != "",
                    rx.el.div(
                        rx.icon("circle-check", class_name="h-4 w-4 shrink-0"),
                        rx.el.p(translate(AccessState.account_success)),
                        role="status",
                        class_name="mb-4 flex items-start gap-2 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700",
                    ),
                ),
                rx.el.div(
                    account_form(),
                    rx.el.section(
                        rx.el.div(
                            rx.el.h2(
                                translate("Accesos asignados"),
                                class_name="text-base font-semibold text-[#182321]",
                            ),
                            rx.el.p(
                                rx.cond(
                                    AccessState.language == "en",
                                    f"{AccessState.accounts.length()} accounts in selected context",
                                    f"{AccessState.accounts.length()} cuentas en el contexto seleccionado",
                                ),
                                class_name="mt-1 text-xs text-gray-500",
                            ),
                            class_name="p-5",
                        ),
                        rx.cond(
                            AccessState.accounts.length() > 0,
                            rx.el.div(
                                rx.el.table(
                                    rx.el.thead(
                                        rx.el.tr(
                                            rx.el.th(
                                                translate("Usuario"),
                                                class_name="px-5 py-3 text-left",
                                            ),
                                            rx.el.th(
                                                translate("Organización"),
                                                class_name="px-4 py-3 text-left",
                                            ),
                                            rx.el.th(
                                                translate("Estado"),
                                                class_name="px-4 py-3 text-left",
                                            ),
                                            rx.el.th(
                                                translate("Acceso"),
                                                class_name="px-5 py-3 text-right",
                                            ),
                                            class_name="border-t border-gray-100 bg-gray-50 text-[10px] uppercase tracking-wide text-gray-500",
                                        )
                                    ),
                                    rx.el.tbody(
                                        rx.foreach(
                                            AccessState.accounts, account_row
                                        )
                                    ),
                                    class_name="table-auto w-full min-w-[600px]",
                                ),
                                class_name="overflow-x-auto",
                            ),
                            rx.el.div(
                                rx.icon(
                                    "users", class_name="h-8 w-8 text-gray-400"
                                ),
                                rx.el.p(
                                    translate("Aún no hay cuentas de cliente"),
                                    class_name="text-sm font-medium text-[#182321]",
                                ),
                                rx.el.p(
                                    translate(
                                        "Crea la primera cuenta y asigna su organización. Después, cierra tu sesión para probar el acceso del cliente."
                                    ),
                                    class_name="max-w-sm text-xs leading-5 text-gray-500",
                                ),
                                class_name="flex flex-col items-center gap-3 border-t border-gray-100 bg-white px-5 py-12 text-center",
                            ),
                        ),
                        rx.el.p(
                            translate(
                                "Suspender una cuenta bloquea nuevos inicios de sesión y las siguientes consultas de sesiones existentes. Las cuentas de administrador no se gestionan aquí."
                            ),
                            class_name="border-t border-gray-100 p-5 text-xs leading-5 text-gray-500",
                        ),
                        class_name="w-full min-w-0 overflow-hidden rounded-xl border border-gray-200 bg-white",
                    ),
                    class_name="grid w-full min-w-0 grid-cols-1 items-start gap-6 xl:grid-cols-[340px_minmax(0,1fr)]",
                ),
                class_name="w-full min-w-0",
            ),
            rx.el.div(
                rx.icon("shield-alert", class_name="h-8 w-8 text-[#187C72]"),
                rx.el.h1(
                    translate("Acceso restringido"),
                    class_name="text-xl font-semibold text-[#182321]",
                ),
                rx.el.p(
                    translate(
                        "Solo el administrador de la red puede gestionar cuentas."
                    ),
                    class_name="text-sm text-gray-600",
                ),
                rx.el.a(
                    translate("Volver a mi resumen"),
                    href="/summary",
                    class_name="rounded-lg bg-[#187C72] px-4 py-2 text-sm text-white focus-visible:outline-2 focus-visible:outline-[#187C72]",
                ),
                class_name="flex flex-col items-center gap-4 rounded-xl border border-gray-200 bg-white px-5 py-12 text-center",
            ),
        )
    )
