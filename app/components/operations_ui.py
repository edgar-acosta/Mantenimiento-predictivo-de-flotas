import reflex as rx

from app.components.layout import context_selector, error_banner
from app.i18n import translate
from app.states.access_state import AccessState


def field(
    label: str,
    name: str,
    value: rx.Var | str = "",
    kind: str = "text",
    required: bool = False,
    step: str = "0.01",
) -> rx.Component:
    return rx.el.div(
        rx.el.label(
            translate(label),
            html_for=name,
            class_name="mb-1.5 block text-xs font-medium text-gray-600",
        ),
        rx.el.input(
            id=name,
            name=name,
            type=kind,
            default_value=value,
            key=f"{name}:{value}",
            required=required,
            step=step,
            min=rx.cond(kind == "number", "0", ""),
            max_length=4000,
            class_name="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm text-[#182321] focus:outline-2 focus:outline-[#187C72]",
        ),
        class_name="min-w-0",
    )


def notes_field(
    label: str, name: str, value: rx.Var | str = "", required: bool = False
) -> rx.Component:
    return rx.el.div(
        rx.el.label(
            translate(label),
            html_for=name,
            class_name="mb-1.5 block text-xs font-medium text-gray-600",
        ),
        rx.el.textarea(
            id=name,
            name=name,
            default_value=value,
            key=f"{name}:{value}",
            required=required,
            max_length=4000,
            rows=3,
            class_name="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm text-[#182321] focus:outline-2 focus:outline-[#187C72]",
        ),
        class_name="min-w-0 md:col-span-2",
    )


def choice(
    label: str,
    name: str,
    options: list[str] | rx.Var,
    value: rx.Var | str = "",
    scope: str = "ops",
) -> rx.Component:
    return rx.el.div(
        rx.el.label(
            translate(label),
            html_for=f"{scope}-{name}",
            class_name="mb-1.5 block text-xs font-medium text-gray-600",
        ),
        rx.el.div(
            rx.el.select(
                rx.foreach(
                    options,
                    lambda option: rx.el.option(
                        rx.cond(
                            option == "", translate("Todos"), translate(option)
                        ),
                        value=option,
                    ),
                ),
                id=f"{scope}-{name}",
                name=name,
                default_value=value,
                key=f"{name}:{value}",
                class_name="w-full appearance-none rounded-lg border border-gray-200 bg-white py-2.5 pl-3 pr-9 text-sm text-[#182321] focus:outline-2 focus:outline-[#187C72]",
            ),
            rx.icon(
                "chevron-down",
                class_name="pointer-events-none absolute right-3 top-3 h-4 w-4 text-gray-500",
            ),
            class_name="relative",
        ),
        class_name="min-w-0",
    )


def entity_choice(
    label: str,
    name: str,
    options: rx.Var,
    label_key: str,
    value: rx.Var | str = "",
    required: bool = False,
) -> rx.Component:
    return rx.el.div(
        rx.el.label(
            translate(label),
            html_for=name,
            class_name="mb-1.5 block text-xs font-medium text-gray-600",
        ),
        rx.el.div(
            rx.el.select(
                rx.el.option("—", value=""),
                rx.foreach(
                    options,
                    lambda option: rx.el.option(
                        translate(option[label_key]), value=option["id"]
                    ),
                ),
                id=name,
                name=name,
                default_value=value,
                key=f"{name}:{value}",
                required=required,
                class_name="w-full appearance-none rounded-lg border border-gray-200 bg-white py-2.5 pl-3 pr-9 text-sm text-[#182321] focus:outline-2 focus:outline-[#187C72]",
            ),
            rx.icon(
                "chevron-down",
                class_name="pointer-events-none absolute right-3 top-3 h-4 w-4 text-gray-500",
            ),
            class_name="relative",
        ),
    )


def fact(label: str, value: rx.Var | str) -> rx.Component:
    return rx.el.div(
        rx.el.dt(translate(label), class_name="text-xs text-gray-500"),
        rx.el.dd(
            rx.cond(
                value != "",
                translate(value),
                translate("Sin límite documentado"),
            ),
            class_name="mt-1 break-words text-sm font-medium text-[#182321]",
        ),
        class_name="min-w-0",
    )


def status_badge(value: rx.Var | str) -> rx.Component:
    return rx.el.span(
        translate(value),
        class_name=rx.cond(
            (value == "approved")
            | (value == "paid")
            | (value == "completed")
            | (value == "installed"),
            "inline-flex w-fit rounded-md bg-[#187C72]/10 px-2 py-1 text-xs font-semibold text-[#187C72]",
            "inline-flex w-fit rounded-md bg-[#E5A547]/15 px-2 py-1 text-xs font-semibold text-[#805410]",
        ),
    )


def empty_message(message: str) -> rx.Component:
    return rx.el.p(
        translate(message),
        class_name="rounded-lg border border-dashed border-gray-200 bg-gray-50 p-5 text-sm text-gray-600",
    )


def workspace_header(
    title: str, description: str, refresh: rx.event.EventType, disabled: rx.Var
) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.p(
                translate("DAIMLER · MANTENIMIENTO DE FLOTA"),
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
                on_click=refresh,
                disabled=disabled,
                class_name="flex w-fit items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-[#187C72] hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-[#187C72] disabled:opacity-50",
            ),
            class_name="flex flex-col gap-3",
        ),
        class_name="mb-6 flex flex-col justify-between gap-5 xl:flex-row",
    )


def workspace_feedback(
    error: rx.Var, success: rx.Var, loading: rx.Var
) -> rx.Component:
    return rx.el.div(
        rx.cond(error != "", error_banner(error)),
        rx.cond(
            success != "",
            rx.el.p(
                translate(success),
                role="status",
                class_name="rounded-lg border border-[#187C72]/20 bg-[#187C72]/10 p-3 text-sm text-[#187C72]",
            ),
        ),
        rx.cond(
            loading,
            rx.el.div(
                rx.icon(
                    "loader-circle",
                    class_name="h-4 w-4 animate-spin text-[#187C72]",
                ),
                translate("Cargando…"),
                role="status",
                class_name="flex items-center gap-2 text-sm text-gray-600",
            ),
        ),
        class_name="mb-5 flex flex-col gap-3",
    )


def save_button(label: str, busy: rx.Var) -> rx.Component:
    return rx.el.button(
        translate(label),
        type="submit",
        disabled=busy,
        class_name="w-fit rounded-lg bg-[#187C72] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#12645C] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#187C72] disabled:opacity-50",
    )
