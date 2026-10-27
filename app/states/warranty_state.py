import reflex as rx

import asyncio
import logging
import time
from datetime import date
from typing import Any
from app.operations import (
    CLAIM_FIELDS,
    CONTRACT_FIELDS,
    load_warranty,
    save_claim,
)
from app.security import AccessDenied


class WarrantyState(rx.State):
    search: str = ""
    status: str = ""
    expiration: str = ""
    page: int = 1
    total: int = 0
    claim_page: int = 1
    claim_total: int = 0
    selected: int = 0
    claim_id: int = 0
    rows: list[dict[str, str]] = []
    detail: dict[str, str] = dict.fromkeys(
        CONTRACT_FIELDS + ["unit", "mileage", "hours", "eligible"], ""
    )
    coverage: list[dict[str, str]] = []
    claims: list[dict[str, str]] = []
    orders: list[dict[str, str]] = []
    draft: dict[str, str] = dict.fromkeys(CLAIM_FIELDS, "")
    editing: bool = False
    loading: bool = False
    busy: bool = False
    ready: bool = False
    context: str = ""
    error: str = ""
    success: str = ""
    _request: int = 0

    @rx.var
    def claim_status_options(self) -> list[str]:
        from app.operations import CLAIM_TRANSITIONS

        status = self.draft.get("status") or "draft"
        return [status, *sorted(CLAIM_TRANSITIONS.get(status, set()))]

    @rx.var
    def page_count(self) -> int:
        return max(1, (self.total + 24) // 25)

    def _clear_view(self) -> None:
        self._request += 1
        self.rows, self.coverage, self.claims, self.orders = [], [], [], []
        self.detail = dict.fromkeys(
            CONTRACT_FIELDS + ["unit", "mileage", "hours", "eligible"], ""
        )
        self.draft = dict.fromkeys(CLAIM_FIELDS, "")
        self.selected = self.claim_id = 0
        self.total = self.claim_total = 0
        self.page = self.claim_page = 1
        self.editing = self.ready = self.loading = self.busy = False
        self.context = self.error = self.success = ""

    @rx.event
    def load(self):
        self._clear_view()
        self.page = self.claim_page = 1
        raw = str(
            self.router.url.query_parameters.get(
                "contract", self.router.page.params.get("contract", "")
            )
        )
        self.selected = int(raw) if raw.isdigit() else 0
        return WarrantyState.refresh

    @rx.event
    def filter_contracts(self, form_data: dict[str, Any]):
        self.search = str(form_data.get("search", ""))[:100]
        self.status = str(form_data.get("status", ""))
        self.expiration = str(form_data.get("expiration", ""))
        self.page = 1
        self.selected = 0
        self.editing = False
        return WarrantyState.refresh

    @rx.event
    def select_contract(self, target: str):
        self.selected = int(target) if target.isdigit() else 0
        self.claim_page = 1
        self.editing = False
        self.success = ""
        return WarrantyState.refresh

    @rx.event
    def paginate(self, section: str, delta: int):
        if section == "claims":
            self.claim_page = min(
                max(1, (self.claim_total + 19) // 20),
                max(1, self.claim_page + delta),
            )
        else:
            self.page = min(self.page_count, max(1, self.page + delta))
        return WarrantyState.refresh

    @rx.event
    def new_claim(self):
        self.claim_id = 0
        self.draft = dict.fromkeys(CLAIM_FIELDS, "")
        self.draft.update(
            status="draft",
            failure_on=date.today().isoformat(),
            requested_amount="0.00",
            approved_amount="0.00",
            paid_amount="0.00",
            deductible_amount=self.detail.get("deductible", "0"),
            odometer_km=self.detail.get("mileage", "0"),
            engine_hours=self.detail.get("hours", "0"),
        )
        self.editing = True
        self.error = self.success = ""

    @rx.event
    def edit_claim(self, target: str):
        row = next((c for c in self.claims if c["id"] == target), None)
        if row:
            self.claim_id = int(target)
            self.draft = row.copy()
            self.editing = True
            self.error = self.success = ""

    @rx.event
    def close_editor(self):
        self.editing = False

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
                self.search,
                self.status,
                self.expiration,
                self.page,
                self.selected,
                self.claim_page,
            )
            self.loading, self.ready, self.error = True, False, ""
        try:
            result = await asyncio.to_thread(
                load_warranty, uid, expires, context, *args
            )
            async with self:
                access = await self.get_state(AccessState)
                if (
                    epoch != access._epoch
                    or context != access.context
                    or request != self._request
                ):
                    return
                self.rows, self.total = result["rows"], result["total"]
                self.detail = result["detail"] or dict.fromkeys(
                    CONTRACT_FIELDS + ["unit", "mileage", "hours", "eligible"],
                    "",
                )
                self.coverage, self.claims, self.orders = (
                    result["coverage"],
                    result["claims"],
                    result["orders"],
                )
                self.claim_total = result["claim_total"]
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
                        else "No se pudo cargar garantías. Inténtalo de nuevo."
                    )

    @rx.event(background=True)
    async def submit_claim(self, form_data: dict[str, Any]):
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
            target, claim_id = self.selected, self.claim_id
            self.busy, self.error, self.success = True, "", ""
        data = {str(k): str(v) for k, v in form_data.items()}
        try:
            await asyncio.to_thread(
                save_claim, uid, expires, context, target, claim_id, data
            )
            async with self:
                access = await self.get_state(AccessState)
                if (
                    epoch != access._epoch
                    or context != access.context
                    or target != self.selected
                ):
                    return
                self.editing = False
                self.success = "Reclamación guardada. La cobertura potencial no constituye aprobación del proveedor."
            yield WarrantyState.refresh
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
                        else "No se pudo guardar la reclamación. Inténtalo de nuevo."
                    )
        finally:
            async with self:
                access = await self.get_state(AccessState)
                if epoch == access._epoch and context == access.context:
                    self.busy = False
