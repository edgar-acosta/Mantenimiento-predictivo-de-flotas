import reflex as rx

from app.demo import seed_startup
from app.pages.login import login_page
from app.pages.summary import summary_page
from app.pages.accounts import accounts_page
from app.pages.units import unit_page, units_page
from app.pages.warranty import warranty_page
from app.pages.orders import orders_page
from app.states.access_state import AccessState
from app.states.units_state import UnitsState
from app.states.warranty_state import WarrantyState
from app.states.orders_state import OrdersState


def index() -> rx.Component:
    return summary_page()


app = rx.App(
    theme=rx.theme(appearance="light"),
    head_components=[
        rx.el.link(rel="preconnect", href="https://fonts.googleapis.com"),
        rx.el.link(
            rel="preconnect",
            href="https://fonts.gstatic.com",
            cross_origin="",
        ),
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap",
            rel="stylesheet",
        ),
    ],
)
app.register_lifespan_task(seed_startup)
app.add_page(
    unit_page,
    route="/units/[id]",
    title="Daimler · Detalle de unidad",
    on_load=[AccessState.load, UnitsState.load_unit],
)
app.add_page(
    units_page,
    route="/units",
    title="Daimler · Inventario de flota",
    on_load=[AccessState.load, UnitsState.load_inventory],
)
app.add_page(
    index,
    route="/",
    title="Daimler · Resumen de mantenimiento",
    on_load=AccessState.load,
)
app.add_page(
    index,
    route="/summary",
    title="Daimler · Resumen de mantenimiento",
    on_load=AccessState.load,
)
app.add_page(
    login_page,
    route="/login",
    title="Daimler · Acceso privado",
    on_load=AccessState.prepare_login,
)
app.add_page(
    accounts_page,
    route="/admin/accounts",
    title="Daimler · Cuentas de clientes",
    on_load=AccessState.load,
)
app.add_page(
    warranty_page,
    route="/warranty",
    title="Daimler · Garantías / Warranty",
    on_load=[AccessState.load, WarrantyState.load],
)
app.add_page(
    orders_page,
    route="/orders",
    title="Daimler · Órdenes de servicio / Service orders",
    on_load=[AccessState.load, OrdersState.load],
)
