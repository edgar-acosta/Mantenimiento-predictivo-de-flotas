import reflex as rx

import hashlib
import hmac
import secrets
import re
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.models import AppUser, ClientOrganization


class AccessDenied(Exception):
    pass


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32
    )
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def password_matches(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$")
        if (algorithm, n, r, p) != ("scrypt", "16384", "8", "1"):
            return False
        salt_bytes = bytes.fromhex(salt)
        expected_bytes = bytes.fromhex(expected)
        if len(salt_bytes) != 16 or len(expected_bytes) != 32:
            return False
        actual = hashlib.scrypt(
            password.encode(), salt=salt_bytes, n=16384, r=8, p=1, dklen=32
        )
        return hmac.compare_digest(actual, expected_bytes)
    except (ValueError, TypeError):
        return False


def validate_account(email: str, password: str, name: str = "") -> str:
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return "Introduce un correo electrónico válido."
    if not 12 <= len(password) <= 128:
        return "La contraseña debe tener entre 12 y 128 caracteres."
    if not name.strip() or len(name.strip()) > 160:
        return "Introduce un nombre de hasta 160 caracteres."
    return ""


def authorize(
    session: Session, user_id: int, expires: float, admin: bool = False
) -> AppUser:
    if not user_id or datetime.now(timezone.utc).timestamp() >= expires:
        raise AccessDenied("Tu sesión ha finalizado. Inicia sesión de nuevo.")
    user = session.scalar(
        select(AppUser).where(
            AppUser.id == user_id, AppUser.is_active.is_(True)
        )
    )
    if not user or (admin and user.role != "admin"):
        raise AccessDenied("No tienes permiso para realizar esta operación.")
    if user.role == "client":
        client = session.scalar(
            select(ClientOrganization).where(
                ClientOrganization.id == user.client_id,
                ClientOrganization.status == "active",
            )
        )
        if not client:
            raise AccessDenied(
                "La organización no está activa. Contacta al administrador."
            )
    return user


def scope_id(session: Session, user: AppUser, context: str) -> int:
    if user.role == "client":
        return int(user.client_id)
    if context == "network":
        return 0
    try:
        client_id = int(context)
    except ValueError:
        raise AccessDenied("Selecciona un cliente válido.") from None
    if not session.scalar(
        select(ClientOrganization.id).where(
            ClientOrganization.id == client_id,
            ClientOrganization.status == "active",
        )
    ):
        raise AccessDenied("El cliente no está disponible.")
    return client_id


def bootstrap_available() -> bool:
    with rx.session() as session:
        return session.scalar(select(AppUser.id).limit(1)) is None


def authenticate(
    email: str, password: str, name: str, bootstrap: bool
) -> tuple[int, str]:
    now = datetime.now(timezone.utc)
    with rx.session() as session:
        if bootstrap:
            error = validate_account(email, password, name)
            if error:
                return 0, error
            encoded = password_hash(password)
            session.execute(text("SELECT pg_advisory_xact_lock(70421902)"))
            if session.scalar(select(AppUser.id).limit(1)) is not None:
                return (
                    0,
                    "La configuración inicial ya fue completada. Inicia sesión.",
                )
            user = AppUser(
                email=email,
                display_name=name.strip(),
                password_hash=encoded,
                password_algorithm="scrypt",
                password_changed_at=now,
                role="admin",
                client_id=None,
                last_login_at=now,
            )
            session.add(user)
            session.flush()
            user_id = user.id
            session.commit()
            return user_id, ""
        if not email or not password or len(email) > 254 or len(password) > 128:
            return 0, "Introduce tu correo y contraseña válidos."
        user = session.scalar(
            select(AppUser).where(AppUser.email == email).with_for_update()
        )
        if not user:
            password_hash(password)
            return 0, "Correo o contraseña incorrectos."
        if user.locked_until and user.locked_until > now:
            return (
                0,
                "Demasiados intentos. Espera 15 minutos antes de volver a intentar.",
            )
        valid = password_matches(password, user.password_hash or "")
        if (
            not valid
            or user.password_algorithm != "scrypt"
            or not user.is_active
        ):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = now + timedelta(minutes=15)
                user.failed_login_attempts = 0
            session.commit()
            return 0, "Correo o contraseña incorrectos."
        if user.role == "client" and not session.scalar(
            select(ClientOrganization.id).where(
                ClientOrganization.id == user.client_id,
                ClientOrganization.status == "active",
            )
        ):
            return (
                0,
                "La organización no está activa. Contacta al administrador.",
            )
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = now
        user_id = user.id
        session.commit()
        return user_id, ""


def provision(
    user_id: int,
    expires: float,
    email: str,
    password: str,
    name: str,
    client: str,
) -> str:
    with rx.session() as session:
        authorize(session, user_id, expires, admin=True)
        error = validate_account(email, password, name)
        if error:
            return error
        if client == "network":
            return "Selecciona la organización del nuevo usuario."
        owner = scope_id(
            session, authorize(session, user_id, expires, admin=True), client
        )
        encoded = password_hash(password)
        session.execute(text("SELECT pg_advisory_xact_lock(70421902)"))
        if session.scalar(select(AppUser.id).where(AppUser.email == email)):
            return "Ya existe una cuenta con ese correo."
        session.add(
            AppUser(
                email=email,
                password_hash=encoded,
                password_algorithm="scrypt",
                password_changed_at=datetime.now(timezone.utc),
                display_name=name.strip(),
                role="client",
                client_id=owner,
            )
        )
        session.commit()
        return ""


def toggle_client_user(
    user_id: int, expires: float, target_id: int, context: str
) -> None:
    with rx.session() as session:
        user = authorize(session, user_id, expires, admin=True)
        client_id = scope_id(session, user, context)
        query = (
            select(AppUser)
            .where(AppUser.id == target_id, AppUser.role == "client")
            .with_for_update()
        )
        if client_id:
            query = query.where(AppUser.client_id == client_id)
        target = session.scalar(query)
        if not target:
            raise AccessDenied("La cuenta no está disponible en este contexto.")
        target.is_active = not target.is_active
        session.commit()
