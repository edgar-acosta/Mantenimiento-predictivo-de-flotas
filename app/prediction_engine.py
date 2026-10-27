import reflex as rx

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import lru_cache

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier
from sqlalchemy import select, text
from app.models import (
    ComponentPrediction,
    DTCCode,
    TelemetrySnapshot,
    Unit,
    UnitFault,
)

VERSION = "xgb-synthetic-degradation-v2"
SYSTEMS = ("engine", "brakes", "aftertreatment", "electrical", "tires")
COMPONENTS = ("engine", "brake_pads", "dpf", "charging_system", "tires")
FEATURES = (
    "mileage_km",
    "engine_hours",
    "dtc_engine",
    "dtc_brakes",
    "dtc_aftertreatment",
    "dtc_electrical",
    "dtc_tires",
    "brake_wear_percent",
    "coolant_c",
    "oil_c",
    "battery_v",
    "tire_kpa",
    "load_percent",
    "harsh_braking",
    "harsh_acceleration",
    "overspeed",
    "idle_percent",
)
ACTIONS = {
    "engine": (
        "Diagnosticar refrigeración, presión de aceite y fugas; confirmar antes de sustituir piezas",
        "Diagnose cooling, oil pressure and leaks; confirm before replacing parts",
        18500,
        12,
    ),
    "brakes": (
        "Medir pastillas y discos; revisar circuito neumático y sustituir material fuera de tolerancia",
        "Measure pads and discs; inspect pneumatic circuit and replace out-of-spec wear parts",
        7800,
        6,
    ),
    "aftertreatment": (
        "Diagnosticar DPF, sensores y contrapresión; regeneración supervisada según fabricante",
        "Diagnose DPF, sensors and backpressure; supervised regeneration per manufacturer",
        12500,
        8,
    ),
    "electrical": (
        "Probar batería bajo carga, alternador, masas y conexiones",
        "Load-test battery and inspect alternator, grounds and connections",
        6500,
        4,
    ),
    "tires": (
        "Inspeccionar presión en frío, dibujo y daños; corregir presión y alineación",
        "Inspect cold pressure, tread and damage; correct pressure and alignment",
        9600,
        4,
    ),
}


def synthetic_examples(
    seed: int = 24117, count: int = 5000
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    age = rng.beta(2, 2, count)
    load = rng.uniform(20, 100, count)
    harsh = rng.poisson(2 + load / 25, count)
    miles = np.clip(
        40000 + age * 600000 + rng.normal(0, 30000, count), 5000, 800000
    )
    hours = miles / rng.uniform(30, 65, count)
    degradation = np.clip(age * 0.5 + rng.beta(1.4, 2, (5, count)), 0, 1)
    faults = rng.poisson(np.maximum(0.05, (degradation.T - 0.3) * 5))
    wear = np.clip(
        degradation[1] * 95 + harsh * 1.2 + rng.normal(0, 6, count), 0, 100
    )
    coolant = 83 + degradation[0] * 28 + load * 0.03 + rng.normal(0, 3, count)
    oil = coolant + 9 + rng.normal(0, 3, count)
    voltage = 27.4 - degradation[3] * 5 + rng.normal(0, 0.35, count)
    tires = 850 - degradation[4] * 280 + rng.normal(0, 30, count)
    accel = rng.poisson(2 + load / 30, count)
    overspeed = rng.poisson(1 + harsh / 4, count)
    idle = np.clip(8 + degradation[2] * 50 + rng.normal(0, 5, count), 0, 80)
    x = np.column_stack(
        (
            miles,
            hours,
            faults,
            wear,
            coolant,
            oil,
            voltage,
            tires,
            load,
            harsh,
            accel,
            overspeed,
            idle,
        )
    ).astype(np.float32)
    stresses = np.column_stack(
        (
            (coolant - 90) / 18 + (oil - 100) / 25 + faults[:, 0] * 0.35,
            (wear - 45) / 28 + harsh / 20 + faults[:, 1] * 0.4,
            (idle - 25) / 22 + load / 150 + faults[:, 2] * 0.45,
            (25.8 - voltage) / 1.5 + faults[:, 3] * 0.4,
            (770 - tires) / 120 + overspeed / 15 + faults[:, 4] * 0.4,
        )
    )
    # A stochastic time-to-failure generator, not labels copied from demo risks.
    hazard = np.exp(
        np.clip(
            -6.1 + stresses * 0.85 + age[:, None] * 0.5 + load[:, None] / 250,
            -8,
            -2.8,
        )
    )
    failure_days = rng.exponential(1 / hazard)
    labels = np.where(failure_days <= 30, 0, np.where(failure_days <= 90, 1, 2))
    return x, labels


@lru_cache(maxsize=1)
def trained_models() -> tuple[
    tuple[CalibratedClassifierCV, ...],
    dict[str, dict[str, float]],
    str,
    datetime,
]:
    x, y = synthetic_examples()
    models, metrics = [], {}
    digest = hashlib.sha256(
        json.dumps(
            {"version": VERSION, "features": FEATURES, "seed": 24117}
        ).encode()
    )
    for i, system in enumerate(SYSTEMS):
        train_x, test_x, train_y, test_y = train_test_split(
            x, y[:, i], test_size=0.25, random_state=417, stratify=y[:, i]
        )
        base = XGBClassifier(
            n_estimators=65,
            max_depth=3,
            learning_rate=0.07,
            subsample=0.9,
            colsample_bytree=0.9,
            tree_method="hist",
            n_jobs=1,
            random_state=24117,
            objective="multi:softprob",
            eval_metric="mlogloss",
        )
        model = CalibratedClassifierCV(base, method="sigmoid", cv=3, n_jobs=1)
        model.fit(train_x, train_y)
        probabilities = model.predict_proba(test_x)
        p30, p90 = (
            probabilities[:, 0],
            probabilities[:, 0] + probabilities[:, 1],
        )
        metrics[system] = {
            "log_loss": float(log_loss(test_y, probabilities)),
            "brier30": float(brier_score_loss(test_y == 0, p30)),
            "brier90": float(brier_score_loss(test_y != 2, p90)),
            "auc30": float(roc_auc_score(test_y == 0, p30)),
            "auc90": float(roc_auc_score(test_y != 2, p90)),
            "test_rows": float(len(test_y)),
        }
        for calibrated in model.calibrated_classifiers_:
            digest.update(calibrated.estimator.get_booster().save_raw())
            for calibrator in calibrated.calibrators:
                digest.update(
                    np.asarray(
                        [calibrator.a_, calibrator.b_], dtype=np.float64
                    ).tobytes()
                )
        models.append(model)
    return (
        tuple(models),
        metrics,
        digest.hexdigest(),
        datetime.now(timezone.utc),
    )


def risk_level(p30: float, p90: float) -> str:
    if p30 >= 0.6:
        return "critical"
    if p30 >= 0.35 or p90 >= 0.65:
        return "high"
    if p30 >= 0.15 or p90 >= 0.35:
        return "medium"
    return "low"


def features_for(t: TelemetrySnapshot, counts: dict[str, int]) -> np.ndarray:
    defaults = {
        "brake_wear_percent": 35,
        "coolant_temperature_c": 90,
        "oil_temperature_c": 100,
        "battery_voltage": 26.5,
        "tire_pressure_kpa": 800,
        "load_percent": 55,
    }
    values = [float(t.odometer_km), float(t.engine_hours)]
    values.extend(counts.get(system, 0) for system in SYSTEMS)
    values.extend(
        float(getattr(t, key) if getattr(t, key) is not None else value)
        for key, value in defaults.items()
    )
    values.extend(
        (
            t.harsh_braking_events,
            t.harsh_acceleration_events,
            t.overspeed_events,
            float(t.idle_percent),
        )
    )
    return np.array([values], dtype=np.float32)


def augment_synthetic_inputs() -> None:
    with rx.session() as session:
        session.execute(text("SELECT pg_advisory_xact_lock(70421903)"))
        codes = {}
        descriptions = (
            (
                "SYN-110-0",
                110,
                0,
                "Temperatura refrigerante elevada",
                "High coolant temperature",
            ),
            (
                "SYN-291-1",
                291,
                1,
                "Desgaste de frenos fuera de umbral",
                "Brake wear beyond threshold",
            ),
            (
                "SYN-3251-0",
                3251,
                0,
                "Presión diferencial DPF elevada",
                "High DPF differential pressure",
            ),
            (
                "SYN-168-1",
                168,
                1,
                "Tensión de alimentación baja",
                "Low supply voltage",
            ),
            (
                "SYN-241-1",
                241,
                1,
                "Presión neumático baja",
                "Low tire pressure",
            ),
        )
        for system, component, spec in zip(SYSTEMS, COMPONENTS, descriptions):
            code, spn, fmi, es, en = spec
            dtc = session.scalar(
                select(DTCCode).where(
                    DTCCode.code == code, DTCCode.manufacturer == "synthetic"
                )
            )
            if not dtc:
                dtc = DTCCode(
                    code=code,
                    manufacturer="synthetic",
                    standard="J1939",
                    spn=spn,
                    fmi=fmi,
                    system=system,
                    component_code=component,
                    description_es=f"SYNTHETIC · {es}",
                    description_en=f"SYNTHETIC · {en}",
                    severity="warning",
                )
                session.add(dtc)
                session.flush()
            codes[system] = dtc.id
        units = session.scalars(
            select(Unit).where(Unit.notes.like("SYNTHETIC%"))
        ).all()
        for unit in units:
            snapshots = session.scalars(
                select(TelemetrySnapshot)
                .where(
                    TelemetrySnapshot.unit_id == unit.id,
                    TelemetrySnapshot.is_synthetic.is_(True),
                    TelemetrySnapshot.generator_version.in_(
                        ["demo-v1", "degradation-v2"]
                    ),
                )
                .order_by(TelemetrySnapshot.observed_at)
            ).all()
            if not snapshots:
                continue
            severity = (int(unit.unit_number or unit.id) % 8) / 7
            for i, t in enumerate(snapshots):
                if t.generator_version == "degradation-v2":
                    continue
                drift = i / max(1, len(snapshots) - 1)
                t.coolant_temperature_c = Decimal(
                    str(round(87 + severity * 24 + drift * 3, 2))
                )
                t.oil_temperature_c = t.coolant_temperature_c + Decimal(10)
                t.brake_wear_percent = Decimal(
                    str(round(20 + severity * 65 + drift * 9, 2))
                )
                t.battery_voltage = Decimal(
                    str(round(27.1 - severity * 4.8 - drift * 0.3, 2))
                )
                t.tire_pressure_kpa = Decimal(
                    str(round(860 - severity * 275 - drift * 20, 2))
                )
                t.load_percent = Decimal(str(round(35 + severity * 55, 2)))
                t.idle_percent = Decimal(str(round(12 + severity * 48, 2)))
                t.harsh_braking_events = int(2 + severity * 10)
                t.harsh_acceleration_events = int(1 + severity * 8)
                t.overspeed_events = int(severity * 7)
                t.generator_version = "degradation-v2"
            latest = snapshots[-1]
            triggers = {
                "engine": float(latest.coolant_temperature_c or 0) > 103,
                "brakes": float(latest.brake_wear_percent or 0) > 70,
                "aftertreatment": float(latest.idle_percent) > 45,
                "electrical": float(latest.battery_voltage or 27) < 24,
                "tires": float(latest.tire_pressure_kpa or 800) < 680,
            }
            for system in SYSTEMS:
                for historical in (True, False):
                    source = (
                        "synthetic-degradation-history-v2"
                        if historical
                        else "synthetic-degradation-active-v2"
                    )
                    if not historical and not triggers[system]:
                        continue
                    if session.scalar(
                        select(UnitFault.id).where(
                            UnitFault.unit_id == unit.id,
                            UnitFault.dtc_code_id == codes[system],
                            UnitFault.source == source,
                        )
                    ):
                        continue
                    t = (
                        snapshots[2]
                        if historical and len(snapshots) > 2
                        else latest
                    )
                    session.add(
                        UnitFault(
                            unit_id=unit.id,
                            dtc_code_id=codes[system],
                            telemetry_snapshot_id=t.id,
                            first_seen_at=t.observed_at - timedelta(hours=8),
                            last_seen_at=t.observed_at,
                            cleared_at=t.observed_at + timedelta(hours=3)
                            if historical
                            else None,
                            status="cleared" if historical else "active",
                            occurrence_count=2 if historical else 3,
                            odometer_km=t.odometer_km,
                            engine_hours=t.engine_hours,
                            source=source,
                            notes="Synthetic simulated diagnostic occurrence; not measured on a real vehicle.",
                        )
                    )
        session.commit()


def infer_seeded_units() -> None:
    models, metrics, artifact, trained_at = trained_models()
    with rx.session() as session:
        session.execute(text("SELECT pg_advisory_xact_lock(70421904)"))
        units = session.scalars(
            select(Unit).where(Unit.notes.like("SYNTHETIC%"))
        ).all()
        for unit in units:
            t = session.scalar(
                select(TelemetrySnapshot)
                .where(TelemetrySnapshot.unit_id == unit.id)
                .order_by(
                    TelemetrySnapshot.observed_at.desc(),
                    TelemetrySnapshot.id.desc(),
                )
                .limit(1)
            )
            if not t:
                continue
            counts = {system: 0 for system in SYSTEMS}
            for fault, dtc in session.execute(
                select(UnitFault, DTCCode)
                .join(DTCCode, UnitFault.dtc_code_id == DTCCode.id)
                .where(
                    UnitFault.unit_id == unit.id,
                    UnitFault.status.in_(["active", "intermittent"]),
                )
            ):
                counts[dtc.system] = (
                    counts.get(dtc.system, 0) + fault.occurrence_count
                )
            x = features_for(t, counts)
            for system, component, model in zip(SYSTEMS, COMPONENTS, models):
                if session.scalar(
                    select(ComponentPrediction.id).where(
                        ComponentPrediction.unit_id == unit.id,
                        ComponentPrediction.telemetry_snapshot_id == t.id,
                        ComponentPrediction.component_code == component,
                        ComponentPrediction.model_version == VERSION,
                        ComponentPrediction.model_artifact_sha256 == artifact,
                        ComponentPrediction.valid_until
                        >= datetime.now(timezone.utc),
                    )
                ):
                    continue
                p = model.predict_proba(x)[0]
                p30, p90 = float(p[0]), float(p[0] + p[1])
                level = risk_level(p30, p90)
                days = {"critical": 1, "high": 3, "medium": 14, "low": 30}[
                    level
                ]
                es, en, cost, hours = ACTIONS[system]
                now = datetime.now(timezone.utc)
                safety_es = (
                    "Retirar de ruta hasta revisión profesional. "
                    if level == "critical"
                    else ""
                )
                explanation = {
                    "synthetic_only": True,
                    "features": dict(zip(FEATURES, x[0].tolist())),
                    "holdout": metrics[system],
                    "training_rows": 3750,
                    "calibration": "sigmoid, 3-fold training-only CV",
                    "failure_bins": "<=30 days, 31-90 days, >90 days",
                    "limitations": "Simulated exponential degradation hazard. Not validated on real fleet failures; missing sensors imputed to training nominal values. No safety guarantee.",
                }
                session.add(
                    ComponentPrediction(
                        unit_id=unit.id,
                        telemetry_snapshot_id=t.id,
                        system=system,
                        component_code=component,
                        predicted_at=now,
                        valid_until=now + timedelta(days=14),
                        failure_probability_30d=Decimal(str(round(p30, 6))),
                        failure_probability_90d=Decimal(str(round(p90, 6))),
                        risk_level=level,
                        odometer_km=t.odometer_km,
                        engine_hours=t.engine_hours,
                        model_name="CPU XGBoost · calibrated synthetic failure classifier",
                        model_version=VERSION,
                        model_artifact_sha256=artifact,
                        training_dataset_version="stochastic-degradation-24117-v2-5000",
                        training_data_is_synthetic=True,
                        trained_at=trained_at,
                        feature_schema_version="fleet-degradation-17-v2",
                        inference_run_id=f"{VERSION}:{t.id}:{artifact[:12]}",
                        explanation_es=json.dumps(
                            explanation, ensure_ascii=False
                        ),
                        explanation_en=json.dumps(explanation),
                        recommended_action_es=f"{safety_es}{es}",
                        recommended_action_en=f"{'Remove from route pending professional inspection. ' if level == 'critical' else ''}{en}",
                        recommended_by=now.date() + timedelta(days=days),
                        estimated_repair_cost=Decimal(cost),
                        estimated_downtime_hours=Decimal(hours),
                        currency="MXN",
                    )
                )
        session.commit()


async def prediction_startup() -> None:
    try:
        await asyncio.to_thread(trained_models)
        await asyncio.to_thread(augment_synthetic_inputs)
        await asyncio.to_thread(infer_seeded_units)
    except Exception as e:
        logging.exception(f"Error: {e}")
        raise
