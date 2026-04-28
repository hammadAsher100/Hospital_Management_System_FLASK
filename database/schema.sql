-- ============================================================
-- MediCore HMS - Database Schema for SQL Server (SSMS)
-- Database: HMS_DB
-- Run this file first, then seed.sql
-- ============================================================

USE master;
GO

IF DB_ID('HMS_DB') IS NOT NULL
    DROP DATABASE HMS_DB;
GO

CREATE DATABASE HMS_DB;
GO

USE HMS_DB;
GO

-- ── Users ─────────────────────────────────────────────────────
CREATE TABLE Users (
    user_id       INT IDENTITY(1,1) PRIMARY KEY,
    username      NVARCHAR(50)  NOT NULL UNIQUE,
    password_hash NVARCHAR(255) NOT NULL,
    role          NVARCHAR(20)  NOT NULL CHECK (role IN ('admin', 'doctor', 'nurse', 'billing', 'patient')),
    email         NVARCHAR(100) NOT NULL UNIQUE,
    full_name     NVARCHAR(100) NOT NULL,
    created_at    DATETIME      DEFAULT GETDATE(),
    last_login    DATETIME      NULL,
    is_active     BIT           DEFAULT 1
);

CREATE INDEX IX_Users_role     ON Users (role);
GO

-- ── Patients ──────────────────────────────────────────────────
CREATE TABLE Patients (
    patient_id        INT IDENTITY(1,1) PRIMARY KEY,
    user_id           INT            NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    first_name        NVARCHAR(50)  NOT NULL,
    last_name         NVARCHAR(50)  NOT NULL,
    dob               DATE          NOT NULL,
    gender            NVARCHAR(10)  NOT NULL CHECK (gender IN ('Male', 'Female', 'Other')),
    phone             NVARCHAR(20)  NOT NULL,
    email             NVARCHAR(100) NULL,
    address           NVARCHAR(MAX) NULL,
    emergency_contact NVARCHAR(100) NULL,
    blood_group       NVARCHAR(5)   NULL CHECK (blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-') OR blood_group IS NULL),
    allergies         NVARCHAR(MAX) NULL,
    registration_date DATETIME      DEFAULT GETDATE()
);

CREATE INDEX IX_Patients_name  ON Patients (last_name, first_name);
CREATE INDEX IX_Patients_phone ON Patients (phone);
CREATE UNIQUE INDEX UQ_Patients_user_id_nonnull ON Patients (user_id) WHERE user_id IS NOT NULL;
GO

-- ── Doctors ───────────────────────────────────────────────────
CREATE TABLE Doctors (
    doctor_id           INT IDENTITY(1,1) PRIMARY KEY,
    user_id             INT            NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    first_name          NVARCHAR(50)   NOT NULL,
    last_name           NVARCHAR(50)   NOT NULL,
    specialization      NVARCHAR(100)  NOT NULL,
    phone               NVARCHAR(20)   NULL,
    email               NVARCHAR(100)  NULL,
    consultation_fee    DECIMAL(10, 2) DEFAULT 0,
    availability_status BIT            DEFAULT 1
);

CREATE INDEX IX_Doctors_user_id ON Doctors (user_id);
GO

-- ── Nurses ────────────────────────────────────────────────────
CREATE TABLE Nurses (
    nurse_id      INT IDENTITY(1,1) PRIMARY KEY,
    user_id       INT          NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    first_name    NVARCHAR(50) NOT NULL,
    last_name     NVARCHAR(50) NOT NULL,
    phone         NVARCHAR(20) NULL,
    email         NVARCHAR(100) NULL,
    assigned_ward NVARCHAR(50) NULL
);

CREATE INDEX IX_Nurses_user_id ON Nurses (user_id);
GO

-- ── Doctor Schedules ──────────────────────────────────────────
CREATE TABLE Doctor_Schedules (
    schedule_id      INT IDENTITY(1,1) PRIMARY KEY,
    doctor_id        INT      NOT NULL REFERENCES Doctors(doctor_id) ON DELETE CASCADE,
    day_of_week      TINYINT  NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    start_time       TIME     NOT NULL,
    end_time         TIME     NOT NULL,
    max_appointments INT      DEFAULT 10,
    CONSTRAINT UQ_DoctorDay UNIQUE (doctor_id, day_of_week)
);
GO

-- ── Appointments ──────────────────────────────────────────────
CREATE TABLE Appointments (
    appointment_id   INT IDENTITY(1,1) PRIMARY KEY,
    patient_id       INT          NOT NULL REFERENCES Patients(patient_id) ON DELETE CASCADE,
    doctor_id        INT          NOT NULL REFERENCES Doctors(doctor_id),
    appointment_date DATE         NOT NULL,
    appointment_time TIME         NOT NULL,
    status           NVARCHAR(20) NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'completed', 'cancelled')),
    reason           NVARCHAR(MAX) NULL,
    notes            NVARCHAR(MAX) NULL,
    created_at       DATETIME     DEFAULT GETDATE(),
    CONSTRAINT UQ_DoctorSlot UNIQUE (doctor_id, appointment_date, appointment_time)
);

CREATE INDEX IX_Appt_patient  ON Appointments (patient_id);
CREATE INDEX IX_Appt_doctor   ON Appointments (doctor_id);
CREATE INDEX IX_Appt_date     ON Appointments (appointment_date);
CREATE INDEX IX_Appt_status   ON Appointments (status);
GO

-- ── Admissions ────────────────────────────────────────────────
CREATE TABLE Admissions (
    admission_id   INT IDENTITY(1,1) PRIMARY KEY,
    patient_id     INT          NOT NULL REFERENCES Patients(patient_id) ON DELETE CASCADE,
    doctor_id      INT          NOT NULL REFERENCES Doctors(doctor_id),
    nurse_id       INT          NULL REFERENCES Nurses(nurse_id) ON DELETE NO ACTION,
    admission_date DATETIME     DEFAULT GETDATE(),
    discharge_date DATETIME     NULL,
    room_number    NVARCHAR(20) NULL,
    diagnosis      NVARCHAR(MAX) NULL
);

CREATE INDEX IX_Admissions_patient ON Admissions (patient_id);
GO

-- ── Billing ───────────────────────────────────────────────────
CREATE TABLE Billing (
    bill_id        INT IDENTITY(1,1) PRIMARY KEY,
    patient_id     INT           NOT NULL REFERENCES Patients(patient_id) ON DELETE CASCADE,
    appointment_id INT           NULL REFERENCES Appointments(appointment_id) ON DELETE NO ACTION,
    admission_id   INT           NULL REFERENCES Admissions(admission_id) ON DELETE NO ACTION,
    bill_date      DATETIME      DEFAULT GETDATE(),
    total_amount   DECIMAL(12,2) DEFAULT 0,
    paid_amount    DECIMAL(12,2) DEFAULT 0,
    status         NVARCHAR(20)  NOT NULL DEFAULT 'pending' CHECK (status IN ('paid', 'pending', 'partial')),
    payment_method NVARCHAR(50)  NULL
);

CREATE INDEX IX_Billing_patient ON Billing (patient_id);
CREATE INDEX IX_Billing_status  ON Billing (status);
CREATE INDEX IX_Billing_date    ON Billing (bill_date);
GO

-- ── Bill Items ────────────────────────────────────────────────
CREATE TABLE Bill_Items (
    item_id     INT IDENTITY(1,1) PRIMARY KEY,
    bill_id     INT           NOT NULL REFERENCES Billing(bill_id) ON DELETE CASCADE,
    description NVARCHAR(255) NOT NULL,
    quantity    INT           DEFAULT 1,
    unit_price  DECIMAL(10,2) NOT NULL,
    total_price DECIMAL(10,2) NOT NULL
);

CREATE INDEX IX_BillItems_bill ON Bill_Items (bill_id);
GO

-- ── Medicines ─────────────────────────────────────────────────
CREATE TABLE Medicines (
    medicine_id    INT IDENTITY(1,1) PRIMARY KEY,
    name           NVARCHAR(100)  NOT NULL,
    category       NVARCHAR(50)   NULL,
    manufacturer   NVARCHAR(100)  NULL,
    unit_price     DECIMAL(10, 2) NOT NULL,
    stock_quantity INT            DEFAULT 0,
    reorder_level  INT            DEFAULT 10,
    expiry_date    DATE           NULL
);

CREATE INDEX IX_Medicines_name     ON Medicines (name);
CREATE INDEX IX_Medicines_category ON Medicines (category);
GO

-- ── Prescriptions ─────────────────────────────────────────────
CREATE TABLE Prescriptions (
    prescription_id INT IDENTITY(1,1) PRIMARY KEY,
    patient_id      INT      NOT NULL REFERENCES Patients(patient_id) ON DELETE CASCADE,
    doctor_id       INT      NOT NULL REFERENCES Doctors(doctor_id),
    appointment_id  INT      NULL REFERENCES Appointments(appointment_id) ON DELETE NO ACTION,
    prescribed_date DATETIME DEFAULT GETDATE(),
    notes           NVARCHAR(MAX) NULL,
    is_dispensed    BIT      DEFAULT 0
);

CREATE INDEX IX_Prescriptions_patient ON Prescriptions (patient_id);
CREATE INDEX IX_Prescriptions_doctor  ON Prescriptions (doctor_id);
GO

-- ── Prescription Items ────────────────────────────────────────
CREATE TABLE Prescription_Items (
    pres_item_id    INT IDENTITY(1,1) PRIMARY KEY,
    prescription_id INT          NOT NULL REFERENCES Prescriptions(prescription_id) ON DELETE CASCADE,
    medicine_id     INT          NOT NULL REFERENCES Medicines(medicine_id),
    dosage          NVARCHAR(50) NULL,
    frequency       NVARCHAR(50) NULL,
    duration        NVARCHAR(50) NULL,
    quantity        INT          DEFAULT 1
);

CREATE INDEX IX_PrescItems_pres ON Prescription_Items (prescription_id);
GO

PRINT 'Schema created successfully. Run seed.sql next.';
GO
