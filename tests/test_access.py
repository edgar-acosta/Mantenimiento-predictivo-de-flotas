import reflex as rx

import asyncio
import time
import unittest
from types import MethodType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from app.models import AppUser
from app.security import (
    AccessDenied,
    authorize,
    scope_id,
    password_hash,
    password_matches,
    validate_account,
    authenticate,
    provision,
)
from app.demo import seed_demo
from app.states.access_state import AccessState, _load_summary_or_none


class AccessTests(unittest.TestCase):
    def test_scrypt_salt_and_verification(self):
        first = password_hash("A long sample passphrase 19")
        second = password_hash("A long sample passphrase 19")
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("scrypt$16384$8$1$"))
        self.assertTrue(password_matches("A long sample passphrase 19", first))
        self.assertFalse(password_matches("A different passphrase", first))
        self.assertFalse(password_matches("test", "invalid"))
        self.assertFalse(
            password_matches("test", first.replace("16384", "999999999"))
        )

    def test_validation(self):
        self.assertEqual(
            validate_account(
                "person@example.test", "Long passphrase 123", "Persona"
            ),
            "",
        )
        self.assertNotEqual(
            validate_account("invalid", "Long passphrase 123", "Persona"), ""
        )
        self.assertNotEqual(
            validate_account("person@example.test", "short", "Persona"), ""
        )
        self.assertNotEqual(
            validate_account("person@example.test", "x" * 129, "Persona"), ""
        )
        self.assertNotEqual(
            validate_account("person@example.test", "Long passphrase 123", ""),
            "",
        )

    def test_client_cannot_select_other_organization(self):
        session = MagicMock()
        user = AppUser(id=11, client_id=21, role="client", is_active=True)
        self.assertEqual(scope_id(session, user, "999"), 21)
        self.assertEqual(scope_id(session, user, "network"), 21)
        session.scalar.assert_not_called()

    def test_admin_required_even_with_forged_target(self):
        session = MagicMock()
        session.scalar.return_value = AppUser(
            id=11, client_id=21, role="client", is_active=True
        )
        with self.assertRaises(AccessDenied):
            authorize(session, 11, time.time() + 3600, admin=True)
        with patch.object(rx, "session") as factory:
            factory.return_value.__enter__.return_value = session
            with self.assertRaises(AccessDenied):
                provision(
                    11,
                    time.time() + 3600,
                    "test@example.test",
                    "Long passphrase 123",
                    "Test",
                    "999",
                )
            session.add.assert_not_called()

    def test_expired_session_never_queries_business_data(self):
        session = MagicMock()
        with self.assertRaises(AccessDenied):
            authorize(session, 11, time.time() - 1)
        session.scalar.assert_not_called()

    def test_signed_out_load_guard_clears_state_without_database_calls(self):
        message = "Tu sesión ha finalizado. Inicia sesión de nuevo."
        for uid, expires, previous_error, expected_error in (
            (0, 0.0, "", ""),
            (11, 99.0, "", message),
            (11, 100.0, "", message),
            (0, 0.0, message, message),
        ):
            with self.subTest(uid=uid, expires=expires, error=previous_error):
                views = [MagicMock(), MagicMock(), MagicMock()]
                state = SimpleNamespace(
                    _user_id=uid,
                    _expires=expires,
                    _epoch=4,
                    authenticated=True,
                    loading=True,
                    error=previous_error,
                    actions=[{"unit": "protected"}],
                    get_state=AsyncMock(side_effect=views),
                )
                state._clear_session = MethodType(
                    AccessState._clear_session, state
                )
                state._clear_protected_session = MethodType(
                    AccessState._clear_protected_session, state
                )
                with (
                    patch(
                        "app.states.access_state.time.time", return_value=100.0
                    ),
                    patch("app.states.access_state.load_summary") as summary,
                    patch.object(rx, "session") as database,
                    patch("app.states.access_state.logging.exception") as log,
                ):
                    self.assertTrue(
                        asyncio.run(AccessState._guard_session(state))
                    )
                summary.assert_not_called()
                database.assert_not_called()
                log.assert_not_called()
                for view in views:
                    view._clear_view.assert_called_once_with()
                self.assertEqual(state._user_id, 0)
                self.assertEqual(state._expires, 0.0)
                self.assertEqual(state._epoch, 5)
                self.assertFalse(state.authenticated)
                self.assertFalse(state.loading)
                self.assertEqual(state.actions, [])
                self.assertEqual(state.error, expected_error)

    def test_load_guard_leaves_valid_session_unchanged(self):
        state = SimpleNamespace(
            _user_id=11,
            _expires=101.0,
            error="existing message",
            _clear_protected_session=AsyncMock(),
        )
        with patch("app.states.access_state.time.time", return_value=100.0):
            self.assertFalse(asyncio.run(AccessState._guard_session(state)))
        state._clear_protected_session.assert_not_awaited()
        self.assertEqual(state._user_id, 11)
        self.assertEqual(state.error, "existing message")

    def test_summary_helper_returns_authorized_result_unchanged(self):
        summary = {"name": "Authorized user"}
        with patch(
            "app.states.access_state.load_summary", return_value=summary
        ) as loader:
            self.assertIs(_load_summary_or_none(11, 101.0, "network"), summary)
        loader.assert_called_once_with(11, 101.0, "network")

    def test_summary_helper_suppresses_only_known_access_denial(self):
        with (
            patch(
                "app.states.access_state.load_summary",
                side_effect=AccessDenied("Session no longer valid"),
            ),
            patch("app.states.access_state.logging.exception") as log,
        ):
            self.assertIsNone(_load_summary_or_none(11, 101.0, "network"))
        log.assert_not_called()

    def test_summary_helper_propagates_unexpected_failure(self):
        failure = RuntimeError("Summary unavailable")
        with patch("app.states.access_state.load_summary", side_effect=failure):
            with self.assertRaises(RuntimeError) as caught:
                _load_summary_or_none(11, 101.0, "network")
        self.assertIs(caught.exception, failure)

    def test_inactive_account_rejected(self):
        session = MagicMock()
        session.scalar.return_value = None
        with self.assertRaises(AccessDenied):
            authorize(session, 11, time.time() + 3600)

    def test_bootstrap_claim_is_locked_and_cannot_be_repeated(self):
        session = MagicMock()
        session.scalar.return_value = 11
        with patch.object(rx, "session") as factory:
            factory.return_value.__enter__.return_value = session
            uid, error = authenticate(
                "admin@example.test", "Long passphrase 123", "Admin", True
            )
        self.assertEqual(uid, 0)
        self.assertTrue(error)
        self.assertIn(
            "pg_advisory_xact_lock", str(session.execute.call_args.args[0])
        )
        session.add.assert_not_called()

    def test_bootstrap_writes_scrypt_algorithm_and_no_client(self):
        session = MagicMock()
        session.scalar.return_value = None
        session.flush.side_effect = lambda: setattr(
            session.add.call_args.args[0], "id", 7
        )
        with patch.object(rx, "session") as factory:
            factory.return_value.__enter__.return_value = session
            uid, error = authenticate(
                "admin@example.test", "Long passphrase 123", "Admin", True
            )
        user = session.add.call_args.args[0]
        self.assertEqual((uid, error), (7, ""))
        self.assertEqual(user.password_algorithm, "scrypt")
        self.assertEqual(user.role, "admin")
        self.assertIsNone(user.client_id)
        self.assertTrue(
            password_matches("Long passphrase 123", user.password_hash)
        )
        session.commit.assert_called_once()

    def test_seed_skips_existing_clients_and_never_seeds_accounts(self):
        session = MagicMock()
        session.scalar.return_value = 21
        with patch.object(rx, "session") as factory:
            factory.return_value.__enter__.return_value = session
            seed_demo()
        self.assertEqual(session.scalar.call_count, 5)
        session.add.assert_not_called()
        session.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
