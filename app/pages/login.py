import reflex as rx

from app.components.layout import brand, error_banner, preference_controls
from app.i18n import themed, translate
from app.states.access_state import AccessState


def login_field(
    label: str, name: str, field_type: str, placeholder: str, autocomplete: str
) -> rx.Component:
    return rx.el.div(
        rx.el.label(
            translate(label),
            html_for=name,
            class_name="mb-2 block text-sm font-medium text-[#182321]",
        ),
        rx.el.input(
            id=name,
            name=name,
            type=field_type,
            placeholder=translate(placeholder),
            auto_complete=autocomplete,
            required=True,
            max_length=rx.cond(field_type == "password", 128, 254),
            class_name="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm text-[#182321] placeholder:text-gray-400 focus:border-[#187C72] focus:outline-2 focus:outline-[#187C72]",
        ),
    )


def login_page() -> rx.Component:
    return themed(
        rx.el.main(
            rx.el.section(
                brand(),
                rx.el.div(
                    rx.el.p(
                        translate("MANTENIMIENTO INTELIGENTE"),
                        class_name="text-xs font-medium tracking-[0.2em] text-[#E5A547]",
                    ),
                    rx.el.h1(
                        translate(
                            "Cada unidad cuenta.\nCada decisión también."
                        ),
                        class_name="mt-6 whitespace-pre-line text-4xl font-semibold leading-tight tracking-tight text-white xl:text-5xl",
                    ),
                    rx.el.p(
                        translate(
                            "Una visión clara de tu flota, sus riesgos y las acciones que no pueden esperar."
                        ),
                        class_name="mt-6 max-w-md text-base leading-7 text-white/60",
                    ),
                    class_name="my-auto py-16",
                ),
                rx.el.div(
                    rx.icon(
                        "shield-check", class_name="h-5 w-5 text-[#E5A547]"
                    ),
                    rx.el.p(
                        translate("Acceso privado por organización"),
                        class_name="text-sm text-white/80",
                    ),
                    class_name="flex items-center gap-3 border-t border-white/15 pt-6",
                ),
                class_name="hidden min-h-dvh w-[45%] flex-col bg-[#182321] p-12 lg:flex xl:p-16",
            ),
            rx.el.section(
                rx.el.div(
                    rx.el.div(
                        rx.icon("truck", class_name="h-7 w-7 text-[#187C72]"),
                        rx.el.p(
                            "DAIMLER · Fleet maintenance",
                            class_name="text-sm font-semibold text-[#182321]",
                        ),
                        class_name="mb-12 flex items-center gap-3 lg:hidden",
                    ),
                    rx.el.div(
                        preference_controls(),
                        class_name="mb-6 flex justify-end",
                    ),
                    rx.el.div(
                        rx.icon(
                            "lock-keyhole", class_name="h-5 w-5 text-[#187C72]"
                        ),
                        class_name="mb-6 flex h-12 w-12 items-center justify-center rounded-xl border border-[#187C72]/20 bg-[#187C72]/5",
                    ),
                    rx.el.p(
                        rx.cond(
                            AccessState.bootstrap,
                            translate("CONFIGURACIÓN INICIAL"),
                            translate("BIENVENIDO A TU CENTRO DE CONTROL"),
                        ),
                        class_name="text-[10px] font-semibold tracking-[0.15em] text-gray-500",
                    ),
                    rx.el.h2(
                        rx.cond(
                            AccessState.bootstrap,
                            translate("Configura el administrador"),
                            translate("Inicia sesión"),
                        ),
                        class_name="mt-3 text-3xl font-semibold tracking-tight text-[#182321]",
                    ),
                    rx.el.p(
                        rx.cond(
                            AccessState.bootstrap,
                            translate(
                                "La primera cuenta administra la red. Después podrás crear accesos privados para cada cliente."
                            ),
                            translate(
                                "Accede con la cuenta asignada por tu administrador."
                            ),
                        ),
                        class_name="mt-3 text-sm leading-6 text-gray-600",
                    ),
                    rx.cond(
                        AccessState.error != "",
                        rx.el.div(
                            error_banner(AccessState.error), class_name="mt-5"
                        ),
                    ),
                    rx.cond(
                        AccessState.ready,
                        rx.el.form(
                            rx.cond(
                                AccessState.bootstrap,
                                login_field(
                                    "Nombre del administrador",
                                    "name",
                                    "text",
                                    "Nombre y apellido",
                                    "name",
                                ),
                            ),
                            login_field(
                                "Correo electrónico",
                                "email",
                                "email",
                                "nombre@empresa.com",
                                "username",
                            ),
                            login_field(
                                "Contraseña",
                                "password",
                                "password",
                                "Tu contraseña",
                                rx.cond(
                                    AccessState.bootstrap,
                                    "new-password",
                                    "current-password",
                                ),
                            ),
                            rx.cond(
                                AccessState.bootstrap,
                                rx.fragment(
                                    rx.el.p(
                                        translate(
                                            "Usa entre 12 y 128 caracteres. No se crean contraseñas de demostración."
                                        ),
                                        class_name="text-xs leading-5 text-gray-500",
                                    ),
                                    login_field(
                                        "Confirmar contraseña",
                                        "confirm",
                                        "password",
                                        "Repite la contraseña",
                                        "new-password",
                                    ),
                                ),
                            ),
                            rx.el.button(
                                rx.cond(
                                    AccessState.busy,
                                    rx.icon(
                                        "loader-circle",
                                        class_name="h-4 w-4 animate-spin",
                                    ),
                                    rx.icon(
                                        "arrow-right", class_name="h-4 w-4"
                                    ),
                                ),
                                rx.cond(
                                    AccessState.busy,
                                    translate("Procesando…"),
                                    rx.cond(
                                        AccessState.bootstrap,
                                        translate("Crear administrador"),
                                        translate("Entrar al resumen"),
                                    ),
                                ),
                                type="submit",
                                disabled=AccessState.busy,
                                class_name="mt-2 flex w-full items-center justify-center gap-3 rounded-lg bg-[#187C72] px-4 py-3 text-sm font-semibold text-white hover:bg-[#12645C] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#187C72] disabled:cursor-wait disabled:opacity-60",
                            ),
                            on_submit=AccessState.sign_in,
                            reset_on_submit=True,
                            class_name="mt-7 flex flex-col gap-5",
                        ),
                        rx.el.div(
                            class_name="mt-7 h-44 animate-pulse rounded-xl bg-gray-200",
                            aria_label=translate("Cargando acceso"),
                        ),
                    ),
                    rx.el.p(
                        translate(
                            "Sin registro público. Si necesitas acceso o recuperar tu cuenta, contacta al administrador de la red."
                        ),
                        class_name="mt-7 border-t border-gray-200 pt-6 text-xs leading-5 text-gray-500",
                    ),
                    rx.el.div(
                        rx.icon(
                            "flask-conical",
                            class_name="h-4 w-4 shrink-0 text-[#187C72]",
                        ),
                        rx.el.p(
                            translate(
                                "SYNTHETIC · Las cinco flotas y sus riesgos son datos ficticios de demostración."
                            ),
                            class_name="text-xs leading-5 text-gray-600",
                        ),
                        class_name="mt-8 flex items-start gap-2 rounded-lg border border-gray-200 bg-white p-3",
                    ),
                    class_name="w-full max-w-md",
                ),
                class_name="flex min-h-dvh w-full flex-1 items-center justify-center bg-[#F6F5F1] px-6 py-10 lg:px-12",
            ),
            class_name="flex min-h-dvh w-full bg-[#F6F5F1] font-['Inter'] text-[#182321]",
        )
    )
