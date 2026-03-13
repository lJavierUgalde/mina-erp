"""
models.py
Modelos de base de datos SQLAlchemy para Mina ERP.

Módulos cubiertos:
  - Auth / Usuarios
  - Dashboard / Alertas / Bitácora
  - Equipos y Mantenimiento
  - Inventario y Almacén
  - Planta y Laboratorio
  - Operación Mina (Extracción y Voladuras)
  - Caseta de Control (Viajes de Camiones)
  - RH y Seguridad
  - Logística y Finanzas
"""

import enum
from datetime import datetime, date

from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, Enum, Float,
    ForeignKey, Integer, Numeric, String, Text, func,
)
from sqlalchemy.orm import relationship

from database import Base


# ═══════════════════════════════════════════════════════════════════
# ENUMERACIONES
# ═══════════════════════════════════════════════════════════════════

class EquipmentStatus(str, enum.Enum):
    OPERATIVO    = "Operativo"
    DETENIDO     = "Detenido"
    MANTENIMIENTO = "Mantenimiento"


class WorkOrderPriority(str, enum.Enum):
    ALTA  = "Alta"
    MEDIA = "Media"
    BAJA  = "Baja"


class WorkOrderStatus(str, enum.Enum):
    PENDIENTE   = "Pendiente"
    EN_PROGRESO = "En Progreso"
    FINALIZADA  = "Finalizada"
    CANCELADA   = "Cancelada"


class InventoryCategory(str, enum.Enum):
    INSUMOS     = "Insumos"
    REFACCIONES = "Refacciones"
    EXPLOSIVOS  = "Explosivos"
    EPP         = "EPP"


class TransactionType(str, enum.Enum):
    ENTRADA = "Entrada"
    SALIDA  = "Salida"


class LabSampleStatus(str, enum.Enum):
    PENDIENTE   = "Pendiente"
    PROCESANDO  = "Procesando"
    APROBADO    = "Aprobado"
    FUERA_RANGO = "Fuera Rango"
    REPETICION  = "Repeticion Solicitada"


class DispatchStatus(str, enum.Enum):
    EN_PLANTA   = "En Planta"
    EN_TRANSITO = "En Tránsito"
    ENTREGADO   = "Entregado"


class BlastingStatus(str, enum.Enum):
    EXITOSA           = "Exitosa"
    PENDIENTE_INSPECCION = "Pend. Inspección"
    FALLIDA           = "Fallida"


class AttendanceStatus(str, enum.Enum):
    PRESENTE = "Presente"
    AUSENTE  = "Ausente"
    PERMISO  = "Permiso"


class IncidentSeverity(str, enum.Enum):
    CASI_ACCIDENTE = "Casi accidente"
    LESION_MENOR   = "Lesión menor"
    LESION_MAYOR   = "Lesión mayor"
    DANO_EQUIPO    = "Daño a equipo"


class AlertSeverity(str, enum.Enum):
    INFO     = "Info"
    WARNING  = "Warning"
    CRITICAL = "Critical"


class LogModule(str, enum.Enum):
    LABORATORIO   = "Laboratorio"
    INVENTARIO    = "Inventario"
    MINA          = "Mina"
    MANTENIMIENTO = "Mantenimiento"
    PLANTA        = "Planta"
    SEGURIDAD     = "Seguridad"
    LOGISTICA     = "Logística"


class ProcessUnitType(str, enum.Enum):
    TRITURADORA     = "Trituradora"
    MOLINO          = "Molino"
    CELDA_FLOTACION = "Celda Flotación"
    CRIBA           = "Criba"
    BOMBA           = "Bomba"
    CINTA           = "Cinta Transportadora"


class ProcessUnitStatus(str, enum.Enum):
    OPERANDO     = "Operando"
    MANTENIMIENTO= "Mantenimiento"
    DETENIDO     = "Detenido"


class DestinationType(str, enum.Enum):
    PLANTA_BENEFICIO = "Planta de Beneficio"
    TEPETATE         = "Tepetate (Escombrera)"
    STOCK_MINERAL    = "Stock de Mineral"
    PUERTO           = "Puerto"
    REFINERIA        = "Refinería"
    CLIENTE_EXTERNO  = "Cliente Externo"


class OreType(str, enum.Enum):
    MINERAL_RICO = "Mineral Rico (Au/Ag)"
    TEPETATE     = "Tepetate (Descapote)"
    CONCENTRADO  = "Concentrado Final"


# ═══════════════════════════════════════════════════════════════════
# 1. USUARIOS Y TURNOS
# ═══════════════════════════════════════════════════════════════════

class User(Base):
    """Usuarios del sistema ERP.
    Visible en: topbar de todas las pantallas (nombre, rol, estado).
    """
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    full_name     = Column(String(120), nullable=False)
    email         = Column(String(180), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role          = Column(String(80), nullable=False)   # "Gerente Turno 1", "Mecánico", etc.
    employee_id   = Column(String(20), unique=True)      # "44920"
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    # Relaciones
    work_orders       = relationship("WorkOrder", back_populates="assigned_to_user",
                                     foreign_keys="WorkOrder.assigned_to_id")
    created_log_entries = relationship("LogEntry", back_populates="created_by_user")
    attendance_records  = relationship("AttendanceRecord", back_populates="employee")
    assay_results       = relationship("AssayResult", back_populates="analyst")


# ═══════════════════════════════════════════════════════════════════
# 2. ALERTAS Y BITÁCORA GENERAL
# ═══════════════════════════════════════════════════════════════════

class Alert(Base):
    """Alertas críticas que aparecen en el banner superior del Dashboard.
    Campo `is_dismissed` permite cerrarlas con el botón ✕.
    """
    __tablename__ = "alerts"

    id           = Column(Integer, primary_key=True, index=True)
    severity     = Column(Enum(AlertSeverity), nullable=False, default=AlertSeverity.CRITICAL)
    title        = Column(String(200), nullable=False)     # "Alerta Crítica"
    message      = Column(Text, nullable=False)            # "El Molino Primario 2 se detuvo..."
    source_module= Column(Enum(LogModule))                 # Módulo que originó la alerta
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=True)
    is_dismissed = Column(Boolean, default=False)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    equipment = relationship("Equipment", back_populates="alerts")


class LogEntry(Base):
    """Bitácora reciente de actividad — widget 'Bitácora Reciente' del Dashboard
    y 'Bitácora de Eventos' del módulo Mantenimiento.
    Cada fila = un evento de cualquier módulo.
    """
    __tablename__ = "log_entries"

    id             = Column(Integer, primary_key=True, index=True)
    module         = Column(Enum(LogModule), nullable=False)   # LABORATORIO, MINA…
    description    = Column(String(300), nullable=False)       # Texto del evento
    equipment_id   = Column(Integer, ForeignKey("equipment.id"), nullable=True)
    work_order_id  = Column(Integer, ForeignKey("work_orders.id"), nullable=True)
    created_by_id  = Column(Integer, ForeignKey("users.id"), nullable=True)
    event_time     = Column(DateTime(timezone=True), server_default=func.now())

    equipment        = relationship("Equipment")
    work_order       = relationship("WorkOrder")
    created_by_user  = relationship("User", back_populates="created_log_entries")


# ═══════════════════════════════════════════════════════════════════
# 3. PROYECTOS ESPECIALES (Gantt simplificado del Dashboard)
# ═══════════════════════════════════════════════════════════════════

class SpecialProject(Base):
    """Proyectos con barra de progreso tipo Gantt en el Dashboard.
    Ej.: 'Expansión Presa de Jales' al 60%, 'Mantenimiento Mayor Trituradora' al 15%.
    """
    __tablename__ = "special_projects"

    id             = Column(Integer, primary_key=True, index=True)
    name           = Column(String(200), nullable=False)
    current_phase  = Column(String(80))         # "Fase 3"
    progress_pct   = Column(Float, nullable=False)  # 0.0 – 100.0
    start_date     = Column(Date, nullable=False)
    end_date       = Column(Date, nullable=False)
    responsible_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_active      = Column(Boolean, default=True)

    responsible = relationship("User")


# ═══════════════════════════════════════════════════════════════════
# 4. RESUMEN DIARIO DE PRODUCCIÓN (KPIs del Dashboard)
# ═══════════════════════════════════════════════════════════════════

class DailyProductionSummary(Base):
    """Un registro por día / por turno que alimenta las 4 KPI cards del Dashboard:
    Producción, Disponibilidad, Góndolas, Seguridad.
    También contiene las métricas de Planta (Trituración, Molinos, Humedad, Jales).
    """
    __tablename__ = "daily_production_summary"

    id                       = Column(Integer, primary_key=True, index=True)
    summary_date             = Column(Date, nullable=False, index=True)
    shift                    = Column(Integer, default=1)  # 1, 2, 3

    # KPI: Producción
    total_tons_produced      = Column(Numeric(12, 2))  # 1250
    production_plan_tons     = Column(Numeric(12, 2))  # Meta del día
    production_vs_plan_pct   = Column(Float)           # +5%

    # KPI: Disponibilidad
    equipment_availability_pct = Column(Float)         # 88.0
    availability_note          = Column(String(100))   # "-2% Molino 2"

    # KPI: Góndolas
    gondolas_loaded          = Column(Integer)         # 6
    gondolas_total           = Column(Integer)         # 8

    # KPI: Seguridad
    incident_count           = Column(Integer, default=0)  # 0
    accident_free_days       = Column(Integer)             # 120

    # Planta – KPIs
    crushing_rate_ton_hr     = Column(Numeric(10, 2))  # 120 Ton/hr
    active_mills             = Column(Integer)         # 3
    total_mills              = Column(Integer)         # 3
    concentrate_humidity_pct = Column(Float)           # 8.5
    tailings_dam_level_pct   = Column(Float)           # 65.0

    # Operación Mina – KPIs (Caseta y Extracción)
    tons_extracted           = Column(Numeric(12, 2))  # 850
    extraction_target_tons   = Column(Numeric(12, 2))  # 1000
    extraction_cost_per_ton  = Column(Numeric(10, 4))  # 12.50
    hauling_efficiency_pct   = Column(Float)           # 92.0
    active_trucks_count      = Column(Integer)         # 12

    # Caseta de control
    trucks_dispatched        = Column(Integer)         # 14
    blasts_performed         = Column(Integer)         # 2
    blasts_planned           = Column(Integer)         # 2

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ═══════════════════════════════════════════════════════════════════
# 5. EQUIPOS Y MANTENIMIENTO
# ═══════════════════════════════════════════════════════════════════

class Equipment(Base):
    """Catálogo de maquinaria.
    Tabla 'Listado de Maquinaria' del módulo Mantenimiento.
    Columnas: ID Equipo, Nombre, Horas Acumuladas, Estado, Última Revisión.
    """
    __tablename__ = "equipment"

    id                  = Column(Integer, primary_key=True, index=True)
    code                = Column(String(20), unique=True, nullable=False, index=True)  # "EQ-001"
    name                = Column(String(150), nullable=False)   # "Molino Primario 2"
    equipment_type      = Column(Enum(ProcessUnitType))
    model               = Column(String(100))          # "CAT 797F"
    serial_number       = Column(String(100))
    accumulated_hours   = Column(Float, default=0.0)   # 1250
    status              = Column(Enum(EquipmentStatus),
                                 nullable=False, default=EquipmentStatus.OPERATIVO)
    last_maintenance_date = Column(Date)               # "10 Mar 2024"
    location            = Column(String(100))          # "Planta", "Nivel 450"
    is_active           = Column(Boolean, default=True)

    # Relaciones
    work_orders  = relationship("WorkOrder", back_populates="equipment")
    alerts       = relationship("Alert", back_populates="equipment")
    truck_trips  = relationship("TruckTrip", back_populates="truck")


class WorkOrder(Base):
    """Órdenes de Trabajo (OT).
    Visible en: tabla de mantenimiento, kanban del Taller, bodega (solicitudes).
    Ej.: OT-998 'Ruido en rodamiento', OT-995 'Reemplazo sello mecánico'.
    """
    __tablename__ = "work_orders"

    id             = Column(Integer, primary_key=True, index=True)
    code           = Column(String(20), unique=True, nullable=False, index=True)  # "OT-998"
    equipment_id   = Column(Integer, ForeignKey("equipment.id"), nullable=False)
    description    = Column(Text, nullable=False)
    priority       = Column(Enum(WorkOrderPriority), nullable=False,
                            default=WorkOrderPriority.MEDIA)
    status         = Column(Enum(WorkOrderStatus), nullable=False,
                            default=WorkOrderStatus.PENDIENTE)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    started_at     = Column(DateTime(timezone=True), nullable=True)
    finished_at    = Column(DateTime(timezone=True), nullable=True)
    elapsed_seconds= Column(BigInteger, nullable=True)  # Timer "02:15:00"

    equipment        = relationship("Equipment", back_populates="work_orders")
    assigned_to_user = relationship("User", back_populates="work_orders",
                                    foreign_keys=[assigned_to_id])
    requested_parts  = relationship("WarehouseRequest", back_populates="work_order")
    log_entries      = relationship("LogEntry", back_populates="work_order")


# ═══════════════════════════════════════════════════════════════════
# 6. INVENTARIO Y ALMACÉN
# ═══════════════════════════════════════════════════════════════════

class InventoryItem(Base):
    """Artículo del almacén.
    Tabla 'Inventario de Insumos y Refacciones':
    Columnas: SKU, Descripción, Categoría, Stock Actual, Punto de Reorden.
    """
    __tablename__ = "inventory_items"

    id              = Column(Integer, primary_key=True, index=True)
    sku             = Column(String(30), unique=True, nullable=False, index=True)  # "INV-001"
    description     = Column(String(200), nullable=False)      # "Aceite Hidráulico SAE 40"
    detail          = Column(String(200))                      # "Tambor 200L - Marca Shell"
    category        = Column(Enum(InventoryCategory), nullable=False)
    unit            = Column(String(30), default="unidad")     # "L", "kg", "caja", "unidad"
    destination_area= Column(String(80))                       # "Planta", "Mina", "Laboratorio"
    current_stock   = Column(Numeric(12, 2), nullable=False, default=0)  # 42
    reorder_point   = Column(Numeric(12, 2), nullable=False, default=0)  # 10
    is_below_reorder= Column(Boolean, default=False)           # Calculado / actualizado por trigger

    transactions = relationship("InventoryTransaction", back_populates="item")


class InventoryTransaction(Base):
    """Movimientos de inventario (entradas y salidas).
    Visible en el panel 'Últimas Salidas' y en los despachos del almacén.
    Ej.: 'Orden #442 — 20L de Aceite → Mantenimiento'.
    """
    __tablename__ = "inventory_transactions"

    id               = Column(Integer, primary_key=True, index=True)
    item_id          = Column(Integer, ForeignKey("inventory_items.id"), nullable=False)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    quantity         = Column(Numeric(12, 2), nullable=False)  # 20
    reference_order  = Column(String(30))                      # "Orden #442"
    work_order_id    = Column(Integer, ForeignKey("work_orders.id"), nullable=True)
    destination      = Column(String(100))                     # "Mantenimiento"
    registered_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    transaction_time = Column(DateTime(timezone=True), server_default=func.now())
    notes            = Column(Text)

    item          = relationship("InventoryItem", back_populates="transactions")
    registered_by = relationship("User")
    work_order    = relationship("WorkOrder")


class WarehouseRequest(Base):
    """Solicitud de materiales desde Taller → Bodega.
    Widget 'Solicitudes de Mantenimiento' del panel de bodega.
    Una OT puede tener una solicitud con múltiples ítems.
    """
    __tablename__ = "warehouse_requests"

    id              = Column(Integer, primary_key=True, index=True)
    work_order_id   = Column(Integer, ForeignKey("work_orders.id"), nullable=False)
    requester_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    status          = Column(String(30), default="Pendiente")  # Pendiente/Aprobada/Rechazada
    approved_by_id  = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at     = Column(DateTime(timezone=True), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    work_order   = relationship("WorkOrder", back_populates="requested_parts")
    requester    = relationship("User", foreign_keys=[requester_id])
    approved_by  = relationship("User", foreign_keys=[approved_by_id])
    items        = relationship("WarehouseRequestItem", back_populates="request")


class WarehouseRequestItem(Base):
    """Línea de artículo dentro de una WarehouseRequest.
    Muestra cada ítem con su disponibilidad ('En Stock' / 'Sin Stock').
    """
    __tablename__ = "warehouse_request_items"

    id                   = Column(Integer, primary_key=True, index=True)
    request_id           = Column(Integer, ForeignKey("warehouse_requests.id"), nullable=False)
    inventory_item_id    = Column(Integer, ForeignKey("inventory_items.id"), nullable=False)
    quantity_requested   = Column(Numeric(10, 2), nullable=False)
    availability_status  = Column(String(20), default="En Stock")  # "En Stock" / "Sin Stock"

    request        = relationship("WarehouseRequest", back_populates="items")
    inventory_item = relationship("InventoryItem")


# ═══════════════════════════════════════════════════════════════════
# 7. PLANTA — UNIDADES DE PROCESO
# ═══════════════════════════════════════════════════════════════════

class ProcessUnit(Base):
    """Nodo del diagrama de flujo de planta en tiempo real.
    Bloques: Trituradoras (PR-01), Molinos (ML-03), Celdas Flotación (CF-08).
    """
    __tablename__ = "process_units"

    id           = Column(Integer, primary_key=True, index=True)
    code         = Column(String(20), unique=True, nullable=False)  # "PR-01"
    name         = Column(String(100), nullable=False)              # "Trituradoras"
    unit_type    = Column(Enum(ProcessUnitType), nullable=False)
    status       = Column(Enum(ProcessUnitStatus), nullable=False,
                          default=ProcessUnitStatus.OPERANDO)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=True)

    equipment    = relationship("Equipment")


# ═══════════════════════════════════════════════════════════════════
# 8. LABORATORIO — MUESTRAS Y ENSAYES
# ═══════════════════════════════════════════════════════════════════

class LabSample(Base):
    """Muestra de laboratorio.
    Cola de trabajo: ID, Origen/Punto de Toma, Hora de Toma, Estado.
    Tabla de ensayes: ID Ensaye, Origen Muestra, Fecha/Hora, Status.
    """
    __tablename__ = "lab_samples"

    id             = Column(Integer, primary_key=True, index=True)
    sample_code    = Column(String(20), unique=True, nullable=False, index=True)  # "LAB-9402" / "M-204"
    origin         = Column(String(200), nullable=False)   # "Concentrado Final", "Tajo Abierto - Nivel 4"
    sampling_time  = Column(DateTime(timezone=True), nullable=False)
    status         = Column(Enum(LabSampleStatus), nullable=False,
                            default=LabSampleStatus.PENDIENTE)
    priority       = Column(String(20), default="Normal")  # "Alta", "Normal"
    hash_registro  = Column(String(30))                    # "B6-88-FF-21-44" (trazabilidad)
    registered_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    registered_by  = relationship("User")
    assay_result   = relationship("AssayResult", back_populates="sample", uselist=False)


class AssayResult(Base):
    """Resultados del ensaye químico de una muestra.
    Campos del formulario: Au g/t, Ag g/t, Cu %, Zn %, Humedad %, Notas.
    """
    __tablename__ = "assay_results"

    id              = Column(Integer, primary_key=True, index=True)
    sample_id       = Column(Integer, ForeignKey("lab_samples.id"), unique=True, nullable=False)
    au_g_t          = Column(Numeric(10, 3))    # Ley de Oro g/t  — 14.5
    ag_g_t          = Column(Numeric(10, 3))    # Ley de Plata g/t — 280.2
    cu_pct          = Column(Numeric(6, 3))     # Cobre %
    zn_pct          = Column(Numeric(6, 3))     # Zinc %
    humidity_pct    = Column(Numeric(6, 2))     # Humedad %       — 8.2
    notes           = Column(Text)              # Observaciones de laboratorio
    analyst_id      = Column(Integer, ForeignKey("users.id"), nullable=True)
    certified_at    = Column(DateTime(timezone=True), nullable=True)
    repeat_requested= Column(Boolean, default=False)

    sample   = relationship("LabSample", back_populates="assay_result")
    analyst  = relationship("User", back_populates="assay_results")


# ═══════════════════════════════════════════════════════════════════
# 9. OPERACIÓN MINA — VOLADURAS Y AVANCE
# ═══════════════════════════════════════════════════════════════════

class BlastingRecord(Base):
    """Registro de voladuras / detonaciones.
    Formulario 'Captura de Voladuras' y tabla 'Historial de Avance Diario'.
    Campos: Nivel/Zona, Metros Avanzados, Explosivo Usado (kg), Notas.
    """
    __tablename__ = "blasting_records"

    id              = Column(Integer, primary_key=True, index=True)
    blast_code      = Column(String(30), index=True)           # "LOTE-450-A2"
    location        = Column(String(150), nullable=False)      # "Nivel 450 - Veta Sur"
    advance_meters  = Column(Numeric(8, 2), nullable=False)    # 3.2
    explosive_kg    = Column(Numeric(10, 2), nullable=False)   # 150.0
    status          = Column(Enum(BlastingStatus), nullable=False,
                             default=BlastingStatus.EXITOSA)
    supervisor_id   = Column(Integer, ForeignKey("users.id"), nullable=True)
    supervisor_notes= Column(Text)
    blasted_at      = Column(DateTime(timezone=True), server_default=func.now())

    supervisor = relationship("User")


class OreYardLot(Base):
    """Lotes del Patio de Mineral en superficie.
    Tarjetas del widget 'Patio de Mineral': Lote #, Tipo, Toneladas.
    """
    __tablename__ = "ore_yard_lots"

    id           = Column(Integer, primary_key=True, index=True)
    lot_code     = Column(String(30), unique=True, nullable=False, index=True)  # "Lote #103"
    ore_type     = Column(Enum(OreType), nullable=False)
    tons         = Column(Numeric(12, 2), nullable=False)   # 1200
    status       = Column(String(30), default="En Patio")   # "En Patio", "Enviado Trituración"
    sent_to_plant_at = Column(DateTime(timezone=True), nullable=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())


# ═══════════════════════════════════════════════════════════════════
# 10. CASETA DE CONTROL — VIAJES DE CAMIONES
# ═══════════════════════════════════════════════════════════════════

class TruckTrip(Base):
    """Cada viaje registrado en la caseta de control.
    Tabla 'Historial Reciente': Unidad ID, Destino, Peso, Hora.
    El operador selecciona camión + destino + peso en báscula.
    """
    __tablename__ = "truck_trips"

    id               = Column(Integer, primary_key=True, index=True)
    trip_code        = Column(String(20), index=True)             # "V-1024"
    truck_id         = Column(Integer, ForeignKey("equipment.id"), nullable=False)
    truck_unit_code  = Column(String(20))                         # "CAT-104", "KOM-215"
    weight_tons      = Column(Numeric(10, 2), nullable=False)     # 42.5
    destination_type = Column(Enum(DestinationType), nullable=False)
    destination_name = Column(String(150))                        # "Puerto Norte"
    dispatch_status  = Column(Enum(DispatchStatus),
                               default=DispatchStatus.EN_PLANTA)
    control_booth    = Column(String(50))                         # "Nivel 450"
    registered_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    trip_time        = Column(DateTime(timezone=True), server_default=func.now())
    plates           = Column(String(20))                         # "ABC-123"

    truck          = relationship("Equipment", back_populates="truck_trips")
    registered_by  = relationship("User")


# ═══════════════════════════════════════════════════════════════════
# 11. RH — EMPLEADOS Y ASISTENCIA
# ═══════════════════════════════════════════════════════════════════

class Employee(Base):
    """Empleado registrado en el sistema.
    Tabla 'Control de Asistencia': Nombre, Puesto, Hora Entrada, Estado.
    """
    __tablename__ = "employees"

    id            = Column(Integer, primary_key=True, index=True)
    full_name     = Column(String(120), nullable=False)   # "Juan Pérez"
    initials      = Column(String(5))                     # "JP"
    position      = Column(String(80), nullable=False)    # "Perforista"
    department    = Column(String(80))                    # "Mina", "Mecánica"
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=True)

    attendance_records = relationship("AttendanceRecord", back_populates="employee")


class AttendanceRecord(Base):
    """Registro de asistencia por turno.
    Columnas de la tabla: Nombre, Puesto, Hora Entrada, Estado (Presente/Ausente).
    """
    __tablename__ = "attendance_records"

    id             = Column(Integer, primary_key=True, index=True)
    employee_id    = Column(Integer, ForeignKey("employees.id"), nullable=False)
    shift_date     = Column(Date, nullable=False)
    shift_number   = Column(Integer, default=1)           # 1 / 2 / 3
    check_in_time  = Column(String(10))                   # "06:55 AM"
    status         = Column(Enum(AttendanceStatus), nullable=False)

    employee = relationship("Employee", back_populates="attendance_records")


# ═══════════════════════════════════════════════════════════════════
# 12. SEGURIDAD — INCIDENTES Y KPIs
# ═══════════════════════════════════════════════════════════════════

class IncidentReport(Base):
    """Reporte de incidentes registrados desde el módulo de Seguridad/RH.
    Formulario: Tipo, Área, Descripción breve → notifica a Seguridad Industrial.
    """
    __tablename__ = "incident_reports"

    id             = Column(Integer, primary_key=True, index=True)
    incident_type  = Column(Enum(IncidentSeverity), nullable=False)
    area           = Column(String(80), nullable=False)   # "Mina", "Planta"
    description    = Column(Text, nullable=False)
    reporter_id    = Column(Integer, ForeignKey("users.id"), nullable=True)
    involved_employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    reported_at    = Column(DateTime(timezone=True), server_default=func.now())
    is_resolved    = Column(Boolean, default=False)

    reporter           = relationship("User")
    involved_employee  = relationship("Employee")


# ═══════════════════════════════════════════════════════════════════
# 13. LOGÍSTICA Y FINANZAS
# ═══════════════════════════════════════════════════════════════════

class FinancialRecord(Base):
    """Resumen financiero mensual.
    KPIs 'Ingresos del Mes' y 'Costos Operativos'.
    Sincronizado con Odoo (indicado en UI).
    """
    __tablename__ = "financial_records"

    id                   = Column(Integer, primary_key=True, index=True)
    record_month         = Column(Date, nullable=False, index=True)  # Primer día del mes
    revenue_usd          = Column(Numeric(14, 2))    # 142500.00
    operational_costs_usd= Column(Numeric(14, 2))   # 68230.45
    costs_vs_prev_month_pct = Column(Float)          # +4.2%
    synced_with_odoo     = Column(Boolean, default=False)
    updated_at           = Column(DateTime(timezone=True), server_default=func.now())


class Invoice(Base):
    """Factura reciente — tabla 'Facturación Reciente'.
    Columnas: Número de factura, Cliente, Monto, Estado de sincronización Odoo.
    """
    __tablename__ = "invoices"

    id              = Column(Integer, primary_key=True, index=True)
    invoice_number  = Column(String(30), unique=True, nullable=False)  # "F-2023-089"
    client_name     = Column(String(150), nullable=False)              # "Minera del Norte S.A."
    amount_usd      = Column(Numeric(14, 2), nullable=False)
    sync_status     = Column(String(30), default="Pendiente")          # "Sincronizado" / "Pendiente"
    odoo_record_id  = Column(String(50), nullable=True)
    issued_at       = Column(DateTime(timezone=True), server_default=func.now())
    trip_id         = Column(Integer, ForeignKey("truck_trips.id"), nullable=True)

    trip = relationship("TruckTrip")
