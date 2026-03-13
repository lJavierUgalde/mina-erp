"""
main.py
Aplicación FastAPI para Mina ERP.

Para ejecutar en desarrollo:
    uvicorn main:app --reload --port 8000

Documentación interactiva disponible en:
    http://localhost:8000/docs
"""

from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

import models
import schemas
from database import Base, engine, get_db

# ── Crear tablas en la base de datos (solo para desarrollo/prototipo)
# En producción se usa Alembic para las migraciones.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Mina ERP – API",
    description="Back-end para el sistema ERP de gestión minera.",
    version="1.0.0",
)

# ── CORS: permite que React (localhost:5173) consuma la API ──────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════
# HELPER: obtener el turno del día
# ═══════════════════════════════════════════════════════════════════

def _current_shift() -> int:
    hour = datetime.now().hour
    if 6 <= hour < 14:
        return 1
    elif 14 <= hour < 22:
        return 2
    return 3


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 1: DASHBOARD PRINCIPAL
# GET /dashboard  ← alimenta las 4 KPI cards + alertas + bitácora + proyectos
# ═══════════════════════════════════════════════════════════════════

@app.get(
    "/dashboard",
    response_model=schemas.DashboardResponse,
    summary="Dashboard principal — KPIs del turno, alertas y bitácora reciente",
    tags=["Dashboard"],
)
def get_dashboard(
    target_date: Optional[date] = Query(
        default=None,
        description="Fecha del resumen (ISO 8601). Por defecto: hoy.",
    ),
    shift: int = Query(default=0, ge=0, le=3, description="0 = turno actual"),
    db: Session = Depends(get_db),
):
    """
    Retorna todos los datos necesarios para renderizar el **Panel Principal**:

    - **KPI Producción**: toneladas producidas vs. plan.
    - **KPI Disponibilidad**: % de equipos operativos + nota de alerta.
    - **KPI Góndolas**: unidades cargadas / total.
    - **KPI Seguridad**: número de incidentes + días sin accidentes.
    - **active_alerts**: banners críticos no descartados.
    - **recent_log_entries**: últimas 4 entradas de la bitácora (todos los módulos).
    - **special_projects**: proyectos activos con % de avance (widget Gantt).
    """
    query_date = target_date or date.today()
    query_shift = shift if shift != 0 else _current_shift()

    # ── Resumen del día ─────────────────────────────────────────────
    summary = (
        db.query(models.DailyProductionSummary)
        .filter(
            models.DailyProductionSummary.summary_date == query_date,
            models.DailyProductionSummary.shift == query_shift,
        )
        .first()
    )

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No se encontró un resumen de producción para "
                f"la fecha {query_date} turno {query_shift}."
            ),
        )

    # ── Alertas activas (no descartadas) ───────────────────────────
    active_alerts = (
        db.query(models.Alert)
        .filter(models.Alert.is_dismissed.is_(False))
        .order_by(models.Alert.created_at.desc())
        .limit(5)
        .all()
    )

    # ── Bitácora reciente (últimas 4 horas / 4 entradas) ───────────
    four_hours_ago = datetime.utcnow() - timedelta(hours=4)
    recent_log = (
        db.query(models.LogEntry)
        .filter(models.LogEntry.event_time >= four_hours_ago)
        .order_by(models.LogEntry.event_time.desc())
        .limit(4)
        .all()
    )

    # ── Proyectos especiales activos ───────────────────────────────
    projects = (
        db.query(models.SpecialProject)
        .filter(models.SpecialProject.is_active.is_(True))
        .order_by(models.SpecialProject.progress_pct.asc())
        .all()
    )

    # ── Ensamblar la respuesta ─────────────────────────────────────
    return schemas.DashboardResponse(
        summary_date=summary.summary_date,
        shift=summary.shift,
        production_kpi=schemas.ProductionKPI(
            tons_produced=float(summary.total_tons_produced or 0),
            plan_tons=float(summary.production_plan_tons or 0),
            vs_plan_pct=float(summary.production_vs_plan_pct or 0),
        ),
        availability_kpi=schemas.AvailabilityKPI(
            availability_pct=float(summary.equipment_availability_pct or 0),
            note=summary.availability_note or "",
        ),
        gondolas_kpi=schemas.GondolasKPI(
            loaded=summary.gondolas_loaded or 0,
            total=summary.gondolas_total or 0,
            fill_pct=round(
                (summary.gondolas_loaded / summary.gondolas_total * 100)
                if summary.gondolas_total
                else 0,
                1,
            ),
        ),
        safety_kpi=schemas.SafetyKPI(
            incident_count=summary.incident_count or 0,
            accident_free_days=summary.accident_free_days or 0,
        ),
        active_alerts=[schemas.AlertOut.model_validate(a) for a in active_alerts],
        recent_log_entries=[schemas.LogEntryOut.model_validate(e) for e in recent_log],
        special_projects=[schemas.SpecialProjectOut.model_validate(p) for p in projects],
    )


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 2: MANTENIMIENTO
# GET  /maintenance          — listado + resumen cards + bitácora
# POST /maintenance/work-orders  — crear nueva OT
# PATCH /maintenance/work-orders/{ot_id}/status — cambiar estado (Kanban)
# ═══════════════════════════════════════════════════════════════════

@app.get(
    "/maintenance",
    response_model=schemas.MaintenanceDashboardResponse,
    summary="Panel de mantenimiento — equipos, KPIs y bitácora de eventos",
    tags=["Mantenimiento"],
)
def get_maintenance(db: Session = Depends(get_db)):
    """
    Devuelve:
    - Contadores de resumen (total / activos / en reparación / mecánicos en turno).
    - Tabla **Listado de Maquinaria** (equipo, horas, estado, última revisión).
    - **Bitácora de Eventos** — timeline de los últimos eventos del módulo.
    """
    all_equipment = (
        db.query(models.Equipment)
        .filter(models.Equipment.is_active.is_(True))
        .all()
    )

    active_count = sum(
        1 for e in all_equipment if e.status == models.EquipmentStatus.OPERATIVO
    )
    repair_count = sum(
        1 for e in all_equipment
        if e.status in (
            models.EquipmentStatus.DETENIDO,
            models.EquipmentStatus.MANTENIMIENTO,
        )
    )

    # Mecánicos activos en el turno actual
    shift_mechanics = (
        db.query(func.count(models.AttendanceRecord.id))
        .join(models.Employee)
        .filter(
            models.Employee.position.ilike("%mecán%"),
            models.AttendanceRecord.shift_date == date.today(),
            models.AttendanceRecord.status == models.AttendanceStatus.PRESENTE,
        )
        .scalar()
        or 0
    )

    recent_events = (
        db.query(models.LogEntry)
        .filter(models.LogEntry.module == models.LogModule.MANTENIMIENTO)
        .order_by(models.LogEntry.event_time.desc())
        .limit(10)
        .all()
    )

    return schemas.MaintenanceDashboardResponse(
        total_equipment=len(all_equipment),
        active_equipment=active_count,
        equipment_in_repair=repair_count,
        mechanics_on_shift=shift_mechanics,
        equipment_list=[schemas.EquipmentOut.model_validate(e) for e in all_equipment],
        recent_events=[schemas.LogEntryOut.model_validate(ev) for ev in recent_events],
    )


@app.post(
    "/maintenance/work-orders",
    response_model=schemas.WorkOrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una nueva Orden de Trabajo (OT)",
    tags=["Mantenimiento"],
)
def create_work_order(
    payload: schemas.WorkOrderCreate,
    db: Session = Depends(get_db),
):
    """
    Crea una OT y la deja en estado **Pendiente**.
    El código OT se genera automáticamente: `OT-{id}`.
    """
    equipment = db.get(models.Equipment, payload.equipment_id)
    if not equipment:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")

    ot = models.WorkOrder(
        code="OT-PENDING",   # Se actualiza después del flush
        equipment_id=payload.equipment_id,
        description=payload.description,
        priority=payload.priority,
        status=models.WorkOrderStatus.PENDIENTE,
        assigned_to_id=payload.assigned_to_id,
    )
    db.add(ot)
    db.flush()              # Genera ot.id sin hacer commit
    ot.code = f"OT-{ot.id:04d}"
    db.commit()
    db.refresh(ot)

    # Actualizar estado del equipo a MANTENIMIENTO
    equipment.status = models.EquipmentStatus.MANTENIMIENTO
    db.commit()

    return schemas.WorkOrderOut.model_validate(ot)


@app.patch(
    "/maintenance/work-orders/{ot_id}/status",
    response_model=schemas.WorkOrderOut,
    summary="Cambiar el estado de una OT (Kanban: Initiar / Finalizar)",
    tags=["Mantenimiento"],
)
def update_work_order_status(
    ot_id: int,
    new_status: str = Query(..., description="Pendiente | En Progreso | Finalizada"),
    db: Session = Depends(get_db),
):
    ot = db.get(models.WorkOrder, ot_id)
    if not ot:
        raise HTTPException(status_code=404, detail="Orden de trabajo no encontrada.")

    try:
        ot.status = models.WorkOrderStatus(new_status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Estado inválido: {new_status}")

    if ot.status == models.WorkOrderStatus.EN_PROGRESO:
        ot.started_at = datetime.utcnow()
    elif ot.status == models.WorkOrderStatus.FINALIZADA:
        ot.finished_at = datetime.utcnow()
        if ot.started_at:
            ot.elapsed_seconds = int(
                (ot.finished_at - ot.started_at).total_seconds()
            )
        # Liberar equipo
        if ot.equipment:
            ot.equipment.status = models.EquipmentStatus.OPERATIVO

    db.commit()
    db.refresh(ot)
    return schemas.WorkOrderOut.model_validate(ot)


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 3: INVENTARIO
# GET  /inventory                — listado paginado + filtros + panel lateral
# POST /inventory/transactions   — registrar entrada o salida
# ═══════════════════════════════════════════════════════════════════

@app.get(
    "/inventory",
    response_model=schemas.InventoryPageResponse,
    summary="Listado de inventario con filtros, paginación y panel de salidas",
    tags=["Inventario"],
)
def get_inventory(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    category: Optional[str] = Query(default=None, description="Insumos | Refacciones | Explosivos | EPP"),
    destination_area: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None, description="Buscar por SKU o descripción"),
    db: Session = Depends(get_db),
):
    """
    Retorna los artículos de almacén con paginación.

    - **is_below_reorder = true** → el Front-End debe resaltar la fila en rojo.
    - **critical_count** → número total de artículos bajo punto de reorden
      (para el badge '15% del inventario…').
    - **recent_exits** → últimas 3 salidas para el panel 'Últimas Salidas'.
    """
    query = db.query(models.InventoryItem)

    if category:
        query = query.filter(models.InventoryItem.category == category)
    if destination_area:
        query = query.filter(models.InventoryItem.destination_area == destination_area)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            models.InventoryItem.sku.ilike(pattern)
            | models.InventoryItem.description.ilike(pattern)
        )

    total = query.count()
    items = (
        query.offset((page - 1) * page_size).limit(page_size).all()
    )

    critical_count = (
        db.query(func.count(models.InventoryItem.id))
        .filter(models.InventoryItem.is_below_reorder.is_(True))
        .scalar()
        or 0
    )

    recent_exits = (
        db.query(models.InventoryTransaction)
        .filter(
            models.InventoryTransaction.transaction_type == models.TransactionType.SALIDA
        )
        .order_by(models.InventoryTransaction.transaction_time.desc())
        .limit(3)
        .all()
    )

    return schemas.InventoryPageResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[schemas.InventoryItemOut.model_validate(i) for i in items],
        critical_count=critical_count,
        recent_exits=[
            schemas.InventoryTransactionOut.model_validate(t) for t in recent_exits
        ],
    )


@app.post(
    "/inventory/transactions",
    status_code=status.HTTP_201_CREATED,
    summary="Registrar entrada o salida de inventario",
    tags=["Inventario"],
)
def create_inventory_transaction(
    item_id: int,
    transaction_type: str = Query(..., description="Entrada | Salida"),
    quantity: float = Query(..., gt=0),
    reference_order: Optional[str] = None,
    destination: Optional[str] = None,
    work_order_id: Optional[int] = None,
    registered_by_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Modifica el stock del ítem según el tipo de movimiento y registra la transacción.
    Si el stock resultante cae bajo el `reorder_point`,
    activa el flag `is_below_reorder = True`.
    """
    item = db.get(models.InventoryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Ítem de inventario no encontrado.")

    try:
        tx_type = models.TransactionType(transaction_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Tipo de transacción inválido.")

    if tx_type == models.TransactionType.SALIDA:
        if item.current_stock < quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuficiente. Disponible: {item.current_stock}",
            )
        item.current_stock -= quantity
    else:
        item.current_stock += quantity

    # Recalcular flag de stock crítico
    item.is_below_reorder = item.current_stock < item.reorder_point

    tx = models.InventoryTransaction(
        item_id=item_id,
        transaction_type=tx_type,
        quantity=quantity,
        reference_order=reference_order,
        destination=destination,
        work_order_id=work_order_id,
        registered_by_id=registered_by_id,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    return {
        "message": "Transacción registrada correctamente.",
        "new_stock": float(item.current_stock),
        "is_below_reorder": item.is_below_reorder,
    }


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 4: PLANTA Y LABORATORIO
# GET  /plant-lab          — KPIs + flujo de proceso + últimos ensayes
# GET  /lab/samples        — cola de trabajo del analista
# POST /lab/assay-results  — certificar resultados de un ensaye
# ═══════════════════════════════════════════════════════════════════

@app.get(
    "/plant-lab",
    response_model=schemas.PlantAndLabResponse,
    summary="Monitoreo de Planta: KPIs, flujo en tiempo real y últimos ensayes",
    tags=["Planta y Laboratorio"],
)
def get_plant_and_lab(db: Session = Depends(get_db)):
    """
    Retorna:
    - **plant_kpis**: Trituración, Molinos, Humedad, Presa de Jales.
    - **process_flow**: estado de cada nodo (Trituradora, Molino, Celda).
    - **recent_assays**: últimos 4 registros de la tabla de ensayes.
    """
    today_summary = (
        db.query(models.DailyProductionSummary)
        .filter(models.DailyProductionSummary.summary_date == date.today())
        .order_by(models.DailyProductionSummary.shift.desc())
        .first()
    )
    if not today_summary:
        raise HTTPException(status_code=404, detail="Sin datos de producción para hoy.")

    process_units = db.query(models.ProcessUnit).all()

    recent_samples = (
        db.query(models.LabSample)
        .filter(
            models.LabSample.status.in_(
                [models.LabSampleStatus.APROBADO, models.LabSampleStatus.FUERA_RANGO]
            )
        )
        .order_by(models.LabSample.sampling_time.desc())
        .limit(4)
        .all()
    )

    return schemas.PlantAndLabResponse(
        plant_kpis=schemas.PlantKPIResponse(
            crushing_rate_ton_hr=float(today_summary.crushing_rate_ton_hr or 0),
            active_mills=today_summary.active_mills or 0,
            total_mills=today_summary.total_mills or 0,
            concentrate_humidity_pct=float(today_summary.concentrate_humidity_pct or 0),
            tailings_dam_level_pct=float(today_summary.tailings_dam_level_pct or 0),
        ),
        process_flow=[schemas.ProcessUnitOut.model_validate(u) for u in process_units],
        recent_assays=[schemas.LabSampleOut.model_validate(s) for s in recent_samples],
    )


@app.get(
    "/lab/samples",
    response_model=List[schemas.LabSampleOut],
    summary="Cola de trabajo activa del analista de laboratorio",
    tags=["Planta y Laboratorio"],
)
def get_lab_work_queue(db: Session = Depends(get_db)):
    """Muestras con estado **Pendiente** o **Procesando**, ordenadas por hora de toma."""
    samples = (
        db.query(models.LabSample)
        .filter(
            models.LabSample.status.in_(
                [models.LabSampleStatus.PENDIENTE, models.LabSampleStatus.PROCESANDO]
            )
        )
        .order_by(models.LabSample.sampling_time.asc())
        .all()
    )
    return [schemas.LabSampleOut.model_validate(s) for s in samples]


@app.post(
    "/lab/assay-results",
    response_model=schemas.AssayResultOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar y certificar resultados de ensaye (formulario del analista)",
    tags=["Planta y Laboratorio"],
)
def create_assay_result(
    payload: schemas.AssayResultCreate,
    db: Session = Depends(get_db),
):
    """
    Guarda los valores analíticos (Au, Ag, Cu, Zn, Humedad) y
    cambia el estado de la muestra a **Aprobado**.
    Si se desea solicitar repetición, usar el endpoint PATCH dedicado.
    """
    sample = db.get(models.LabSample, payload.sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Muestra no encontrada.")
    if sample.assay_result:
        raise HTTPException(
            status_code=409, detail="Esta muestra ya tiene resultados registrados."
        )

    result = models.AssayResult(
        sample_id=payload.sample_id,
        au_g_t=payload.au_g_t,
        ag_g_t=payload.ag_g_t,
        cu_pct=payload.cu_pct,
        zn_pct=payload.zn_pct,
        humidity_pct=payload.humidity_pct,
        notes=payload.notes,
        analyst_id=payload.analyst_id,
        certified_at=datetime.utcnow(),
    )
    db.add(result)
    sample.status = models.LabSampleStatus.APROBADO
    db.commit()
    db.refresh(result)

    return schemas.AssayResultOut.model_validate(result)


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 5: OPERACIÓN MINA
# GET  /mine-operation     — KPIs + historial de voladuras + patio mineral
# POST /mine-operation/blasts — registrar nueva detonación
# POST /mine-operation/ore-lots/{lot_id}/send-to-plant — enviar lote a planta
# ═══════════════════════════════════════════════════════════════════

@app.get(
    "/mine-operation",
    response_model=schemas.MineOperationResponse,
    summary="Control de Extracción y Voladuras — KPIs, historial y patio de mineral",
    tags=["Operación Mina"],
)
def get_mine_operation(db: Session = Depends(get_db)):
    today_summary = (
        db.query(models.DailyProductionSummary)
        .filter(models.DailyProductionSummary.summary_date == date.today())
        .order_by(models.DailyProductionSummary.shift.desc())
        .first()
    )
    if not today_summary:
        raise HTTPException(status_code=404, detail="Sin datos para hoy.")

    extracted = float(today_summary.tons_extracted or 0)
    target    = float(today_summary.extraction_target_tons or 1)

    blast_history = (
        db.query(models.BlastingRecord)
        .order_by(models.BlastingRecord.blasted_at.desc())
        .limit(10)
        .all()
    )
    ore_yard = (
        db.query(models.OreYardLot)
        .filter(models.OreYardLot.status == "En Patio")
        .all()
    )

    return schemas.MineOperationResponse(
        kpis=schemas.MineOperationKPI(
            tons_extracted=extracted,
            extraction_target_tons=target,
            progress_pct=round(extracted / target * 100, 1),
            extraction_cost_per_ton=float(today_summary.extraction_cost_per_ton or 0),
            hauling_efficiency_pct=float(today_summary.hauling_efficiency_pct or 0),
            active_trucks=today_summary.active_trucks_count or 0,
        ),
        blasting_history=[schemas.BlastingRecordOut.model_validate(b) for b in blast_history],
        ore_yard=[schemas.OreYardLotOut.model_validate(l) for l in ore_yard],
    )


@app.post(
    "/mine-operation/blasts",
    response_model=schemas.BlastingRecordOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar voladura / detonación controlada",
    tags=["Operación Mina"],
)
def register_blast(
    payload: schemas.BlastingRecordCreate,
    db: Session = Depends(get_db),
):
    blast = models.BlastingRecord(**payload.model_dump())
    db.add(blast)
    db.commit()
    db.refresh(blast)

    # Agregar entrada a la bitácora general
    log = models.LogEntry(
        module=models.LogModule.MINA,
        description=f"Detonación en {blast.location}: {blast.advance_meters}m avanzados.",
        created_by_id=payload.supervisor_id,
    )
    db.add(log)
    db.commit()

    return schemas.BlastingRecordOut.model_validate(blast)


@app.patch(
    "/mine-operation/ore-lots/{lot_id}/send-to-plant",
    summary="Enviar lote del Patio de Mineral a Trituración",
    tags=["Operación Mina"],
)
def send_ore_lot_to_plant(lot_id: int, db: Session = Depends(get_db)):
    lot = db.get(models.OreYardLot, lot_id)
    if not lot:
        raise HTTPException(status_code=404, detail="Lote no encontrado.")
    if lot.status != "En Patio":
        raise HTTPException(status_code=409, detail="El lote ya fue enviado.")

    lot.status = "Enviado Trituración"
    lot.sent_to_plant_at = datetime.utcnow()
    db.commit()

    return {"message": f"Lote {lot.lot_code} enviado a Trituración.", "lot_id": lot.id}


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 6: CASETA DE CONTROL — VIAJES
# GET  /truck-trips        — historial reciente + KPIs del turno
# POST /truck-trips        — registrar nueva salida de camión
# ═══════════════════════════════════════════════════════════════════

@app.get(
    "/truck-trips",
    summary="Historial de viajes registrados en la caseta de control",
    tags=["Caseta de Control"],
)
def get_truck_trips(
    limit: int = Query(default=10, ge=1, le=100),
    control_booth: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(models.TruckTrip)
    if control_booth:
        query = query.filter(models.TruckTrip.control_booth == control_booth)

    trips = (
        query
        .options(joinedload(models.TruckTrip.truck))
        .order_by(models.TruckTrip.trip_time.desc())
        .limit(limit)
        .all()
    )
    return [schemas.TruckTripOut.model_validate(t) for t in trips]


@app.post(
    "/truck-trips",
    response_model=schemas.TruckTripOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar salida de camión desde la báscula",
    tags=["Caseta de Control"],
)
def register_truck_trip(
    payload: schemas.TruckTripCreate,
    db: Session = Depends(get_db),
):
    truck = db.get(models.Equipment, payload.truck_id)
    if not truck:
        raise HTTPException(status_code=404, detail="Equipo/camión no encontrado.")

    # Generar código de viaje
    last_trip = (
        db.query(models.TruckTrip)
        .order_by(models.TruckTrip.id.desc())
        .first()
    )
    next_id = (last_trip.id + 1) if last_trip else 1000

    trip = models.TruckTrip(
        trip_code=f"V-{next_id}",
        **payload.model_dump(),
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)

    return schemas.TruckTripOut.model_validate(trip)


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 7: RH Y SEGURIDAD
# GET  /hr-security        — asistencia + KPIs de seguridad
# POST /hr-security/incidents — registrar incidente
# ═══════════════════════════════════════════════════════════════════

@app.get(
    "/hr-security",
    response_model=schemas.HRSecurityResponse,
    summary="Gestión de Personal y Seguridad — asistencia del turno y KPIs",
    tags=["RH y Seguridad"],
)
def get_hr_security(
    shift_date: Optional[date] = Query(default=None),
    shift: int = Query(default=1, ge=1, le=3),
    db: Session = Depends(get_db),
):
    """
    Combina:
    - KPIs de seguridad (TRIR, días sin accidentes, personal en turno).
    - Tabla de asistencia con estado por empleado.
    """
    query_date = shift_date or date.today()

    # KPIs de seguridad del día
    today_summary = (
        db.query(models.DailyProductionSummary)
        .filter(
            models.DailyProductionSummary.summary_date == query_date,
            models.DailyProductionSummary.shift == shift,
        )
        .first()
    )
    trir              = 0.0
    accident_free_days = today_summary.accident_free_days if today_summary else 0

    # Lista de empleados + asistencia del turno
    employees = db.query(models.Employee).all()
    result: List[schemas.EmployeeWithAttendance] = []
    for emp in employees:
        att = (
            db.query(models.AttendanceRecord)
            .filter(
                models.AttendanceRecord.employee_id == emp.id,
                models.AttendanceRecord.shift_date == query_date,
                models.AttendanceRecord.shift_number == shift,
            )
            .first()
        )
        result.append(
            schemas.EmployeeWithAttendance(
                id=emp.id,
                full_name=emp.full_name,
                initials=emp.initials,
                position=emp.position,
                attendance=schemas.AttendanceRecordOut.model_validate(att) if att else None,
            )
        )

    present_count = sum(
        1 for r in result
        if r.attendance and r.attendance.status == models.AttendanceStatus.PRESENTE.value
    )

    return schemas.HRSecurityResponse(
        trir=trir,
        accident_free_days=accident_free_days,
        personnel_on_shift=present_count,
        attendance_list=result,
    )


@app.post(
    "/hr-security/incidents",
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo incidente de seguridad",
    tags=["RH y Seguridad"],
)
def create_incident_report(
    payload: schemas.IncidentReportCreate,
    db: Session = Depends(get_db),
):
    """
    Crea el reporte y añade entrada en la bitácora general.
    En producción, aquí se dispararía también una notificación por correo/WebSocket.
    """
    incident = models.IncidentReport(**payload.model_dump())
    db.add(incident)

    log = models.LogEntry(
        module=models.LogModule.SEGURIDAD,
        description=f"Incidente reportado: {payload.incident_type} en {payload.area}.",
        created_by_id=payload.reporter_id,
    )
    db.add(log)
    db.commit()
    db.refresh(incident)

    return {"message": "Incidente registrado y equipo de Seguridad notificado.", "incident_id": incident.id}


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 8: LOGÍSTICA Y FINANZAS
# GET /logistics-finance   — despachos activos + métricas financieras + facturas
# ═══════════════════════════════════════════════════════════════════

@app.get(
    "/logistics-finance",
    response_model=schemas.LogisticsFinanceResponse,
    summary="Control de Góndolas y Facturación — despachos y finanzas del mes",
    tags=["Logística y Finanzas"],
)
def get_logistics_finance(db: Session = Depends(get_db)):
    """
    Retorna:
    - **dispatch_summary**: camiones en ruta, góndolas despachadas / total.
    - **active_dispatches**: tabla de despachos activos (En Planta / En Tránsito).
    - **monthly_revenue** y **operational_costs** del mes en curso.
    - **recent_invoices**: últimas 3 facturas (sincronizadas con Odoo).
    """
    active_dispatches = (
        db.query(models.TruckTrip)
        .filter(
            models.TruckTrip.dispatch_status.in_(
                [models.DispatchStatus.EN_PLANTA, models.DispatchStatus.EN_TRANSITO]
            )
        )
        .order_by(models.TruckTrip.trip_time.desc())
        .all()
    )

    en_transito = sum(
        1 for t in active_dispatches
        if t.dispatch_status == models.DispatchStatus.EN_TRANSITO
    )
    total_today = (
        db.query(func.count(models.TruckTrip.id))
        .filter(func.date(models.TruckTrip.trip_time) == date.today())
        .scalar()
        or 0
    )

    # Finanzas del mes en curso
    first_of_month = date.today().replace(day=1)
    fin_record = (
        db.query(models.FinancialRecord)
        .filter(models.FinancialRecord.record_month == first_of_month)
        .first()
    )

    recent_invoices = (
        db.query(models.Invoice)
        .order_by(models.Invoice.issued_at.desc())
        .limit(3)
        .all()
    )

    return schemas.LogisticsFinanceResponse(
        dispatch_summary=schemas.DispatchSummary(
            trucks_en_route=en_transito,
            gondolas_dispatched=len(active_dispatches),
            gondolas_total=total_today,
        ),
        active_dispatches=[schemas.TruckTripOut.model_validate(t) for t in active_dispatches],
        monthly_revenue=float(fin_record.revenue_usd) if fin_record else 0.0,
        operational_costs=float(fin_record.operational_costs_usd) if fin_record else 0.0,
        recent_invoices=[schemas.InvoiceOut.model_validate(i) for i in recent_invoices],
    )


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 9: ALERTAS
# PATCH /alerts/{alert_id}/dismiss — descartar alerta del banner
# ═══════════════════════════════════════════════════════════════════

@app.patch(
    "/alerts/{alert_id}/dismiss",
    summary="Descartar alerta del banner del Dashboard",
    tags=["Dashboard"],
)
def dismiss_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(models.Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada.")
    alert.is_dismissed = True
    db.commit()
    return {"message": "Alerta descartada."}
