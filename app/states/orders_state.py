import reflex as rx

import asyncio
import logging
import time
from datetime import date
from typing import Any
from app.operations import (
    ORDER_FIELDS,
    PART_FIELDS,
    load_orders,
    save_order,
    save_part,
)
from app.security import AccessDenied


class OrdersState(rx.State):
    month: str = date.today().strftime("%Y-%m")
    page: int = 1
    selected: int = 0
    part_page: int = 1
    part_total: int = 0
    calendar_total: int = 0
    calendar_page: int = 1
    columns: list[dict[str, str]] = []
    cards: list[dict[str, str]] = []
    days: list[dict[str, str]] = []
    calendar_orders: list[dict[str, str]] = []
    detail: dict[str, str] = dict.fromkeys(
        ORDER_FIELDS + ["unit", "estimated", "actual", "prediction"], ""
    )
    parts: list[dict[str, str]] = []
    warranties: list[dict[str, str]] = []
    claims: list[dict[str, str]] = []
    part_id: int = 0
    part_draft: dict[str, str] = dict.fromkeys(PART_FIELDS, "")
    editing_part: bool = False
    loading: bool = False
    busy: bool = False
    ready: bool = False
    context: str = ""
    error: str = ""
    success: str = ""
    _request: int = 0

    @rx.var
    def calendar_pages(self) -> int:
        return max(1, (self.calendar_total + 499) // 500)

    @rx.var
    def cards_by_status(self) -> dict[str, list[dict[str, str]]]:
        from app.operations import ORDER_STATES

        return {
            status: [card for card in self.cards if card["status"] == status]
            for status in ORDER_STATES
        }

    @rx.var
    def order_status_options(self) -> list[str]:
        from app.operations import ORDER_TRANSITIONS

        status = self.detail.get("status") or "draft"
        return [status, *sorted(ORDER_TRANSITIONS.get(status, set()))]

    @rx.var
    def board_pages(self) -> int:
        return max(
            1,
            max((int(c["count"]) + 14) // 15 for c in self.columns)
            if self.columns
            else 1,
        )

    def _clear_view(self) -> None:
        self._request += 1
        self.columns, self.cards, self.days, self.calendar_orders = (
            [],
            [],
            [],
            [],
        )
        self.parts, self.warranties, self.claims = [], [], []
        self.detail = dict.fromkeys(
            ORDER_FIELDS + ["unit", "estimated", "actual", "prediction"], ""
        )
        self.part_draft = dict.fromkeys(PART_FIELDS, "")
        self.selected = self.part_id = self.part_total = self.calendar_total = 0
        self.page = self.part_page = self.calendar_page = 1
        self.editing_part = self.loading = self.busy = self.ready = False
        self.context = self.error = self.success = ""

    @rx.event
    def load(self):
        self._clear_view()
        self.page = self.part_page = self.calendar_page = 1
        raw = str(
            self.router.url.query_parameters.get(
                "order", self.router.page.params.get("order", "")
            )
        )
        self.selected = int(raw) if raw.isdigit() else 0
        return OrdersState.refresh

    @rx.event
    def select_order(self, target: str):
        self.selected = int(target) if target.isdigit() else 0
        self.part_page = 1
        self.editing_part = False
        self.success = ""
        return OrdersState.refresh

    @rx.event
    def change_month(self, form_data: dict[str, Any]):
        raw = str(form_data.get("month", ""))
        try:
            date.fromisoformat(f"{raw}-01")
        except ValueError as e:
            logging.exception(f"Error: {e}")
            self.error = "Selecciona un mes válido."
            return
        self.month = raw
        self.calendar_page = 1
        return OrdersState.refresh

    @rx.event
    def move_month(self, delta: int):
        first = date.fromisoformat(f"{self.month}-01")
        ordinal = first.year * 12 + first.month - 1 + delta
        year, month = divmod(ordinal, 12)
        if 1900 <= year <= 2200:
            self.month = f"{year:04d}-{month + 1:02d}"
            self.calendar_page = 1
        return OrdersState.refresh

    @rx.event
    def paginate(self, section: str, delta: int):
        if section == "parts":
            self.part_page = min(
                max(1, (self.part_total + 19) // 20),
                max(1, self.part_page + delta),
            )
        elif section == "calendar":
            self.calendar_page = min(
                self.calendar_pages, max(1, self.calendar_page + delta)
            )
        else:
            self.page = min(self.board_pages, max(1, self.page + delta))
        return OrdersState.refresh

    @rx.event
    def new_part(self):
        self.part_id = 0
        self.part_draft = dict.fromkeys(PART_FIELDS, "")
        self.part_draft.update(
            quantity_required="1",
            quantity_ordered="0",
            quantity_received="0",
            quantity_installed="0",
            estimated_unit_cost="0.00",
            status="needed",
            component_code=self.detail.get("component_code", ""),
        )
        self.editing_part = True

    @rx.event
    def edit_part(self, target: str):
        row = next((p for p in self.parts if p["id"] == target), None)
        if row:
            self.part_id = int(target)
            self.part_draft = row.copy()
            self.editing_part = True

    @rx.event
    def close_part(self):
        self.editing_part = False

    @rx.event(background=True)
    async def refresh(self):
        from app.states.access_state import AccessState

        async with self:
            access = await self.get_state(AccessState)
            uid, expires, epoch, context = (
                access._user_id,
                access._expires,
                access._epoch,
                access.context,
            )
            if not uid or time.time() >= expires:
                self._clear_view()
                return
            self._request += 1
            request = self._request
            args = (
                self.month,
                self.page,
                self.selected,
                self.part_page,
                self.calendar_page,
            )
            self.loading, self.ready, self.error = True, False, ""
        try:
            result = await asyncio.to_thread(
                load_orders, uid, expires, context, *args
            )
            async with self:
                access = await self.get_state(AccessState)
                if (
                    epoch != access._epoch
                    or context != access.context
                    or request != self._request
                ):
                    return
                self.columns, self.cards, self.days = (
                    result["columns"],
                    result["cards"],
                    result["days"],
                )
                self.calendar_orders, self.calendar_total = (
                    result["calendar_orders"],
                    result["calendar_total"],
                )
                self.detail = result["detail"] or dict.fromkeys(
                    ORDER_FIELDS
                    + ["unit", "estimated", "actual", "prediction"],
                    "",
                )
                self.parts, self.part_total = (
                    result["parts"],
                    result["part_total"],
                )
                self.warranties, self.claims = (
                    result["warranties"],
                    result["claims"],
                )
                self.context, self.ready, self.loading = context, True, False

        except AccessDenied as e:
            logging.exception("Unexpected error")
            async with self:
                access = await self.get_state(AccessState)
                if (
                    epoch == access._epoch
                    and context == access.context
                    and request == self._request
                ):
                    self._clear_view()
                    self.error = str(e)
        except Exception as e:
            logging.exception(f"Error: {e}")
            async with self:
                access = await self.get_state(AccessState)
                if (
                    epoch == access._epoch
                    and context == access.context
                    and request == self._request
                ):
                    self._clear_view()
                    self.error = (
                        str(e)
                        if isinstance(e, ValueError)
                        else "No se pudo cargar órdenes. Inténtalo de nuevo."
                    )

    async def _save(self, data: dict[str, str], is_part: bool):
        from app.states.access_state import AccessState

        async with self:
            if self.busy or self.loading:
                return
            access = await self.get_state(AccessState)
            uid, expires, epoch, context = (
                access._user_id,
                access._expires,
                access._epoch,
                access.context,
            )
            target, part_id = self.selected, self.part_id
            self.busy, self.error, self.success = True, "", ""
        try:
            if is_part:
                await asyncio.to_thread(
                    save_part, uid, expires, context, target, part_id, data
                )
            else:
                await asyncio.to_thread(
                    save_order, uid, expires, context, target, data
                )
            async with self:
                access = await self.get_state(AccessState)
                if (
                    epoch != access._epoch
                    or context != access.context
                    or target != self.selected
                ):
                    return
                self.editing_part = False
                self.success = "Cambios guardados en base de datos."
            yield OrdersState.refresh
        except Exception as e:
            logging.exception(f"Error: {e}")
            async with self:
                access = await self.get_state(AccessState)
                if (
                    epoch == access._epoch
                    and context == access.context
                    and target == self.selected
                ):
                    self.error = (
                        str(e)
                        if isinstance(e, (ValueError, AccessDenied))
                        else "No se pudo guardar. Inténtalo de nuevo."
                    )
        finally:
            async with self:
                access = await self.get_state(AccessState)
                if epoch == access._epoch and context == access.context:
                    self.busy = False

    @rx.event(background=True)
    async def submit_order(self, form_data: dict[str, Any]):
        async with self:
            self.busy = self.busy
        async for event in self._save(
            {str(k): str(v) for k, v in form_data.items()}, False
        ):
            yield event

    @rx.event(background=True)
    async def submit_part(self, form_data: dict[str, Any]):
        async with self:
            self.busy = self.busy
        async for event in self._save(
            {str(k): str(v) for k, v in form_data.items()}, True
        ):
            yield event
