import reflex as rx

import io
import os
import time
import unittest
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image
from sqlalchemy import func, select
from app.models import (
    AppUser,
    ClientOrganization,
    ComponentPrediction,
    Evidence,
    Fleet,
    ServiceOrder,
    TelemetrySnapshot,
    Unit,
    WarrantyContract,
    WarrantyCoverage,
)
from app.prediction_engine import (
    FEATURES,
    SYSTEMS,
    VERSION,
    features_for,
    infer_seeded_units,
    risk_level,
    synthetic_examples,
    trained_models,
)
from app.security import AccessDenied, password_hash
from app.unit_queries import (
    create_service_order,
    load_detail,
    load_inventory,
    owned_unit,
    read_evidence,
    save_evidence,
    validated_media,
    warranty_review,
)


class PredictionTests(unittest.TestCase):
    def test_reproducible_stochastic_training_examples(self):
        x, y = synthetic_examples()
        other_x, other_y = synthetic_examples()
        np.testing.assert_array_equal(x, other_x)
        np.testing.assert_array_equal(y, other_y)
        self.assertEqual(x.shape, (5000, len(FEATURES)))
        self.assertEqual(y.shape, (5000, 5))
        self.assertTrue(np.isfinite(x).all())
        for i in range(5):
            self.assertEqual(set(y[:, i]), {0, 1, 2})
        self.assertNotEqual(float(np.std(x[:, 7])), 0)

    def test_trained_classifier_calibration_and_holdout(self):
        models, metrics, artifact, trained_at = trained_models()
        self.assertEqual(len(models), 5)
        self.assertEqual(len(artifact), 64)
        self.assertIsNotNone(trained_at.tzinfo)
        test_x, _ = synthetic_examples(seed=51821, count=250)
        for system, model in zip(SYSTEMS, models):
            p = model.predict_proba(test_x)
            self.assertTrue(np.isfinite(p).all())
            self.assertTrue(((p >= 0) & (p <= 1)).all())
            np.testing.assert_allclose(p.sum(axis=1), 1, atol=1e-6)
            self.assertTrue((p[:, 0] <= p[:, 0] + p[:, 1]).all())
            self.assertEqual(metrics[system]["test_rows"], 1250)
            self.assertGreater(metrics[system]["auc30"], 0.5)
            self.assertGreater(metrics[system]["auc90"], 0.5)
            self.assertLess(metrics[system]["brier30"], 0.25)
            self.assertLess(metrics[system]["brier90"], 0.25)
        self.assertIs(models, trained_models()[0])

    def test_feature_order_and_missing_sensor_defaults(self):
        t = TelemetrySnapshot(
            odometer_km=Decimal(123456),
            engine_hours=Decimal(1234),
            idle_percent=Decimal(20),
            harsh_braking_events=3,
            harsh_acceleration_events=4,
            overspeed_events=5,
        )
        x = features_for(t, {"engine": 2, "tires": 1})
        self.assertEqual(x.shape, (1, 17))
        self.assertEqual(x[0, 2], 2)
        self.assertEqual(x[0, 6], 1)
        self.assertEqual(x[0, 7], 35)
        self.assertEqual(x[0, -1], 20)
        self.assertEqual(risk_level(0.61, 0.7), "critical")
        self.assertEqual(risk_level(0.1, 0.7), "high")
        self.assertEqual(risk_level(0.2, 0.4), "medium")
        self.assertEqual(risk_level(0.05, 0.1), "low")


class PrivateMediaTests(unittest.TestCase):
    @staticmethod
    def image_bytes() -> bytes:
        data = io.BytesIO()
        Image.new("RGB", (24, 24), (80, 100, 90)).save(data, format="PNG")
        return data.getvalue()

    def test_image_normalized_to_safe_jpeg(self):
        clean, mime, kind = validated_media(self.image_bytes())
        self.assertEqual((mime, kind), ("image/jpeg", "photo"))
        self.assertTrue(clean.startswith(b"\xff\xd8"))
        with Image.open(io.BytesIO(clean)) as image:
            self.assertEqual(image.size, (24, 24))

    def test_untrusted_and_oversized_files_rejected(self):
        for data in (
            b"<svg onload='alert(1)'/>",
            b"<html>unsafe</html>",
            b"",
            b"x" * (8 * 1024 * 1024 + 1),
            b"\x89PNG\r\n\x1a\ninvalid",
        ):
            with self.assertRaises((ValueError, OSError)):
                validated_media(data)

    def test_ownership_query_joins_fleet_scope(self):
        session = MagicMock()
        session.scalar.return_value = None
        with patch("app.unit_queries.scope", return_value=27):
            with self.assertRaises(AccessDenied):
                owned_unit(session, 4, time.time() + 3600, "999", 123)
        sql = str(session.scalar.call_args.args[0])
        self.assertIn("fleet.client_id", sql)
        self.assertIn("unit.id", sql)
        self.assertIn("client_organization.status", sql)

    def test_expired_sessions_reject_all_read_and_write_paths(self):
        with patch.object(rx, "session") as factory:
            session = factory.return_value.__enter__.return_value
            expires = time.time() - 1
            for operation in (
                lambda: load_inventory(
                    1, expires, "network", "", "", "", "", 1
                ),
                lambda: load_detail(1, expires, "network", 1),
                lambda: create_service_order(1, expires, "network", 1, 1),
                lambda: save_evidence(
                    1, expires, "network", 1, self.image_bytes(), "evidence.png"
                ),
                lambda: read_evidence(1, expires, "network", 1, 1),
            ):
                with self.assertRaises(AccessDenied):
                    operation()
            session.scalar.assert_not_called()
            session.add.assert_not_called()

    def test_rejected_ownership_does_not_validate_or_store_media(self):
        with (
            patch.object(rx, "session"),
            patch(
                "app.unit_queries.owned_unit",
                side_effect=AccessDenied("Denied"),
            ),
            patch("app.unit_queries.validated_media") as validator,
        ):
            with self.assertRaises(AccessDenied):
                save_evidence(
                    1,
                    time.time() + 3600,
                    "network",
                    100,
                    b"payload",
                    "file.png",
                )
            validator.assert_not_called()


@unittest.skipUnless(
    os.getenv("RUN_FLEET_DB_TESTS") == "1",
    "Explicit opt-in for managed database integration tests",
)
class ScopedDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.real_context = rx.session()
        self.session = self.real_context.__enter__()
        session = self.session
        clients = []
        for suffix in ("A", "B"):
            org = ClientOrganization(
                display_name=f"Integration fleet {suffix}",
                legal_name="Integration rollback test",
                status="active",
            )
            session.add(org)
            session.flush()
            fleet = Fleet(client_id=org.id, name=f"Integration {suffix}")
            session.add(fleet)
            session.flush()
            unit = Unit(
                fleet_id=fleet.id,
                unit_number=f"TEST-{suffix}",
                odometer_km=Decimal(80000),
                engine_hours=Decimal(2500),
            )
            session.add(unit)
            session.flush()
            clients.append((org, unit))
        self.org_a, self.unit_a = clients[0]
        self.org_b, self.unit_b = clients[1]
        user = AppUser(
            client_id=self.org_a.id,
            role="client",
            email=f"rollback-{self.org_a.id}@example.test",
            password_hash=password_hash("Integration test passphrase"),
            is_active=True,
        )
        admin = AppUser(
            role="admin",
            email=f"rollback-admin-{self.org_a.id}@example.test",
            password_hash=password_hash("Integration test passphrase"),
            is_active=True,
        )
        session.add_all([user, admin])
        session.flush()
        self.uid, self.admin_uid = user.id, admin.id
        self.expires = time.time() + 3600
        self.commit_patch = patch.object(
            session, "commit", side_effect=session.flush
        )
        self.commit_patch.start()

        @contextmanager
        def shared_session():
            yield session

        self.session_patch = patch.object(
            rx, "session", side_effect=shared_session
        )
        self.session_patch.start()

    def tearDown(self):
        self.session_patch.stop()
        self.commit_patch.stop()
        self.session.rollback()
        self.real_context.__exit__(None, None, None)

    def prediction(self, unit: Unit) -> ComponentPrediction:
        now = datetime.now(timezone.utc)
        p = ComponentPrediction(
            unit_id=unit.id,
            system="engine",
            component_code="engine",
            failure_probability_30d=Decimal("0.3"),
            failure_probability_90d=Decimal("0.6"),
            risk_level="medium",
            predicted_at=now,
            valid_until=now + timedelta(days=14),
            model_version=VERSION,
            model_artifact_sha256="a" * 64,
            model_name="Integration test fixture, not trained inference",
            recommended_by=now.date() + timedelta(days=14),
            estimated_repair_cost=Decimal(10000),
            estimated_downtime_hours=Decimal(8),
        )
        self.session.add(p)
        self.session.flush()
        return p

    def test_client_tampering_admin_context_and_private_evidence(self):
        for context in ("network", str(self.org_b.id)):
            inventory = load_inventory(
                self.uid, self.expires, context, "TEST-", "", "", "", 1
            )
            self.assertEqual(
                [r["id"] for r in inventory["rows"]], [str(self.unit_a.id)]
            )
            with self.assertRaises(AccessDenied):
                load_detail(self.uid, self.expires, context, self.unit_b.id)
        with self.assertRaises(AccessDenied):
            load_detail(
                self.admin_uid, self.expires, str(self.org_a.id), self.unit_b.id
            )
        detail = load_detail(
            self.admin_uid, self.expires, str(self.org_b.id), self.unit_b.id
        )
        self.assertEqual(detail["unit"]["id"], str(self.unit_b.id))
        save_evidence(
            self.uid,
            self.expires,
            "network",
            self.unit_a.id,
            PrivateMediaTests.image_bytes(),
            "photo.png",
        )
        e = self.session.scalar(
            select(Evidence).where(Evidence.unit_id == self.unit_a.id)
        )
        self.assertTrue(e.storage_key.startswith("inline-v1:"))
        uri, kind, name = read_evidence(
            self.uid, self.expires, "network", self.unit_a.id, e.id
        )
        self.assertTrue(uri.startswith("data:image/jpeg;base64,"))
        self.assertEqual(kind, "photo")
        self.assertEqual(name, "photo.png")
        with self.assertRaises(AccessDenied):
            read_evidence(
                self.uid, self.expires, "network", self.unit_b.id, e.id
            )
        with self.assertRaises(ValueError):
            read_evidence(
                self.admin_uid, self.expires, "network", self.unit_b.id, e.id
            )
        with self.assertRaises(AccessDenied):
            save_evidence(
                self.uid,
                self.expires,
                "network",
                self.unit_b.id,
                PrivateMediaTests.image_bytes(),
                "photo.png",
            )
        metadata = load_detail(
            self.uid, self.expires, "network", self.unit_a.id
        )["evidence"]
        self.assertNotIn("storage_key", metadata[0])
        self.assertNotIn("base64", str(metadata))

    def test_prediction_order_scope_dedup_and_expiry(self):
        prediction = self.prediction(self.unit_a)
        foreign = self.prediction(self.unit_b)
        first = create_service_order(
            self.uid, self.expires, "network", self.unit_a.id, prediction.id
        )
        second = create_service_order(
            self.uid, self.expires, "network", self.unit_a.id, prediction.id
        )
        self.assertIn("guardada", first)
        self.assertIn("Ya existe", second)
        self.assertEqual(
            self.session.scalar(
                select(func.count())
                .select_from(ServiceOrder)
                .where(ServiceOrder.prediction_id == prediction.id)
            ),
            1,
        )
        with self.assertRaises(ValueError):
            create_service_order(
                self.uid, self.expires, "network", self.unit_a.id, foreign.id
            )
        prediction.predicted_at = datetime.now(timezone.utc) - timedelta(days=2)
        prediction.valid_until = datetime.now(timezone.utc) - timedelta(
            minutes=1
        )
        self.session.flush()
        with self.assertRaises(ValueError):
            create_service_order(
                self.uid, self.expires, "network", self.unit_a.id, prediction.id
            )

    def test_warranty_component_dates_and_mileage(self):
        contract = WarrantyContract(
            unit_id=self.unit_a.id,
            status="active",
            starts_on=date.today() - timedelta(days=300),
            ends_on=date.today() + timedelta(days=40),
            mileage_limit_km=Decimal(100000),
        )
        self.session.add(contract)
        self.session.flush()
        coverage = WarrantyCoverage(
            warranty_contract_id=contract.id,
            system="engine",
            component_code="engine",
            requires_preapproval=True,
        )
        self.session.add(coverage)
        self.session.flush()
        due = date.today() + timedelta(days=3)
        eligibility, note = warranty_review(
            self.session, self.unit_a, "engine", "engine", due
        )
        self.assertEqual(eligibility, "potential")
        self.assertIn("Verificar términos", note)
        self.assertIn("autorización previa", note)
        self.assertEqual(
            warranty_review(
                self.session, self.unit_a, "brake_pads", "brakes", due
            )[0],
            "not_covered",
        )
        self.unit_a.odometer_km = Decimal(110000)
        self.assertEqual(
            warranty_review(self.session, self.unit_a, "engine", "engine", due)[
                0
            ],
            "not_covered",
        )
        self.unit_a.odometer_km = Decimal(80000)
        self.assertEqual(
            warranty_review(
                self.session,
                self.unit_a,
                "engine",
                "engine",
                date.today() + timedelta(days=50),
            )[0],
            "not_covered",
        )

    def test_database_pagination_and_filtering(self):
        for i in range(55):
            self.session.add(
                Unit(fleet_id=self.unit_a.fleet_id, unit_number=f"PAGE-{i:03d}")
            )
        self.session.flush()
        first = load_inventory(
            self.uid,
            self.expires,
            "network",
            "PAGE-",
            str(self.unit_a.fleet_id),
            "unknown",
            "uncovered",
            1,
        )
        second = load_inventory(
            self.uid,
            self.expires,
            "network",
            "PAGE-",
            str(self.unit_a.fleet_id),
            "unknown",
            "uncovered",
            2,
        )
        self.assertEqual(first["total"], 55)
        self.assertEqual(len(first["rows"]), 25)
        self.assertEqual(len(second["rows"]), 25)
        self.assertFalse(
            {r["id"] for r in first["rows"]} & {r["id"] for r in second["rows"]}
        )
        self.assertEqual(
            load_inventory(
                self.uid,
                self.expires,
                "network",
                "PAGE-",
                str(self.unit_b.fleet_id),
                "",
                "",
                1,
            )["total"],
            0,
        )

    def test_seed_inference_idempotence(self):
        infer_seeded_units()
        first = self.session.scalar(
            select(func.count())
            .select_from(ComponentPrediction)
            .where(ComponentPrediction.model_version == VERSION)
        )
        infer_seeded_units()
        second = self.session.scalar(
            select(func.count())
            .select_from(ComponentPrediction)
            .where(ComponentPrediction.model_version == VERSION)
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
