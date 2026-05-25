-- ============================================================
-- MediCore HMS - PostgreSQL Schema
-- Converted from T-SQL (SQL Server) to PostgreSQL
-- Run this file first, then seed_postgres.sql
-- ============================================================

-- ── Users ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    user_id       SERIAL PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20)  NOT NULL CHECK (role IN ('admin', 'doctor', 'nurse', 'billing', 'patient')),
    email         VARCHAR(100) NOT NULL UNIQUE,
    full_name     VARCHAR(100) NOT NULL,
    created_at    TIMESTAMP    DEFAULT NOW(),
    last_login    TIMESTAMP    NULL,
    is_active     BOOLEAN      DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS ix_users_role ON users (role);

-- ── Patients ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS patients (
    patient_id        SERIAL PRIMARY KEY,
    user_id           INT            NULL REFERENCES users(user_id) ON DELETE CASCADE,
    first_name        VARCHAR(50)   NOT NULL,
    last_name         VARCHAR(50)   NOT NULL,
    dob               DATE          NOT NULL,
    gender            VARCHAR(10)   NOT NULL CHECK (gender IN ('Male', 'Female', 'Other')),
    phone             VARCHAR(20)   NOT NULL,
    email             VARCHAR(100)  NULL,
    address           TEXT          NULL,
    emergency_contact VARCHAR(100)  NULL,
    blood_group       VARCHAR(5)    NULL CHECK (blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-') OR blood_group IS NULL),
    allergies         TEXT          NULL,
    registration_date TIMESTAMP     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_patients_name  ON patients (last_name, first_name);
CREATE INDEX IF NOT EXISTS ix_patients_phone ON patients (phone);
CREATE UNIQUE INDEX IF NOT EXISTS uq_patients_user_id_nonnull ON patients (user_id) WHERE user_id IS NOT NULL;

-- ── Doctors ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS doctors (
    doctor_id           SERIAL PRIMARY KEY,
    user_id             INT            NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    first_name          VARCHAR(50)    NOT NULL,
    last_name           VARCHAR(50)    NOT NULL,
    specialization      VARCHAR(100)   NOT NULL,
    phone               VARCHAR(20)    NULL,
    email               VARCHAR(100)   NULL,
    consultation_fee    NUMERIC(10, 2) DEFAULT 0,
    availability_status BOOLEAN        DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS ix_doctors_user_id ON doctors (user_id);

-- ── Nurses ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS nurses (
    nurse_id      SERIAL PRIMARY KEY,
    user_id       INT          NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    first_name    VARCHAR(50)  NOT NULL,
    last_name     VARCHAR(50)  NOT NULL,
    phone         VARCHAR(20)  NULL,
    email         VARCHAR(100) NULL,
    assigned_ward VARCHAR(50)  NULL
);

CREATE INDEX IF NOT EXISTS ix_nurses_user_id ON nurses (user_id);

-- ── Doctor Schedules ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS doctor_schedules (
    schedule_id      SERIAL PRIMARY KEY,
    doctor_id        INT     NOT NULL REFERENCES doctors(doctor_id) ON DELETE CASCADE,
    day_of_week      SMALLINT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    start_time       TIME    NOT NULL,
    end_time         TIME    NOT NULL,
    max_appointments INT     DEFAULT 10,
    CONSTRAINT uq_doctor_day UNIQUE (doctor_id, day_of_week)
);

-- ── Appointments ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS appointments (
    appointment_id   SERIAL PRIMARY KEY,
    patient_id       INT          NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    doctor_id        INT          NOT NULL REFERENCES doctors(doctor_id),
    appointment_date DATE         NOT NULL,
    appointment_time TIME         NOT NULL,
    status           VARCHAR(20)  NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'completed', 'cancelled')),
    reason           TEXT         NULL,
    notes            TEXT         NULL,
    created_at       TIMESTAMP    DEFAULT NOW(),
    CONSTRAINT uq_doctor_slot UNIQUE (doctor_id, appointment_date, appointment_time)
);

CREATE INDEX IF NOT EXISTS ix_appt_patient ON appointments (patient_id);
CREATE INDEX IF NOT EXISTS ix_appt_doctor  ON appointments (doctor_id);
CREATE INDEX IF NOT EXISTS ix_appt_date    ON appointments (appointment_date);
CREATE INDEX IF NOT EXISTS ix_appt_status  ON appointments (status);

-- ── Admissions ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS admissions (
    admission_id   SERIAL PRIMARY KEY,
    patient_id     INT          NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    doctor_id      INT          NOT NULL REFERENCES doctors(doctor_id),
    nurse_id       INT          NULL REFERENCES nurses(nurse_id) ON DELETE SET NULL,
    admission_date TIMESTAMP    DEFAULT NOW(),
    discharge_date TIMESTAMP    NULL,
    room_number    VARCHAR(20)  NULL,
    diagnosis      TEXT         NULL
);

CREATE INDEX IF NOT EXISTS ix_admissions_patient ON admissions (patient_id);

-- ── Billing ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS billing (
    bill_id        SERIAL PRIMARY KEY,
    patient_id     INT           NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    appointment_id INT           NULL REFERENCES appointments(appointment_id) ON DELETE SET NULL,
    admission_id   INT           NULL REFERENCES admissions(admission_id) ON DELETE SET NULL,
    bill_date      TIMESTAMP     DEFAULT NOW(),
    total_amount   NUMERIC(12,2) DEFAULT 0,
    paid_amount    NUMERIC(12,2) DEFAULT 0,
    status         VARCHAR(20)   NOT NULL DEFAULT 'pending' CHECK (status IN ('paid', 'pending', 'partial')),
    payment_method VARCHAR(50)   NULL
);

CREATE INDEX IF NOT EXISTS ix_billing_patient ON billing (patient_id);
CREATE INDEX IF NOT EXISTS ix_billing_status  ON billing (status);
CREATE INDEX IF NOT EXISTS ix_billing_date    ON billing (bill_date);

-- ── Bill Items ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bill_items (
    item_id     SERIAL PRIMARY KEY,
    bill_id     INT           NOT NULL REFERENCES billing(bill_id) ON DELETE CASCADE,
    description VARCHAR(255)  NOT NULL,
    quantity    INT           DEFAULT 1,
    unit_price  NUMERIC(10,2) NOT NULL,
    total_price NUMERIC(10,2) NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_bill_items_bill ON bill_items (bill_id);

-- ── Medicines ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS medicines (
    medicine_id    SERIAL PRIMARY KEY,
    name           VARCHAR(100)   NOT NULL,
    category       VARCHAR(50)    NULL,
    manufacturer   VARCHAR(100)   NULL,
    unit_price     NUMERIC(10, 2) NOT NULL,
    stock_quantity INT            DEFAULT 0,
    reorder_level  INT            DEFAULT 10,
    expiry_date    DATE           NULL
);

CREATE INDEX IF NOT EXISTS ix_medicines_name     ON medicines (name);
CREATE INDEX IF NOT EXISTS ix_medicines_category ON medicines (category);

-- ── Prescriptions ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prescriptions (
    prescription_id SERIAL PRIMARY KEY,
    patient_id      INT       NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    doctor_id       INT       NOT NULL REFERENCES doctors(doctor_id),
    appointment_id  INT       NULL REFERENCES appointments(appointment_id) ON DELETE SET NULL,
    prescribed_date TIMESTAMP DEFAULT NOW(),
    notes           TEXT      NULL,
    is_dispensed    BOOLEAN   DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS ix_prescriptions_patient ON prescriptions (patient_id);
CREATE INDEX IF NOT EXISTS ix_prescriptions_doctor  ON prescriptions (doctor_id);

-- ── Prescription Items ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prescription_items (
    pres_item_id    SERIAL PRIMARY KEY,
    prescription_id INT          NOT NULL REFERENCES prescriptions(prescription_id) ON DELETE CASCADE,
    medicine_id     INT          NOT NULL REFERENCES medicines(medicine_id),
    dosage          VARCHAR(50)  NULL,
    frequency       VARCHAR(50)  NULL,
    duration        VARCHAR(50)  NULL,
    quantity        INT          DEFAULT 1
);

CREATE INDEX IF NOT EXISTS ix_presc_items_pres ON prescription_items (prescription_id);

-- ── Audit Log ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    log_id      SERIAL PRIMARY KEY,
    table_name  VARCHAR(50)  NOT NULL,
    operation   VARCHAR(10)  NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    record_id   INT          NOT NULL,
    old_values  TEXT         NULL,
    new_values  TEXT         NULL,
    description TEXT         NULL,
    changed_by  VARCHAR(100) NULL DEFAULT CURRENT_USER,
    changed_at  TIMESTAMP    DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_audit_log_table_op  ON audit_log (table_name, operation);
CREATE INDEX IF NOT EXISTS ix_audit_log_changed_at ON audit_log (changed_at DESC);
