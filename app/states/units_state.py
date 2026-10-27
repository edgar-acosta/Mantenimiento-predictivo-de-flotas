import reflex as rx

import asyncio
import logging
import time
from typing import Any
from app.security import AccessDenied
from app.unit_queries import (
    MEDIA_LIMIT,
    create_service_order,
    load_detail,
    load_inventory,
    read_evidence,
    save_evidence,
)


class UnitsState(rx.State):
    search: str = ""
    fleet_filter: str = ""
    risk_filter: str = ""
    warranty_filter: str = ""
    page: int = 1
    total: int = 0
    rows: list[dict[str, str]] = []
    fleets: list[dict[str, str]] = []
    context: str = ""
    loading: bool = False
    busy: bool = False
    ready: bool = False
    error: str = ""
    success: str = ""
    selected_unit: int = 0
    unit: dict[str, str] = {
        "id": "",
        "number": "",
        "vin": "",
        "plate": "",
        "model": "",
        "fleet": "",
        "status": "",
        "mileage": "",
        "hours": "",
        "observed": "",
        "source": "",
        "active_faults": "0",
    }
    predictions: list[dict[str, str]] = []
    latest: list[dict[str, str]] = []
    telemetry: list[dict[str, str]] = []
    faults: list[dict[str, str]] = []
    services: list[dict[str, str]] = []
    warranties: list[dict[str, str]] = []
    evidence: list[dict[str, str]] = []
    telemetry_page: int = 1
    fault_page: int = 1
    service_page: int = 1
    evidence_page: int = 1
    telemetry_total: int = 0
    fault_total: int = 0
    service_total: int = 0
    evidence_total: int = 0
    media_src: str = ""
    media_type: str = ""
    media_name: str = ""
    _detail: bool = False
    _request: int = 0
    _pending_data: bytes = b""
    _pending_name: str = ""
    _pending_unit: int = 0
    _pending_uid: int = 0
    _pending_epoch: int = 0
    _pending_context: str = ""

    @rx.var
    def page_count(self) -> int:
        return max(1, (self.total + 24) // 25)

    def _clear_view(self) -> None:
        self._request += 1
        self.ready = False
        self.rows = []
        self.fleets = []
        self.predictions = []
        self.latest = []
        self.telemetry = []
        self.faults = []
        self.services = []
        self.warranties = []
        self.evidence = []
        self.unit = {key: "" for key in self.unit}
        self.media_src = ""
        self.media_type = ""
        self.media_name = ""
        self._pending_data = b""
        self.context = ""
        self.loading = False
        self.busy = False
        self.success = ""
        self.error = ""

    @rx.event
    def load_inventory(self):
        self._clear_view()
        self._detail = False
        self.page = 1
        return UnitsState.refresh

    @rx.event
    def load_unit(self):
        self._clear_view()
        self._detail = True
        raw = str(self.router.page.params.get("id", ""))
        self.selected_unit = int(raw) if raw.isdigit() else 0
        self.telemetry_page = 1
        self.fault_page = 1
        self.service_page = 1
        self.evidence_page = 1
        return UnitsState.refresh

    @rx.event
    def filters(self, form_data: dict[str, Any]):
        self.search = str(form_data.get("search", ""))[:100]
        self.fleet_filter = str(form_data.get("fleet", ""))
        self.risk_filter = str(form_data.get("risk", ""))
        self.warranty_filter = str(form_data.get("warranty", ""))
        self.page = 1
        return UnitsState.refresh

    @rx.event
    def paginate(self, delta: int):
        self.page = min(self.page_count, max(1, self.page + delta))
        return UnitsState.refresh

    @rx.event
    def history_page(self, section: str, delta: int):
        pages = {
            "telemetry": ("telemetry_page", self.telemetry_total),
            "fault": ("fault_page", self.fault_total),
            "service": ("service_page", self.service_total),
            "evidence": ("evidence_page", self.evidence_total),
        }
        if section not in pages:
            return
        field, total = pages[section]
        setattr(
            self,
            field,
            min(
                max(1, (total + 19) // 20), max(1, getattr(self, field) + delta)
            ),
        )
        self.media_src = ""
        return UnitsState.refresh

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
            detail, target = self._detail, self.selected_unit
            search, fleet, risk, warranty, page = (
                self.search,
                self.fleet_filter,
                self.risk_filter,
                self.warranty_filter,
                self.page,
            )
            history_pages = (
                self.telemetry_page,
                self.fault_page,
                self.service_page,
                self.evidence_page,
            )
            self.loading = True
            self.ready = False
            self.media_src = ""
            self.error = ""
        try:
            if detail:
                result = await asyncio.to_thread(
                    load_detail, uid, expires, context, target, *history_pages
                )
            else:
                result = await asyncio.to_thread(
                    load_inventory,
                    uid,
                    expires,
                    context,
                    search,
                    fleet,
                    risk,
                    warranty,
                    page,
                )
            async with self:
                access = await self.get_state(AccessState)
                if (
                    request != self._request
                    or epoch != access._epoch
                    or context != access.context
                ):
                    return
                self.context = result["context"]
                if detail:
                    self.unit = result["unit"]
                    self.predictions = result["predictions"]
                    self.latest = result["latest"]
                    self.telemetry = result["telemetry"]
                    self.faults = result["faults"]
                    self.services = result["services"]
                    self.warranties = result["warranties"]
                    self.evidence = result["evidence"]
                    self.telemetry_total = result["telemetry_total"]
                    self.fault_total = result["fault_total"]
                    self.service_total = result["service_total"]
                    self.evidence_total = result["evidence_total"]
                else:
                    self.rows = result["rows"]
                    self.fleets = result["fleets"]
                    self.page = result["page"]
                    self.total = result["total"]
                self.ready = True
                self.loading = False

        except AccessDenied as e:
            logging.exception("Unexpected error")
            async with self:
                access = await self.get_state(AccessState)
                if request == self._request and epoch == access._epoch:
                    self._clear_view()
                    self.error = str(e)
        except Exception as e:
            logging.exception(f"Error: {e}")
            async with self:
                access = await self.get_state(AccessState)
                if request == self._request and epoch == access._epoch:
                    self._clear_view()
                    self.error = (
                        str(e)
                        if isinstance(e, ValueError)
                        else "No se pudo cargar la unidad o flota. Vuelve a intentar."
                    )

    @rx.event(background=True)
    async def create_order(self, prediction: str):
        from app.states.access_state import AccessState

        async with self:
            if self.busy:
                return
            access = await self.get_state(AccessState)
            uid, expires, epoch, context = (
                access._user_id,
                access._expires,
                access._epoch,
                access.context,
            )
            target = self.selected_unit
            self.busy = True
            self.error = ""
            self.success = ""
        try:
            message = await asyncio.to_thread(
                create_service_order,
                uid,
                expires,
                context,
                target,
                int(prediction),
            )
            async with self:
                access = await self.get_state(AccessState)
                if (
                    epoch != access._epoch
                    or context != access.context
                    or target != self.selected_unit
                ):
                    return
                self.success = message
            yield UnitsState.refresh
        except Exception as e:
            logging.exception(f"Error: {e}")
            async with self:
                access = await self.get_state(AccessState)
                if (
                    epoch == access._epoch
                    and context == access.context
                    and target == self.selected_unit
                ):
                    self.error = (
                        str(e)
                        if isinstance(e, (ValueError, AccessDenied))
                        else "No se pudo guardar la orden. Inténtalo de nuevo."
                    )
        finally:
            async with self:
                access = await self.get_state(AccessState)
                if epoch == access._epoch:
                    self.busy = False

    @rx.event
    async def upload(self, files: list[rx.UploadFile]):
        from app.states.access_state import AccessState

        if self.busy:
            return
        self.error = ""
        if len(files) != 1 or not self.ready:
            self.error = (
                "Selecciona un solo archivo para una unidad disponible."
            )
            return
        access = await self.get_state(AccessState)
        self._pending_uid = access._user_id
        self._pending_epoch = access._epoch
        self._pending_context = access.context
        self._pending_unit = self.selected_unit
        try:
            data = await files[0].read(MEDIA_LIMIT + 1)
            if not data or len(data) > MEDIA_LIMIT:
                self.error = "Archivo vacío o mayor a 8 MB."
                return
            self._pending_data = data
            self._pending_name = str(files[0].name or "evidencia")
            self.busy = True
            yield UnitsState.process_upload
        except Exception as e:
            logging.exception(f"Error: {e}")
            self.error = "No se pudo recibir el archivo."

    @rx.event(background=True)
    async def process_upload(self):
        from app.states.access_state import AccessState

        async with self:
            access = await self.get_state(AccessState)
            data, name, target = (
                self._pending_data,
                self._pending_name,
                self._pending_unit,
            )
            uid, epoch, context = (
                self._pending_uid,
                self._pending_epoch,
                self._pending_context,
            )
            expires = access._expires
            self._pending_data = b""
            valid = (
                uid == access._user_id
                and epoch == access._epoch
                and context == access.context
                and target == self.selected_unit
            )
        try:
            if not valid:
                raise AccessDenied(
                    "El contexto cambió. Selecciona de nuevo el archivo."
                )
            await asyncio.to_thread(
                save_evidence, uid, expires, context, target, data, name
            )
            async with self:
                access = await self.get_state(AccessState)
                if (
                    epoch == access._epoch
                    and context == access.context
                    and target == self.selected_unit
                ):
                    self.success = "Evidencia guardada de forma privada; no se generó una URL pública."
            yield rx.clear_selected_files("unit-evidence")
            yield UnitsState.refresh
        except Exception as e:
            logging.exception(f"Error: {e}")
            async with self:
                access = await self.get_state(AccessState)
                if (
                    epoch == access._epoch
                    and context == access.context
                    and target == self.selected_unit
                ):
                    self.error = (
                        str(e)
                        if isinstance(e, (AccessDenied, ValueError))
                        else "No se pudo validar o guardar la evidencia."
                    )
        finally:
            async with self:
                access = await self.get_state(AccessState)
                if epoch == access._epoch:
                    self.busy = False

    @rx.event(background=True)
    async def view_evidence(self, evidence: str):
        from app.states.access_state import AccessState

        async with self:
            if self.busy:
                return
            access = await self.get_state(AccessState)
            uid, expires, epoch, context = (
                access._user_id,
                access._expires,
                access._epoch,
                access.context,
            )
            target, request = self.selected_unit, self._request
            self.busy = True
            self.media_src = ""
        try:
            src, kind, name = await asyncio.to_thread(
                read_evidence, uid, expires, context, target, int(evidence)
            )
            async with self:
                access = await self.get_state(AccessState)
                if (
                    epoch == access._epoch
                    and context == access.context
                    and request == self._request
                ):
                    self.media_src, self.media_type, self.media_name = (
                        src,
                        kind,
                        name,
                    )
        except Exception as e:
            logging.exception(f"Error: {e}")
            async with self:
                access = await self.get_state(AccessState)
                if epoch == access._epoch and request == self._request:
                    self.error = (
                        str(e)
                        if isinstance(e, (AccessDenied, ValueError))
                        else "No se pudo abrir la evidencia."
                    )
        finally:
            async with self:
                access = await self.get_state(AccessState)
                if epoch == access._epoch:
                    self.busy = False

    @rx.event
    def close_media(self):
        self.media_src = ""
        self.media_name = ""
        self.media_type = ""
