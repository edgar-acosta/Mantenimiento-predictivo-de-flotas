import reflex as rx

import os
import time
import unittest
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch
from sqlalchemy import select
from app.models import (
    AppUser,
    ClientOrganization,
    Fleet,
    OrderPart,
    ServiceOrder,
    Unit,
    WarrantyClaim,
    WarrantyContract,
    WarrantyCoverage,
)
from app.operations import (
    CLAIM_FIELDS,
    ORDER_FIELDS,
    PART_FIELDS,
    day,
    eligibility,
    load_orders,
    load_warranty,
    money,
    save_claim,
    save_order,
    save_part,
    serialize,
    user_preferences,
)
from app.security import AccessDenied, password_hash


class ValidationTests(unittest.TestCase):
    def test_currency_and_quantity_validation(self):
        self.assertEqual(money("12.34"), Decimal("12.34"))
        self.assertEqual(money("1.125", places=3), Decimal("1.125"))
        for value in ("-1", "NaN", "Infinity", "abc", "1.001", "1000000000000"):
            with self.assertRaises(ValueError):
                money(value)
        with self.assertRaises(ValueError):
            day("2026-02-30")

    def test_expired_sessions_cannot_read_or_write(self):
        with patch.object(rx, "session") as factory:
            session = factory.return_value.__enter__.return_value
            expired = time.time() - 10
            for operation in (
                lambda: load_orders(1, expired, "network", "2026-01", 1, 0, 1),
                lambda: load_warranty(
                    1, expired, "network", "", "", "", 1, 0, 1
                ),
                lambda: save_claim(1, expired, "network", 1, 0, {}),
                lambda: save_order(1, expired, "network", 1, {}),
                lambda: save_part(1, expired, "network", 1, 0, {}),
                lambda: user_preferences(1, expired, "en", "dark"),
            ):
                with self.assertRaises(AccessDenied):
                    operation()
            session.scalar.assert_not_called()
            session.add.assert_not_called()
            session.commit.assert_not_called()

    def test_eligibility_is_not_approval_and_checks_start_usage(self):
        contract = WarrantyContract(
            status="active",
            starts_on=date.today() - timedelta(days=1),
            ends_on=date.today() + timedelta(days=1),
            starting_odometer_km=Decimal(100),
            mileage_limit_km=Decimal(200),
            starting_engine_hours=Decimal(10),
            engine_hours_limit=Decimal(20),
        )
        unit = Unit(odometer_km=Decimal(150), engine_hours=Decimal(15))
        self.assertTrue(eligibility(contract, unit))
        unit.odometer_km = Decimal(99)
        self.assertFalse(eligibility(contract, unit))
        unit.odometer_km = Decimal(201)
        self.assertFalse(eligibility(contract, unit))


@unittest.skipUnless(
    os.getenv("RUN_FLEET_DB_TESTS") == "1",
    "Opt-in managed database rollback tests",
)
class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.context_manager = rx.session()
        self.session = self.context_manager.__enter__()
        session = self.session
        self.units = []
        self.orgs = []
        for label in ("A", "B"):
            org = ClientOrganization(
                display_name=f"Workflow rollback {label}",
                legal_name="Workflow rollback",
                status="active",
            )
            session.add(org)
            session.flush()
            fleet = Fleet(client_id=org.id, name="Rollback workflow")
            session.add(fleet)
            session.flush()
            unit = Unit(
                fleet_id=fleet.id,
                unit_number=f"WF-{org.id}",
                odometer_km=Decimal(100),
                engine_hours=Decimal(10),
            )
            session.add(unit)
            session.flush()
            self.units.append(unit)
            self.orgs.append(org)
        client = AppUser(
            client_id=self.orgs[0].id,
            role="client",
            email=f"workflow-{self.orgs[0].id}@example.test",
            password_hash=password_hash("Rollback testing passphrase"),
            is_active=True,
        )
        admin = AppUser(
            role="admin",
            email=f"workflow-admin-{self.orgs[0].id}@example.test",
            password_hash=password_hash("Rollback testing passphrase"),
            is_active=True,
        )
        session.add_all([client, admin])
        session.flush()
        self.uid, self.admin = client.id, admin.id
        self.expires = time.time() + 3600
        self.contracts, self.orders, self.coverages = [], [], []
        for unit in self.units:
            c = WarrantyContract(
                unit_id=unit.id,
                contract_number=f"WF-{unit.id}",
                provider_name="Rollback provider",
                status="active",
                starts_on=date.today() - timedelta(days=100),
                ends_on=date.today() + timedelta(days=100),
                mileage_limit_km=Decimal(1000),
            )
            o = ServiceOrder(
                unit_id=unit.id,
                order_number=f"WF-{unit.id}",
                title="Rollback service",
                component_code="engine",
                status="draft",
            )
            session.add_all([c, o])
            session.flush()
            coverage = WarrantyCoverage(
                warranty_contract_id=c.id,
                component_code="engine",
                system="engine",
            )
            session.add(coverage)
            session.flush()
            self.contracts.append(c)
            self.orders.append(o)
            self.coverages.append(coverage)
        self.commit_patch = patch.object(
            session, "commit", side_effect=session.flush
        )
        self.commit_patch.start()

        @contextmanager
        def shared_session():
            yield session

        self.factory_patch = patch.object(
            rx, "session", side_effect=shared_session
        )
        self.factory_patch.start()

    def tearDown(self):
        self.factory_patch.stop()
        self.commit_patch.stop()
        self.session.rollback()
        self.context_manager.__exit__(None, None, None)

    def order_form(self) -> dict[str, str]:
        data = serialize(self.orders[0], ORDER_FIELDS)
        data.update(
            status="scheduled",
            scheduled_start_at=datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M"
            ),
            scheduled_end_at="",
            due_on=(date.today() + timedelta(days=2)).isoformat(),
            assigned_technician="Rollback technician",
            workshop_name="Rollback workshop",
            progress_percent="0",
            progress_notes="Persisted progress",
        )
        return data

    def claim_form(self) -> dict[str, str]:
        return {
            "status": "draft",
            "warranty_coverage_id": str(self.coverages[0].id),
            "service_order_id": str(self.orders[0].id),
            "failure_on": date.today().isoformat(),
            "failure_description": "Documented failure",
            "requested_amount": "100.00",
            "approved_amount": "0.00",
            "paid_amount": "0.00",
            "deductible_amount": "0.00",
            "odometer_km": "100",
            "engine_hours": "10",
            "notes": "Saved claim progress",
        }

    def test_scope_tampering_and_admin_filter(self):
        for context in ("network", str(self.orgs[1].id)):
            result = load_warranty(
                self.uid, self.expires, context, "WF-", "", "", 1, 0, 1
            )
            self.assertEqual(
                [r["unit_id"] for r in result["rows"]], [str(self.units[0].id)]
            )
            for operation in (
                lambda: save_order(
                    self.uid, self.expires, context, self.orders[1].id, {}
                ),
                lambda: save_part(
                    self.uid, self.expires, context, self.orders[1].id, 0, {}
                ),
                lambda: save_claim(
                    self.uid, self.expires, context, self.contracts[1].id, 0, {}
                ),
            ):
                with self.assertRaises(AccessDenied):
                    operation()
        with self.assertRaises(AccessDenied):
            save_order(
                self.admin,
                self.expires,
                str(self.orgs[0].id),
                self.orders[1].id,
                {},
            )
        data = self.claim_form()
        data["service_order_id"] = str(self.orders[1].id)
        with self.assertRaises(AccessDenied):
            save_claim(
                self.uid, self.expires, "network", self.contracts[0].id, 0, data
            )
        data = self.claim_form()
        data["warranty_coverage_id"] = str(self.coverages[1].id)
        with self.assertRaises(ValueError):
            save_claim(
                self.uid, self.expires, "network", self.contracts[0].id, 0, data
            )

    def test_saved_orders_calendar_parts_and_completion(self):
        target = self.orders[0].id
        form = self.order_form()
        save_order(self.uid, self.expires, "network", target, form)
        loaded = load_orders(
            self.uid,
            self.expires,
            "network",
            date.today().strftime("%Y-%m"),
            1,
            target,
            1,
        )
        self.assertEqual(
            loaded["detail"]["progress_notes"], "Persisted progress"
        )
        self.assertEqual(loaded["calendar_total"], 1)
        self.assertEqual(loaded["calendar_orders"][0]["id"], str(target))
        part = {
            "part_number": "P-001",
            "description": "Replacement part",
            "quantity_required": "2",
            "quantity_ordered": "2",
            "quantity_received": "0",
            "quantity_installed": "0",
            "estimated_unit_cost": "25.00",
            "status": "ordered",
        }
        save_part(self.uid, self.expires, "network", target, 0, part)
        saved = self.session.scalar(
            select(OrderPart).where(OrderPart.service_order_id == target)
        )
        part.update(
            quantity_received="2",
            quantity_installed="2",
            actual_unit_cost="23.50",
            status="installed",
        )
        save_part(self.uid, self.expires, "network", target, saved.id, part)
        data = serialize(self.orders[0], ORDER_FIELDS)
        data.update(status="in_progress", progress_percent="40")
        save_order(self.uid, self.expires, "network", target, data)
        data = serialize(self.orders[0], ORDER_FIELDS)
        data.update(
            status="completed",
            progress_percent="100",
            actual_parts_cost="47.00",
        )
        save_order(self.uid, self.expires, "network", target, data)
        loaded = load_orders(
            self.uid,
            self.expires,
            "network",
            date.today().strftime("%Y-%m"),
            1,
            target,
            1,
        )
        self.assertEqual(loaded["detail"]["status"], "completed")
        self.assertEqual(loaded["detail"]["actual"], "47.00")
        self.assertEqual(loaded["parts"][0]["quantity_installed"], "2.000")
        with self.assertRaises(ValueError):
            save_part(self.uid, self.expires, "network", target, saved.id, part)

    def test_claim_progress_amounts_and_preferences_survive_queries(self):
        target = save_claim(
            self.uid,
            self.expires,
            "network",
            self.contracts[0].id,
            0,
            self.claim_form(),
        )
        claim = self.session.get(WarrantyClaim, target)
        self.assertEqual(claim.notes, "Saved claim progress")
        for status in ("submitted", "under_review", "approved", "paid"):
            data = serialize(claim, CLAIM_FIELDS)
            data["status"] = status
            if status in ("approved", "paid"):
                data.update(
                    approved_amount="100.00",
                    decision_reason="Documented provider approval",
                    provider_reference="PROVIDER-1",
                )
            if status == "paid":
                data["paid_amount"] = "100.00"
            save_claim(
                self.uid,
                self.expires,
                "network",
                self.contracts[0].id,
                target,
                data,
            )
        loaded = load_warranty(
            self.uid,
            self.expires,
            "network",
            "",
            "",
            "",
            1,
            self.contracts[0].id,
            1,
        )
        self.assertEqual(loaded["claims"][0]["status"], "paid")
        self.assertEqual(loaded["claims"][0]["paid_amount"], "100.00")
        self.assertTrue(loaded["claims"][0]["paid_at"])
        self.assertEqual(
            user_preferences(self.uid, self.expires, "en", "dark"),
            ("en", "dark"),
        )
        self.assertEqual(
            user_preferences(self.uid, self.expires), ("en", "dark")
        )
        data = serialize(claim, CLAIM_FIELDS)
        data["paid_amount"] = "101.00"
        with self.assertRaises(ValueError):
            save_claim(
                self.uid,
                self.expires,
                "network",
                self.contracts[0].id,
                target,
                data,
            )


if __name__ == "__main__":
    unittest.main()
