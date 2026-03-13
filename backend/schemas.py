"""
schemas.py
Esquemas Pydantic para validación de peticiones (Request) y serialización
de respuestas (Response) de la API FastAPI.

Cada sección corresponde a un módulo / pantalla del ERP.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


# ─────────────────────────────────────────────
# Helpers comunes
# ─────────────────────────────────────────────

class OrmBase(BaseModel):
    """Pydantic con orm_mode activado para conversión directa desde SQLAlchemy."""
    model_config = ConfigDict(from_attributes=True)


# ═══════════════════════════════════════════════════════════════════
# ALERTAS
# ═══════════════════════════════════════════════════════════════════

class AlertOut(OrmBase):
    id          : int
    severity    : str
    title       : str
    message     : str
    source_module: Optional[str]
    is_dismissed: bool
    created_at  : datetime


# ═══════════════════════════════════════════════════════════════════
# BITÁCORA GENERAL
# ═══════════════════════════════════════════════════════════════════

class LogEntryOut(OrmBase):
    id           : int
    module       : str
    description  : str
    event_time   : datetime


# ═══════════════════════════════════════════════════════════════════
# PROYECTOS ESPECIALES
# ═══════════════════════════════════════════════════════════════════

class SpecialProjectOut(OrmBase):
    id            : int
    name          : str
    current_phase : Optional[str]
    progress_pct  : float
    start_date    : date
    end_date      : date


# ═══════════════════════════════════════════════════════════════════
# KPIs DEL DASHBOARD
# ═══════════════════════════════════════════════════════════════════

class ProductionKPI(BaseModel):
    """KPI card: Producción"""
    tons_produced        : float
    plan_tons            : float
    vs_plan_pct          : float        # +5 → muestra "+5% vs plan"


class AvailabilityKPI(BaseModel):
    """KPI card: Disponibilidad de equipos"""
    availability_pct     : float        # 88.0
    note                 : str          # "-2% Molino 2"


class GondolasKPI(BaseModel):
    """KPI card: Góndolas Cargadas"""
    loaded               : int          # 6
    total                : int          # 8
    fill_pct             : float        # 75.0


class SafetyKPI(BaseModel):
    """KPI card: Seguridad"""
    incident_count       : int          # 0
    accident_free_days   : int          # 120


class DashboardResponse(BaseModel):
    """Respuesta completa del endpoint GET /dashboard."""
    summary_date        : date
    shift               : int
    production_kpi      : ProductionKPI
    availability_kpi    : AvailabilityKPI
    gondolas_kpi        : GondolasKPI
    safety_kpi          : SafetyKPI
    active_alerts       : List[AlertOut]
    recent_log_entries  : List[LogEntryOut]
    special_projects    : List[SpecialProjectOut]


# ═══════════════════════════════════════════════════════════════════
# EQUIPOS Y MANTENIMIENTO
# ═══════════════════════════════════════════════════════════════════

class EquipmentOut(OrmBase):
    id                     : int
    code                   : str         # "EQ-001"
    name                   : str         # "Molino Primario 2"
    accumulated_hours      : float       # 1250
    status                 : str         # "Operativo"
    last_maintenance_date  : Optional[date]
    location               : Optional[str]


class WorkOrderOut(OrmBase):
    id          : int
    code        : str                    # "OT-998"
    description : str
    priority    : str
    status      : str
    created_at  : datetime
    started_at  : Optional[datetime]
    finished_at : Optional[datetime]
    elapsed_seconds: Optional[int]


class WorkOrderCreate(BaseModel):
    equipment_id    : int
    description     : str
    priority        : str = "Media"
    assigned_to_id  : Optional[int] = None


class MaintenanceDashboardResponse(BaseModel):
    """Respuesta del endpoint GET /maintenance."""
    total_equipment      : int           # 28
    active_equipment     : int           # 24
    equipment_in_repair  : int           # 4
    mechanics_on_shift   : int           # 5
    equipment_list       : List[EquipmentOut]
    recent_events        : List[LogEntryOut]


# ═══════════════════════════════════════════════════════════════════
# INVENTARIO
# ═══════════════════════════════════════════════════════════════════

class InventoryItemOut(OrmBase):
    id              : int
    sku             : str                # "INV-001"
    description     : str
    detail          : Optional[str]
    category        : str
    current_stock   : float
    reorder_point   : float
    is_below_reorder: bool
    unit            : str


class InventoryTransactionOut(OrmBase):
    id               : int
    transaction_type : str
    quantity         : float
    reference_order  : Optional[str]
    destination      : Optional[str]
    transaction_time : datetime


class InventoryPageResponse(BaseModel):
    """Respuesta del endpoint GET /inventory con paginación."""
    total             : int
    page              : int
    page_size         : int
    items             : List[InventoryItemOut]
    critical_count    : int              # cantidad < reorder_point
    recent_exits      : List[InventoryTransactionOut]


# ═══════════════════════════════════════════════════════════════════
# PLANTA Y LABORATORIO
# ═══════════════════════════════════════════════════════════════════

class PlantKPIResponse(BaseModel):
    """KPIs superiores de la pantalla Planta y Ensayes."""
    crushing_rate_ton_hr    : float      # 120
    active_mills            : int        # 3
    total_mills             : int        # 3
    concentrate_humidity_pct: float      # 8.5
    tailings_dam_level_pct  : float      # 65.0


class ProcessUnitOut(OrmBase):
    code   : str        # "PR-01"
    name   : str        # "Trituradoras"
    status : str        # "Operando"


class LabSampleOut(OrmBase):
    id          : int
    sample_code : str
    origin      : str
    sampling_time: datetime
    status      : str
    priority    : Optional[str]


class AssayResultOut(OrmBase):
    id           : int
    sample_id    : int
    au_g_t       : Optional[float]
    ag_g_t       : Optional[float]
    cu_pct       : Optional[float]
    zn_pct       : Optional[float]
    humidity_pct : Optional[float]
    certified_at : Optional[datetime]


class AssayResultCreate(BaseModel):
    sample_id    : int
    au_g_t       : float
    ag_g_t       : float
    cu_pct       : Optional[float] = None
    zn_pct       : Optional[float] = None
    humidity_pct : float
    notes        : Optional[str]  = None
    analyst_id   : Optional[int]  = None


class PlantAndLabResponse(BaseModel):
    """Respuesta del endpoint GET /plant-lab."""
    plant_kpis      : PlantKPIResponse
    process_flow    : List[ProcessUnitOut]
    recent_assays   : List[LabSampleOut]


# ═══════════════════════════════════════════════════════════════════
# OPERACIÓN MINA
# ═══════════════════════════════════════════════════════════════════

class MineOperationKPI(BaseModel):
    tons_extracted          : float      # 850
    extraction_target_tons  : float      # 1000
    progress_pct            : float      # 85.0
    extraction_cost_per_ton : float      # 12.50
    hauling_efficiency_pct  : float      # 92.0
    active_trucks           : int        # 12


class BlastingRecordOut(OrmBase):
    id              : int
    blast_code      : Optional[str]
    location        : str
    advance_meters  : float
    explosive_kg    : float
    status          : str
    blasted_at      : datetime


class BlastingRecordCreate(BaseModel):
    location        : str
    advance_meters  : float
    explosive_kg    : float
    supervisor_notes: Optional[str] = None
    supervisor_id   : Optional[int] = None


class OreYardLotOut(OrmBase):
    id        : int
    lot_code  : str
    ore_type  : str
    tons      : float
    status    : str


class MineOperationResponse(BaseModel):
    """Respuesta del endpoint GET /mine-operation."""
    kpis              : MineOperationKPI
    blasting_history  : List[BlastingRecordOut]
    ore_yard          : List[OreYardLotOut]


# ═══════════════════════════════════════════════════════════════════
# CASETA DE CONTROL — VIAJES
# ═══════════════════════════════════════════════════════════════════

class TruckTripOut(OrmBase):
    id               : int
    trip_code        : Optional[str]
    truck_unit_code  : str             # "CAT-104"
    weight_tons      : float
    destination_type : str
    destination_name : Optional[str]
    dispatch_status  : str
    trip_time        : datetime
    plates           : Optional[str]


class TruckTripCreate(BaseModel):
    truck_id         : int
    truck_unit_code  : str
    weight_tons      : float
    destination_type : str
    destination_name : Optional[str] = None
    control_booth    : Optional[str] = None
    registered_by_id : Optional[int] = None
    plates           : Optional[str] = None


# ═══════════════════════════════════════════════════════════════════
# RH Y SEGURIDAD
# ═══════════════════════════════════════════════════════════════════

class AttendanceRecordOut(OrmBase):
    id              : int
    employee_id     : int
    shift_date      : date
    check_in_time   : Optional[str]
    status          : str


class EmployeeWithAttendance(OrmBase):
    id        : int
    full_name : str
    initials  : Optional[str]
    position  : str
    attendance: Optional[AttendanceRecordOut]


class IncidentReportCreate(BaseModel):
    incident_type : str
    area          : str
    description   : str
    reporter_id   : Optional[int] = None


class HRSecurityResponse(BaseModel):
    """Respuesta del endpoint GET /hr-security."""
    trir                 : float        # 0.0
    accident_free_days   : int          # 120
    personnel_on_shift   : int          # 85
    attendance_list      : List[EmployeeWithAttendance]


# ═══════════════════════════════════════════════════════════════════
# LOGÍSTICA Y FINANZAS
# ═══════════════════════════════════════════════════════════════════

class DispatchSummary(BaseModel):
    trucks_en_route        : int         # 4
    gondolas_dispatched    : int         # 6
    gondolas_total         : int         # 8


class InvoiceOut(OrmBase):
    id             : int
    invoice_number : str
    client_name    : str
    amount_usd     : float
    sync_status    : str
    issued_at      : datetime


class LogisticsFinanceResponse(BaseModel):
    """Respuesta del endpoint GET /logistics-finance."""
    dispatch_summary  : DispatchSummary
    active_dispatches : List[TruckTripOut]
    monthly_revenue   : float
    operational_costs : float
    recent_invoices   : List[InvoiceOut]
