import reflex as rx
import reflex_xy

import asyncio
import logging
import time
from contextlib import suppress
from typing import Any
from app.security import (
    AccessDenied,
    authenticate,
    bootstrap_available,
    provision,
    toggle_client_user,
)
from app.queries import Summary, load_summary


def _load_summary_or_none(
    uid: int, expires: float, context: str
) -> Summary | None:
    with suppress(AccessDenied):
        return load_summary(uid, expires, context)
    return None


class AccessState(rx.State):
    _user_id: int = 0
    _expires: float = 0.0
    _epoch: int = 0
    authenticated: bool = False
    bootstrap: bool = False
    ready: bool = False
    busy: bool = False
    loading: bool = False
    error: str = ""
    account_error: str = ""
    account_success: str = ""
    name: str = ""
    role: str = ""
    context: str = "network"
    title: str = "Resumen de la red"
    clients: list[dict[str, str]] = []
    accounts: list[dict[str, str]] = []
    active: int = 0
    high_risk: int = 0
    overdue: int = 0
    cost: float = 0.0
    unit_count: int = 0
    actions: list[dict[str, str]] = []
    dates: list[str] = []
    risk30: list[float] = []
    risk90: list[float] = []
    updated: str = ""
    language: str = "es"
    theme: str = "light"
    preferences_busy: bool = False

    @rx.var(auto_deps=False, deps=["language"])
    def translations(self) -> dict[str, str]:
        from app.i18n import TRANSLATIONS, STATUS_EN, STATUS_ES

        return (
            {**TRANSLATIONS, **STATUS_EN}
            if self.language == "en"
            else STATUS_ES
        )

    @rx.event(background=True)
    async def toggle_language(self):
        async with self:
            self.preferences_busy = self.preferences_busy
        async for event in self._save_preferences(True):
            yield event

    @rx.event(background=True)
    async def toggle_theme(self):
        async with self:
            self.preferences_busy = self.preferences_busy
        async for event in self._save_preferences(False):
            yield event

    async def _save_preferences(self, language_toggle: bool):
        from app.operations import user_preferences

        async with self:
            if self.preferences_busy:
                return
            uid, expires, epoch = self._user_id, self._expires, self._epoch
            language = (
                ("en" if self.language == "es" else "es")
                if language_toggle
                else self.language
            )
            theme = (
                self.theme
                if language_toggle
                else ("dark" if self.theme == "light" else "light")
            )
            self.preferences_busy = True
        try:
            if uid:
                language, theme = await asyncio.to_thread(
                    user_preferences, uid, expires, language, theme
                )
            async with self:
                if epoch != self._epoch:
                    return
                self.language, self.theme = language, theme
                path = str(self.router.page.path)
            if uid and language_toggle:
                yield AccessState.load
                if path.startswith("/units"):
                    from app.states.units_state import UnitsState

                    yield UnitsState.refresh
                elif path == "/warranty":
                    from app.states.warranty_state import WarrantyState

                    yield WarrantyState.refresh
                elif path == "/orders":
                    from app.states.orders_state import OrdersState

                    yield OrdersState.refresh
        except Exception as e:
            logging.exception(f"Error: {e}")
            async with self:
                if epoch == self._epoch:
                    self.error = (
                        "No se pudo guardar preferencias. Inténtalo de nuevo."
                    )
        finally:
            async with self:
                if epoch == self._epoch:
                    self.preferences_busy = False

    @reflex_xy.data
    def trend(self) -> dict[str, list[str] | list[float]]:
        return {
            "date": self.dates,
            "risk30": self.risk30,
            "risk90": self.risk90,
        }

    def _clear_session(self) -> None:
        self._epoch += 1
        self._user_id = 0
        self._expires = 0.0
        self.authenticated = False
        self.name = ""
        self.role = ""
        self.context = "network"
        self.title = "Resumen de la red"
        self.clients = []
        self.accounts = []
        self.actions = []
        self.dates = []
        self.risk30 = []
        self.risk90 = []
        self.active = 0
        self.high_risk = 0
        self.overdue = 0
        self.cost = 0.0
        self.unit_count = 0
        self.updated = ""
        self.busy = False
        self.loading = False
        self.account_error = ""
        self.account_success = ""

    async def _clear_protected_session(self) -> None:
        from app.states.units_state import UnitsState
        from app.states.warranty_state import WarrantyState
        from app.states.orders_state import OrdersState

        units = await self.get_state(UnitsState)
        warranty = await self.get_state(WarrantyState)
        orders = await self.get_state(OrdersState)
        units._clear_view()
        warranty._clear_view()
        orders._clear_view()
        self._clear_session()

    async def _guard_session(self) -> bool:
        if self._user_id and time.time() < self._expires:
            return False
        if self._user_id:
            self.error = "Tu sesión ha finalizado. Inicia sesión de nuevo."
        await self._clear_protected_session()
        return True

    def _apply(self, summary: Summary) -> None:
        self.language = summary.get("language", self.language)
        self.theme = summary.get("theme", self.theme)
        self.name = summary["name"]
        self.role = summary["role"]
        self.context = summary["context"]
        self.title = summary["title"]
        self.clients = summary["clients"]
        self.accounts = summary["accounts"]
        self.active = summary["active"]
        self.high_risk = summary["high_risk"]
        self.overdue = summary["overdue"]
        self.cost = summary["cost"]
        self.unit_count = summary["unit_count"]
        self.actions = summary["actions"]
        self.dates = summary["dates"]
        self.risk30 = summary["risk30"]
        self.risk90 = summary["risk90"]
        self.updated = summary["updated"]
        self.authenticated = True

    @rx.event
    async def logout(self):
        from app.states.units_state import UnitsState

        units = await self.get_state(UnitsState)
        units._clear_view()
        from app.states.warranty_state import WarrantyState
        from app.states.orders_state import OrdersState

        warranty = await self.get_state(WarrantyState)
        orders = await self.get_state(OrdersState)
        warranty._clear_view()
        orders._clear_view()
        self._clear_session()
        self.error = ""
        self.ready = False
        return rx.redirect("/login")

    @rx.event(background=True)
    async def prepare_login(self):
        async with self:
            uid, expires, epoch = self._user_id, self._expires, self._epoch
            if self.error != "Tu sesión ha finalizado. Inicia sesión de nuevo.":
                self.error = ""
            self.ready = False
        try:
            if uid:
                summary = await asyncio.to_thread(
                    _load_summary_or_none, uid, expires, "network"
                )
                async with self:
                    if epoch != self._epoch:
                        return
                    if summary is None:
                        await self._clear_protected_session()
                        epoch = self._epoch
                    else:
                        self._apply(summary)
                if summary is not None:
                    yield rx.redirect("/summary")
                    return
            available = await asyncio.to_thread(bootstrap_available)
            async with self:
                if epoch == self._epoch:
                    self.bootstrap = available
                    self.ready = True

        except Exception as e:
            logging.exception(f"Error: {e}")
            async with self:
                if epoch == self._epoch:
                    self.error = "No se pudo conectar. Vuelve a intentar en unos momentos."
                    self.ready = True

    @rx.event(background=True)
    async def sign_in(self, form_data: dict[str, Any]):
        async with self:
            if self.busy:
                return
            self.busy = True
            self.error = ""
            bootstrap, epoch = self.bootstrap, self._epoch
            language, theme = self.language, self.theme
        email = str(form_data.get("email", "")).strip().lower()
        password = str(form_data.get("password", ""))
        name = str(form_data.get("name", ""))
        if bootstrap and password != str(form_data.get("confirm", "")):
            async with self:
                if epoch == self._epoch:
                    self.error = "Las contraseñas no coinciden."
                    self.busy = False
            return
        try:
            uid, error = await asyncio.to_thread(
                authenticate, email, password, name, bootstrap
            )
            if error:
                available = await asyncio.to_thread(bootstrap_available)
                async with self:
                    if epoch == self._epoch:
                        self.error = error
                        self.bootstrap = available
                        self.busy = False
                return
            expires = time.time() + 8 * 3600
            if bootstrap:
                from app.operations import user_preferences

                await asyncio.to_thread(
                    user_preferences, uid, expires, language, theme
                )
            summary = await asyncio.to_thread(
                load_summary, uid, expires, "network"
            )
            async with self:
                if epoch != self._epoch:
                    return
                self._user_id = uid
                self._expires = expires
                self._apply(summary)
                self.busy = False
                self.bootstrap = False
            yield rx.redirect("/summary")
        except Exception as e:
            logging.exception(f"Error: {e}")
            async with self:
                if epoch == self._epoch:
                    self.error = (
                        "No se pudo iniciar sesión. Inténtalo de nuevo."
                    )
                    self.busy = False

    @rx.event(background=True)
    async def load(self):
        async with self:
            denied = await self._guard_session()
            uid, expires, context, epoch = (
                self._user_id,
                self._expires,
                self.context,
                self._epoch,
            )
            if not denied:
                self.loading = True
                self.error = ""
        if denied:
            yield rx.redirect("/login")
            return
        try:
            summary = await asyncio.to_thread(
                _load_summary_or_none, uid, expires, context
            )
            async with self:
                if epoch != self._epoch:
                    return
                if summary is None:
                    await self._clear_protected_session()
                    self.error = (
                        "Tu sesión ha finalizado. Inicia sesión de nuevo."
                    )
                else:
                    self._apply(summary)
                    self.loading = False
            if summary is None:
                yield rx.redirect("/login")
        except Exception as e:
            logging.exception(f"Error: {e}")
            async with self:
                if epoch == self._epoch:
                    self.error = "No se pudo cargar el resumen. Utiliza Actualizar para reintentar."
                    self.loading = False

    @rx.event(background=True)
    async def switch_context(self, form_data: dict[str, Any]):
        async with self:
            if self.loading or self.busy:
                return
            uid, expires, epoch = self._user_id, self._expires, self._epoch
            self.loading = True
            self.error = ""
        context = str(form_data.get("context", "network"))
        try:
            with_admin = await asyncio.to_thread(
                self._check_admin, uid, expires
            )
            if not with_admin:
                raise AccessDenied(
                    "Solo el administrador puede cambiar de organización."
                )
            summary = await asyncio.to_thread(
                load_summary, uid, expires, context
            )
            async with self:
                if epoch == self._epoch:
                    self._apply(summary)
                    from app.states.units_state import UnitsState

                    units = await self.get_state(UnitsState)
                    units._clear_view()
                    units.fleet_filter = ""
                    units.page = 1
                    from app.states.warranty_state import WarrantyState
                    from app.states.orders_state import OrdersState

                    warranty = await self.get_state(WarrantyState)
                    orders = await self.get_state(OrdersState)
                    warranty._clear_view()
                    orders._clear_view()
                    path = str(self.router.page.path)
                else:
                    path = ""
            if path.startswith("/units"):
                yield UnitsState.refresh
            elif path == "/warranty":
                yield WarrantyState.refresh
            elif path == "/orders":
                yield OrdersState.refresh
        except AccessDenied as e:
            logging.exception("Unexpected error")
            async with self:
                if epoch == self._epoch:
                    self.error = str(e)
        except Exception as e:
            logging.exception(f"Error: {e}")
            async with self:
                if epoch == self._epoch:
                    self.error = (
                        "No se pudo cambiar de contexto. Inténtalo de nuevo."
                    )
        finally:
            async with self:
                if epoch == self._epoch:
                    self.loading = False

    def _check_admin(self, uid: int, expires: float) -> bool:
        from app.security import authorize

        with rx.session() as session:
            authorize(session, uid, expires, admin=True)
            return True

    @rx.event(background=True)
    async def create_account(self, form_data: dict[str, Any]):
        async with self:
            if self.busy or self.loading:
                return
            uid, expires, context, epoch = (
                self._user_id,
                self._expires,
                self.context,
                self._epoch,
            )
            self.busy = True
            self.account_error = ""
            self.account_success = ""
        try:
            error = await asyncio.to_thread(
                provision,
                uid,
                expires,
                str(form_data.get("email", "")).strip().lower(),
                str(form_data.get("password", "")),
                str(form_data.get("name", "")),
                str(form_data.get("client", "")),
            )
            summary = await asyncio.to_thread(
                load_summary, uid, expires, context
            )
            async with self:
                if epoch == self._epoch:
                    self._apply(summary)
                    self.account_error = error
                    self.account_success = (
                        ""
                        if error
                        else "Cuenta creada. Comunica la contraseña al usuario por un canal seguro; ya puede iniciar sesión."
                    )
        except AccessDenied as e:
            logging.exception("Unexpected error")
            async with self:
                if epoch == self._epoch:
                    self.account_error = str(e)
        except Exception as e:
            logging.exception(f"Error: {e}")
            async with self:
                if epoch == self._epoch:
                    self.account_error = (
                        "No se pudo crear la cuenta. Inténtalo de nuevo."
                    )
        finally:
            async with self:
                if epoch == self._epoch:
                    self.busy = False

    @rx.event(background=True)
    async def toggle_account(self, target: str):
        async with self:
            if self.busy or self.loading:
                return
            uid, expires, context, epoch = (
                self._user_id,
                self._expires,
                self.context,
                self._epoch,
            )
            self.busy = True
            self.account_error = ""
            self.account_success = ""
        try:
            await asyncio.to_thread(
                toggle_client_user, uid, expires, int(target), context
            )
            summary = await asyncio.to_thread(
                load_summary, uid, expires, context
            )
            async with self:
                if epoch == self._epoch:
                    self._apply(summary)
                    self.account_success = "Estado de la cuenta actualizado."
        except AccessDenied as e:
            logging.exception("Unexpected error")
            async with self:
                if epoch == self._epoch:
                    self.account_error = str(e)
        except Exception as e:
            logging.exception(f"Error: {e}")
            async with self:
                if epoch == self._epoch:
                    self.account_error = "No se pudo actualizar la cuenta."
        finally:
            async with self:
                if epoch == self._epoch:
                    self.busy = False
