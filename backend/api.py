from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


ROOT = Path(__file__).resolve().parent.parent
CLINIC_TZ = ZoneInfo("America/Mexico_City")


def database_url() -> str:
    configured_url = os.environ.get("DATABASE_URL")
    if configured_url:
        if configured_url.startswith("postgres://"):
            return configured_url.replace("postgres://", "postgresql+psycopg://", 1)
        if configured_url.startswith("postgresql://"):
            return configured_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return configured_url
    if os.environ.get("VERCEL"):
        return "sqlite:////tmp/clinica-turnos.db"
    return f"sqlite:///{(ROOT / 'clinica-turnos.db').as_posix()}"


metadata = MetaData()
tickets = Table(
    "tickets",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("code", String(12), nullable=False),
    Column("service", String(40), nullable=False),
    Column("status", String(16), nullable=False, index=True),
    Column("station_number", Integer, nullable=True),
    Column("sequence_number", Integer, nullable=False),
    Column("day_key", String(10), nullable=False, index=True),
    Column("created_at", DateTime, nullable=False),
    Column("called_at", DateTime, nullable=True),
    Column("finished_at", DateTime, nullable=True),
)
stations = Table(
    "stations",
    metadata,
    Column("number", Integer, primary_key=True),
    Column("status", String(16), nullable=False),
    Column("current_ticket_id", ForeignKey("tickets.id"), nullable=True),
)


def make_engine(url: str) -> Engine:
    options: dict[str, object] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **options)


engine = make_engine(database_url())
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
state_lock = threading.RLock()
metadata.create_all(engine)


with engine.begin() as connection:
    for number in range(1, 5):
        exists = connection.execute(
            select(stations.c.number).where(stations.c.number == number)
        ).first()
        if not exists:
            connection.execute(
                stations.insert().values(
                    number=number, status="available", current_ticket_id=None
                )
            )


def now_local() -> datetime:
    return datetime.now(CLINIC_TZ).replace(tzinfo=None, microsecond=0)


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def ticket_json(row: object | None) -> dict[str, object] | None:
    if row is None:
        return None
    item = dict(row._mapping)
    return {
        "id": item["id"],
        "code": item["code"],
        "service": item["service"],
        "status": item["status"],
        "station_number": item["station_number"],
        "created_at": iso(item["created_at"]),
        "called_at": iso(item["called_at"]),
        "finished_at": iso(item["finished_at"]),
    }


def get_station_ticket(session: Session, ticket_id: int | None) -> dict[str, object] | None:
    if ticket_id is None:
        return None
    row = session.execute(
        select(tickets).where(tickets.c.id == ticket_id)
    ).first()
    return ticket_json(row)


def station_json(session: Session, row: object) -> dict[str, object]:
    item = dict(row._mapping)
    return {
        "number": item["number"],
        "status": item["status"],
        "current_ticket": get_station_ticket(session, item["current_ticket_id"]),
    }


def next_waiting_ticket(session: Session) -> object | None:
    return session.execute(
        select(tickets)
        .where(tickets.c.status == "waiting")
        .order_by(tickets.c.created_at, tickets.c.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).first()


app = Flask(__name__)
app.json.ensure_ascii = False


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "clinica-turnos"})


@app.get("/api/status")
def status():
    today = now_local().date().isoformat()
    with SessionLocal() as session:
        station_rows = session.execute(
            select(stations).order_by(stations.c.number)
        ).all()
        waiting_rows = session.execute(
            select(tickets)
            .where(tickets.c.status == "waiting")
            .order_by(tickets.c.created_at, tickets.c.id)
        ).all()
        called_rows = session.execute(
            select(tickets)
            .where(tickets.c.day_key == today, tickets.c.called_at.is_not(None))
            .order_by(tickets.c.called_at.desc(), tickets.c.id.desc())
            .limit(4)
        ).all()
        completed = session.scalar(
            select(func.count())
            .select_from(tickets)
            .where(
                tickets.c.status == "completed",
                tickets.c.day_key == today,
            )
        ) or 0
        created = session.scalar(
            select(func.count())
            .select_from(tickets)
            .where(tickets.c.day_key == today)
        ) or 0
        result_stations = [station_json(session, row) for row in station_rows]
        waiting = [ticket_json(row) for row in waiting_rows]
        recent_calls = [ticket_json(row) for row in called_rows]

    return jsonify(
        {
            "stations": result_stations,
            "waiting": waiting,
            "recent_calls": recent_calls,
            "latest_call": recent_calls[0] if recent_calls else None,
            "stats": {
                "waiting": len(waiting),
                "completed_today": completed,
                "created_today": created,
                "available_stations": sum(
                    1 for item in result_stations if item["status"] == "available"
                ),
            },
            "server_time": now_local().isoformat(),
        }
    )


@app.post("/api/tickets")
def create_ticket():
    body = request.get_json(silent=True) or {}
    service = str(body.get("service", "Consulta general")).strip()
    allowed_services = {
        "Consulta general",
        "Laboratorio",
        "Farmacia",
        "Imagenología",
    }
    if service not in allowed_services:
        return jsonify({"error": "Selecciona un servicio válido."}), 400

    with state_lock, SessionLocal.begin() as session:
        current_time = now_local()
        day_key = current_time.date().isoformat()
        sequence = (
            session.scalar(
                select(func.max(tickets.c.sequence_number)).where(
                    tickets.c.day_key == day_key
                )
            )
            or 0
        ) + 1
        code = f"A{sequence:02d}"
        result = session.execute(
            tickets.insert().values(
                code=code,
                service=service,
                status="waiting",
                station_number=None,
                sequence_number=sequence,
                day_key=day_key,
                created_at=current_time,
            )
        )
        ticket_id = result.inserted_primary_key[0]
        created = session.execute(
            select(tickets).where(tickets.c.id == ticket_id)
        ).first()
        payload = ticket_json(created)

    return jsonify({"ticket": payload}), 201


@app.post("/api/stations/<int:number>/call")
def call_next(number: int):
    with state_lock, SessionLocal.begin() as session:
        station = session.execute(
            select(stations)
            .where(stations.c.number == number)
            .with_for_update()
        ).first()
        if station is None:
            return jsonify({"error": "La ventanilla no existe."}), 404
        station_data = dict(station._mapping)
        if station_data["status"] == "occupied":
            return jsonify({"error": "Libera la ventanilla antes de llamar otro turno."}), 409
        if station_data["current_ticket_id"] is not None:
            current = session.execute(
                select(tickets).where(
                    tickets.c.id == station_data["current_ticket_id"]
                )
            ).first()
            if current and current._mapping["status"] in ("called", "attending"):
                return jsonify({"error": "Ya hay un turno asignado a esta ventanilla."}), 409

        ticket = next_waiting_ticket(session)
        if ticket is None:
            return jsonify({"error": "No hay turnos en espera."}), 409
        ticket_data = dict(ticket._mapping)
        called_at = now_local()
        session.execute(
            tickets.update()
            .where(tickets.c.id == ticket_data["id"])
            .values(
                status="called",
                station_number=number,
                called_at=called_at,
            )
        )
        session.execute(
            stations.update()
            .where(stations.c.number == number)
            .values(current_ticket_id=ticket_data["id"], status="available")
        )
        assigned = session.execute(
            select(tickets).where(tickets.c.id == ticket_data["id"])
        ).first()
        payload = ticket_json(assigned)

    return jsonify({"ticket": payload, "station_number": number})


@app.patch("/api/stations/<int:number>/status")
def update_station(number: int):
    body = request.get_json(silent=True) or {}
    requested_status = body.get("status")
    if requested_status not in ("occupied", "available"):
        return jsonify({"error": "El estado debe ser ocupado o disponible."}), 400

    with state_lock, SessionLocal.begin() as session:
        station = session.execute(
            select(stations)
            .where(stations.c.number == number)
            .with_for_update()
        ).first()
        if station is None:
            return jsonify({"error": "La ventanilla no existe."}), 404
        station_data = dict(station._mapping)
        current_id = station_data["current_ticket_id"]

        if requested_status == "occupied":
            if station_data["status"] == "occupied":
                return jsonify({"error": "La ventanilla ya está ocupada."}), 409
            if current_id is None:
                return jsonify({"error": "Primero llama un turno."}), 409
            current = session.execute(
                select(tickets).where(tickets.c.id == current_id)
            ).first()
            if current is None or current._mapping["status"] != "called":
                return jsonify({"error": "Llama un turno antes de iniciar atención."}), 409
            session.execute(
                tickets.update()
                .where(tickets.c.id == current_id)
                .values(status="attending")
            )
            session.execute(
                stations.update()
                .where(stations.c.number == number)
                .values(status="occupied")
            )
            result = {"status": "occupied", "next_ticket": None}
        else:
            next_ticket = None
            if station_data["status"] == "occupied" and current_id is not None:
                session.execute(
                    tickets.update()
                    .where(tickets.c.id == current_id)
                    .values(status="completed", finished_at=now_local())
                )
                session.execute(
                    stations.update()
                    .where(stations.c.number == number)
                    .values(status="available", current_ticket_id=None)
                )
                waiting = next_waiting_ticket(session)
                if waiting is not None:
                    waiting_data = dict(waiting._mapping)
                    called_at = now_local()
                    session.execute(
                        tickets.update()
                        .where(tickets.c.id == waiting_data["id"])
                        .values(
                            status="called",
                            station_number=number,
                            called_at=called_at,
                        )
                    )
                    session.execute(
                        stations.update()
                        .where(stations.c.number == number)
                        .values(current_ticket_id=waiting_data["id"])
                    )
                    next_ticket = ticket_json(
                        session.execute(
                            select(tickets).where(
                                tickets.c.id == waiting_data["id"]
                            )
                        ).first()
                    )
            else:
                session.execute(
                    stations.update()
                    .where(stations.c.number == number)
                    .values(status="available")
                )
            result = {"status": "available", "next_ticket": next_ticket}

    return jsonify(result)


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "No encontramos esa ruta."}), 404


@app.errorhandler(500)
def internal_error(_error):
    return jsonify({"error": "Ocurrió un error interno. Intenta de nuevo."}), 500
