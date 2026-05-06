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

-- ── Reporting Views ──────────────────────────────────────────────
IF OBJECT_ID('dbo.ufn_CalculateAge', 'FN') IS NOT NULL
    DROP FUNCTION dbo.ufn_CalculateAge;
GO
CREATE FUNCTION dbo.ufn_CalculateAge (@dob DATE)
RETURNS INT
AS
BEGIN
    RETURN DATEDIFF(YEAR, @dob, GETDATE())
           - CASE
                WHEN DATEADD(YEAR, DATEDIFF(YEAR, @dob, GETDATE()), @dob) > CAST(GETDATE() AS DATE) THEN 1
                ELSE 0
             END;
END
GO

IF OBJECT_ID('dbo.vw_ActiveDoctors', 'V') IS NOT NULL
    DROP VIEW dbo.vw_ActiveDoctors;
GO
CREATE VIEW dbo.vw_ActiveDoctors AS
SELECT
    d.doctor_id,
    d.first_name,
    d.last_name,
    CONCAT('Dr. ', d.first_name, ' ', d.last_name) AS full_name,
    d.specialization,
    d.consultation_fee
FROM Doctors d
INNER JOIN Users u ON u.user_id = d.user_id
WHERE u.is_active = 1
  AND (d.availability_status = 1 OR d.availability_status IS NULL);
GO

IF OBJECT_ID('dbo.vw_TodayAppointmentsDetailed', 'V') IS NOT NULL
    DROP VIEW dbo.vw_TodayAppointmentsDetailed;
GO
CREATE VIEW dbo.vw_TodayAppointmentsDetailed AS
SELECT
    a.appointment_id,
    a.patient_id,
    a.doctor_id,
    a.appointment_date,
    a.appointment_time,
    a.status,
    CONCAT(p.first_name, ' ', p.last_name) AS patient_name,
    CONCAT('Dr. ', d.first_name, ' ', d.last_name) AS doctor_name
FROM Appointments a
INNER JOIN Patients p ON p.patient_id = a.patient_id
INNER JOIN Doctors d ON d.doctor_id = a.doctor_id;
GO

IF OBJECT_ID('dbo.vw_RecentPatients', 'V') IS NOT NULL
    DROP VIEW dbo.vw_RecentPatients;
GO
CREATE VIEW dbo.vw_RecentPatients AS
SELECT
    patient_id,
    CONCAT(first_name, ' ', last_name) AS full_name,
    gender,
    phone,
    registration_date
FROM Patients;
GO

IF OBJECT_ID('dbo.vw_DailyRevenue', 'V') IS NOT NULL
    DROP VIEW dbo.vw_DailyRevenue;
GO
CREATE VIEW dbo.vw_DailyRevenue AS
SELECT
    CAST(bill_date AS DATE) AS bill_day,
    SUM(total_amount) AS total_amount,
    SUM(paid_amount) AS paid_amount
FROM Billing
GROUP BY CAST(bill_date AS DATE);
GO

IF OBJECT_ID('dbo.vw_AppointmentStatusSummary', 'V') IS NOT NULL
    DROP VIEW dbo.vw_AppointmentStatusSummary;
GO
CREATE VIEW dbo.vw_AppointmentStatusSummary AS
SELECT
    status,
    COUNT(*) AS appointment_count
FROM Appointments
GROUP BY status;
GO

IF OBJECT_ID('dbo.vw_AppointmentDoctorSummary', 'V') IS NOT NULL
    DROP VIEW dbo.vw_AppointmentDoctorSummary;
GO
CREATE VIEW dbo.vw_AppointmentDoctorSummary AS
SELECT
    d.first_name,
    d.last_name,
    COUNT(a.appointment_id) AS appointment_count
FROM Doctors d
INNER JOIN Appointments a ON a.doctor_id = d.doctor_id
GROUP BY d.doctor_id, d.first_name, d.last_name;
GO

IF OBJECT_ID('dbo.vw_MedicineCategorySummary', 'V') IS NOT NULL
    DROP VIEW dbo.vw_MedicineCategorySummary;
GO
CREATE VIEW dbo.vw_MedicineCategorySummary AS
SELECT
    ISNULL(category, 'Uncategorized') AS category,
    COUNT(*) AS medicine_count,
    SUM(stock_quantity) AS total_stock,
    SUM(unit_price * stock_quantity) AS total_value
FROM Medicines
GROUP BY ISNULL(category, 'Uncategorized');
GO

-- ── Stored Procedures ────────────────────────────────────────────
IF OBJECT_ID('dbo.usp_GetAdminDashboardMetrics', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetAdminDashboardMetrics;
GO
CREATE PROCEDURE dbo.usp_GetAdminDashboardMetrics
    @today DATE
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @month_start DATE = DATEFROMPARTS(YEAR(@today), MONTH(@today), 1);

    SELECT
        (SELECT COUNT(*) FROM Patients) AS total_patients,
        (SELECT COUNT(*) FROM Appointments WHERE appointment_date = @today) AS today_appointments,
        (SELECT COUNT(*) FROM Admissions WHERE discharge_date IS NULL) AS active_admissions,
        (SELECT COUNT(*) FROM Medicines WHERE stock_quantity <= reorder_level) AS low_stock_count,
        (SELECT ISNULL(SUM(paid_amount), 0) FROM Billing WHERE bill_date >= @month_start) AS monthly_revenue,
        (SELECT COUNT(*) FROM Billing WHERE status = 'pending') AS pending_bills_count;
END
GO

IF OBJECT_ID('dbo.usp_CheckAppointmentConflict', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_CheckAppointmentConflict;
GO
CREATE PROCEDURE dbo.usp_CheckAppointmentConflict
    @doctor_id INT,
    @appointment_date DATE,
    @appointment_time TIME,
    @exclude_id INT = NULL
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM Appointments
                WHERE doctor_id = @doctor_id
                  AND appointment_date = @appointment_date
                  AND appointment_time = @appointment_time
                  AND status = 'scheduled'
                  AND (@exclude_id IS NULL OR appointment_id <> @exclude_id)
            ) THEN CAST(1 AS BIT)
            ELSE CAST(0 AS BIT)
        END AS has_conflict;
END
GO

IF OBJECT_ID('dbo.usp_GetDoctorBookedSlots', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetDoctorBookedSlots;
GO
CREATE PROCEDURE dbo.usp_GetDoctorBookedSlots
    @doctor_id INT,
    @appointment_date DATE
AS
BEGIN
    SET NOCOUNT ON;

    SELECT appointment_time
    FROM Appointments
    WHERE doctor_id = @doctor_id
      AND appointment_date = @appointment_date
      AND status = 'scheduled';
END
GO

IF OBJECT_ID('dbo.usp_GetUserByUsername', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetUserByUsername;
GO
CREATE PROCEDURE dbo.usp_GetUserByUsername
    @username NVARCHAR(50)
AS
BEGIN
    SET NOCOUNT ON;

    SELECT user_id, username, password_hash, role, email, full_name, created_at, last_login, is_active
    FROM Users
    WHERE username = @username;
END
GO

IF OBJECT_ID('dbo.usp_GetUserById', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetUserById;
GO
CREATE PROCEDURE dbo.usp_GetUserById
    @user_id INT
AS
BEGIN
    SET NOCOUNT ON;

    SELECT user_id, username, password_hash, role, email, full_name, created_at, last_login, is_active
    FROM Users
    WHERE user_id = @user_id;
END
GO

IF OBJECT_ID('dbo.usp_CreateUser', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_CreateUser;
GO
CREATE PROCEDURE dbo.usp_CreateUser
    @username NVARCHAR(50),
    @password_hash NVARCHAR(255),
    @role NVARCHAR(20),
    @email NVARCHAR(100),
    @full_name NVARCHAR(100)
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO Users (username, password_hash, role, email, full_name, is_active)
    VALUES (@username, @password_hash, @role, @email, @full_name, 1);

    SELECT CAST(SCOPE_IDENTITY() AS INT) AS id;
END
GO

IF OBJECT_ID('dbo.usp_UpdateLastLogin', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_UpdateLastLogin;
GO
CREATE PROCEDURE dbo.usp_UpdateLastLogin
    @user_id INT
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE Users
    SET last_login = GETDATE()
    WHERE user_id = @user_id;

    SELECT CAST(1 AS BIT) AS success;
END
GO

IF OBJECT_ID('dbo.usp_UpdateUserProfile', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_UpdateUserProfile;
GO
CREATE PROCEDURE dbo.usp_UpdateUserProfile
    @user_id INT,
    @full_name NVARCHAR(100),
    @email NVARCHAR(100)
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE Users
    SET full_name = @full_name,
        email = @email
    WHERE user_id = @user_id;

    SELECT CAST(1 AS BIT) AS success;
END
GO

IF OBJECT_ID('dbo.usp_UpdateUserPasswordHash', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_UpdateUserPasswordHash;
GO
CREATE PROCEDURE dbo.usp_UpdateUserPasswordHash
    @user_id INT,
    @password_hash NVARCHAR(255)
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE Users
    SET password_hash = @password_hash
    WHERE user_id = @user_id;

    SELECT CAST(1 AS BIT) AS success;
END
GO

IF OBJECT_ID('dbo.vw_AppointmentDetails', 'V') IS NOT NULL
    DROP VIEW dbo.vw_AppointmentDetails;
GO
CREATE VIEW dbo.vw_AppointmentDetails AS
SELECT
    a.appointment_id,
    a.patient_id,
    a.doctor_id,
    a.appointment_date,
    a.appointment_time,
    a.status,
    a.reason,
    a.notes,
    a.created_at,
    p.first_name AS patient_first_name,
    p.last_name AS patient_last_name,
    CONCAT(p.first_name, ' ', p.last_name) AS patient_full_name,
    p.gender AS patient_gender,
    p.phone AS patient_phone,
    p.blood_group AS patient_blood_group,
    p.allergies AS patient_allergies,
    dbo.ufn_CalculateAge(p.dob) AS patient_age,
    d.first_name AS doctor_first_name,
    d.last_name AS doctor_last_name,
    CONCAT('Dr. ', d.first_name, ' ', d.last_name) AS doctor_full_name,
    d.specialization AS doctor_specialization
FROM Appointments a
INNER JOIN Patients p ON p.patient_id = a.patient_id
INNER JOIN Doctors d ON d.doctor_id = a.doctor_id;
GO

IF OBJECT_ID('dbo.usp_ListActiveDoctors', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_ListActiveDoctors;
GO
CREATE PROCEDURE dbo.usp_ListActiveDoctors
AS
BEGIN
    SET NOCOUNT ON;
    SELECT doctor_id, full_name, specialization, consultation_fee
    FROM dbo.vw_ActiveDoctors
    ORDER BY full_name;
END
GO

IF OBJECT_ID('dbo.usp_CountAppointments', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_CountAppointments;
GO
CREATE PROCEDURE dbo.usp_CountAppointments
    @status NVARCHAR(20) = NULL,
    @doctor_id INT = NULL,
    @patient_id INT = NULL,
    @appointment_date DATE = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SELECT COUNT(*) AS total_count
    FROM Appointments a
    WHERE (@status IS NULL OR a.status = @status)
      AND (@doctor_id IS NULL OR a.doctor_id = @doctor_id)
      AND (@patient_id IS NULL OR a.patient_id = @patient_id)
      AND (@appointment_date IS NULL OR a.appointment_date = @appointment_date);
END
GO

IF OBJECT_ID('dbo.usp_ListAppointments', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_ListAppointments;
GO
CREATE PROCEDURE dbo.usp_ListAppointments
    @status NVARCHAR(20) = NULL,
    @doctor_id INT = NULL,
    @patient_id INT = NULL,
    @appointment_date DATE = NULL,
    @skip INT = 0,
    @take INT = 50
AS
BEGIN
    SET NOCOUNT ON;
    SELECT *
    FROM dbo.vw_AppointmentDetails
    WHERE (@status IS NULL OR status = @status)
      AND (@doctor_id IS NULL OR doctor_id = @doctor_id)
      AND (@patient_id IS NULL OR patient_id = @patient_id)
      AND (@appointment_date IS NULL OR appointment_date = @appointment_date)
    ORDER BY appointment_date DESC, appointment_time DESC
    OFFSET @skip ROWS FETCH NEXT @take ROWS ONLY;
END
GO

IF OBJECT_ID('dbo.usp_GetAppointmentById', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetAppointmentById;
GO
CREATE PROCEDURE dbo.usp_GetAppointmentById
    @appointment_id INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT *
    FROM dbo.vw_AppointmentDetails
    WHERE appointment_id = @appointment_id;
END
GO

IF OBJECT_ID('dbo.usp_CreateAppointment', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_CreateAppointment;
GO
CREATE PROCEDURE dbo.usp_CreateAppointment
    @patient_id INT,
    @doctor_id INT,
    @appointment_date DATE,
    @appointment_time TIME,
    @reason NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO Appointments (patient_id, doctor_id, appointment_date, appointment_time, status, reason)
    VALUES (@patient_id, @doctor_id, @appointment_date, @appointment_time, 'scheduled', @reason);
    SELECT CAST(SCOPE_IDENTITY() AS INT) AS id;
END
GO

IF OBJECT_ID('dbo.usp_UpdateAppointmentStatus', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_UpdateAppointmentStatus;
GO
CREATE PROCEDURE dbo.usp_UpdateAppointmentStatus
    @appointment_id INT,
    @status NVARCHAR(20),
    @notes NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE Appointments
    SET status = @status,
        notes = CASE WHEN @notes IS NULL THEN notes ELSE @notes END
    WHERE appointment_id = @appointment_id;
    SELECT CAST(1 AS BIT) AS success;
END
GO

IF OBJECT_ID('dbo.usp_RescheduleAppointment', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_RescheduleAppointment;
GO
CREATE PROCEDURE dbo.usp_RescheduleAppointment
    @appointment_id INT,
    @new_date DATE,
    @new_time TIME
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE Appointments
    SET appointment_date = @new_date,
        appointment_time = @new_time
    WHERE appointment_id = @appointment_id;
    SELECT CAST(1 AS BIT) AS success;
END
GO

IF OBJECT_ID('dbo.usp_GetDoctorScheduleByDay', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetDoctorScheduleByDay;
GO
CREATE PROCEDURE dbo.usp_GetDoctorScheduleByDay
    @doctor_id INT,
    @day_of_week TINYINT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT schedule_id, doctor_id, day_of_week, start_time, end_time, max_appointments
    FROM Doctor_Schedules
    WHERE doctor_id = @doctor_id AND day_of_week = @day_of_week;
END
GO

IF OBJECT_ID('dbo.usp_ListPatients', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_ListPatients;
GO
CREATE PROCEDURE dbo.usp_ListPatients
    @skip INT = 0,
    @take INT = 100
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        patient_id,
        user_id,
        first_name,
        last_name,
        CONCAT(first_name, ' ', last_name) AS full_name,
        dob,
        gender,
        phone,
        email,
        address,
        emergency_contact,
        blood_group,
        allergies,
        registration_date
    FROM Patients
    ORDER BY last_name, first_name
    OFFSET @skip ROWS FETCH NEXT @take ROWS ONLY;
END
GO

IF OBJECT_ID('dbo.vw_BillDetails', 'V') IS NOT NULL
    DROP VIEW dbo.vw_BillDetails;
GO
CREATE VIEW dbo.vw_BillDetails AS
SELECT
    b.bill_id,
    b.patient_id,
    b.appointment_id,
    b.admission_id,
    b.bill_date,
    b.total_amount,
    b.paid_amount,
    b.status,
    b.payment_method,
    p.first_name AS patient_first_name,
    p.last_name AS patient_last_name,
    CONCAT(p.first_name, ' ', p.last_name) AS patient_full_name,
    p.phone AS patient_phone,
    p.email AS patient_email,
    p.address AS patient_address,
    p.blood_group AS patient_blood_group
FROM Billing b
INNER JOIN Patients p ON p.patient_id = b.patient_id;
GO

IF OBJECT_ID('dbo.usp_CountBills', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_CountBills;
GO
CREATE PROCEDURE dbo.usp_CountBills
    @patient_id INT = NULL,
    @status NVARCHAR(20) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SELECT COUNT(*) AS total_count
    FROM Billing
    WHERE (@patient_id IS NULL OR patient_id = @patient_id)
      AND (@status IS NULL OR status = @status);
END
GO

IF OBJECT_ID('dbo.usp_ListBills', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_ListBills;
GO
CREATE PROCEDURE dbo.usp_ListBills
    @patient_id INT = NULL,
    @status NVARCHAR(20) = NULL,
    @skip INT = 0,
    @take INT = 50
AS
BEGIN
    SET NOCOUNT ON;
    SELECT *
    FROM dbo.vw_BillDetails
    WHERE (@patient_id IS NULL OR patient_id = @patient_id)
      AND (@status IS NULL OR status = @status)
    ORDER BY bill_date DESC
    OFFSET @skip ROWS FETCH NEXT @take ROWS ONLY;
END
GO

IF OBJECT_ID('dbo.usp_GetBillById', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetBillById;
GO
CREATE PROCEDURE dbo.usp_GetBillById
    @bill_id INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT * FROM dbo.vw_BillDetails WHERE bill_id = @bill_id;
END
GO

IF OBJECT_ID('dbo.usp_GetBillByAppointmentId', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetBillByAppointmentId;
GO
CREATE PROCEDURE dbo.usp_GetBillByAppointmentId
    @appointment_id INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT * FROM dbo.vw_BillDetails WHERE appointment_id = @appointment_id;
END
GO

IF OBJECT_ID('dbo.usp_CreateBill', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_CreateBill;
GO
CREATE PROCEDURE dbo.usp_CreateBill
    @patient_id INT,
    @appointment_id INT = NULL,
    @admission_id INT = NULL,
    @payment_method NVARCHAR(50) = NULL,
    @total_amount DECIMAL(12,2) = 0
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO Billing (patient_id, appointment_id, admission_id, payment_method, total_amount, paid_amount, status)
    VALUES (@patient_id, @appointment_id, @admission_id, @payment_method, @total_amount, 0, 'pending');
    SELECT CAST(SCOPE_IDENTITY() AS INT) AS id;
END
GO

IF OBJECT_ID('dbo.usp_AddBillItem', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_AddBillItem;
GO
CREATE PROCEDURE dbo.usp_AddBillItem
    @bill_id INT,
    @description NVARCHAR(255),
    @quantity INT,
    @unit_price DECIMAL(10,2)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @total DECIMAL(10,2) = @quantity * @unit_price;
    INSERT INTO Bill_Items (bill_id, description, quantity, unit_price, total_price)
    VALUES (@bill_id, @description, @quantity, @unit_price, @total);
    SELECT CAST(SCOPE_IDENTITY() AS INT) AS id;
END
GO

IF OBJECT_ID('dbo.usp_ListBillItems', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_ListBillItems;
GO
CREATE PROCEDURE dbo.usp_ListBillItems
    @bill_id INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT item_id, bill_id, description, quantity, unit_price, total_price
    FROM Bill_Items
    WHERE bill_id = @bill_id
    ORDER BY item_id;
END
GO

IF OBJECT_ID('dbo.usp_RefreshBillTotals', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_RefreshBillTotals;
GO
CREATE PROCEDURE dbo.usp_RefreshBillTotals
    @bill_id INT
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @total DECIMAL(12,2) = ISNULL((SELECT SUM(total_price) FROM Bill_Items WHERE bill_id = @bill_id), 0);
    DECLARE @paid DECIMAL(12,2) = ISNULL((SELECT paid_amount FROM Billing WHERE bill_id = @bill_id), 0);
    DECLARE @status NVARCHAR(20) = CASE WHEN @paid >= @total THEN 'paid' WHEN @paid > 0 THEN 'partial' ELSE 'pending' END;
    UPDATE Billing SET total_amount = @total, status = @status WHERE bill_id = @bill_id;
    SELECT CAST(1 AS BIT) AS success;
END
GO

IF OBJECT_ID('dbo.usp_RecordPayment', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_RecordPayment;
GO
CREATE PROCEDURE dbo.usp_RecordPayment
    @bill_id INT,
    @payment_amount DECIMAL(12,2),
    @payment_method NVARCHAR(50)
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE Billing
    SET paid_amount = paid_amount + @payment_amount,
        payment_method = @payment_method
    WHERE bill_id = @bill_id;
    EXEC dbo.usp_RefreshBillTotals @bill_id=@bill_id;
END
GO

IF OBJECT_ID('dbo.usp_ListCompletedAppointments', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_ListCompletedAppointments;
GO
CREATE PROCEDURE dbo.usp_ListCompletedAppointments
    @patient_id INT = NULL,
    @skip INT = 0,
    @take INT = 100
AS
BEGIN
    SET NOCOUNT ON;
    SELECT *
    FROM dbo.vw_AppointmentDetails
    WHERE status = 'completed'
      AND (@patient_id IS NULL OR patient_id = @patient_id)
    ORDER BY appointment_date DESC, appointment_time DESC
    OFFSET @skip ROWS FETCH NEXT @take ROWS ONLY;
END
GO

IF OBJECT_ID('dbo.usp_CountMedicines', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_CountMedicines;
GO
CREATE PROCEDURE dbo.usp_CountMedicines
    @search NVARCHAR(100) = NULL,
    @category NVARCHAR(50) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SELECT COUNT(*) AS total_count
    FROM Medicines
    WHERE (@search IS NULL OR name LIKE '%' + @search + '%')
      AND (@category IS NULL OR category = @category);
END
GO

IF OBJECT_ID('dbo.usp_ListMedicines', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_ListMedicines;
GO
CREATE PROCEDURE dbo.usp_ListMedicines
    @search NVARCHAR(100) = NULL,
    @category NVARCHAR(50) = NULL,
    @skip INT = 0,
    @take INT = 50
AS
BEGIN
    SET NOCOUNT ON;
    SELECT medicine_id, name, category, manufacturer, unit_price, stock_quantity, reorder_level, expiry_date
    FROM Medicines
    WHERE (@search IS NULL OR name LIKE '%' + @search + '%')
      AND (@category IS NULL OR category = @category)
    ORDER BY name
    OFFSET @skip ROWS FETCH NEXT @take ROWS ONLY;
END
GO

IF OBJECT_ID('dbo.usp_ListMedicineCategories', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_ListMedicineCategories;
GO
CREATE PROCEDURE dbo.usp_ListMedicineCategories
AS
BEGIN
    SET NOCOUNT ON;
    SELECT DISTINCT category
    FROM Medicines
    WHERE category IS NOT NULL AND LTRIM(RTRIM(category)) <> ''
    ORDER BY category;
END
GO

IF OBJECT_ID('dbo.usp_CountPrescriptions', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_CountPrescriptions;
GO
CREATE PROCEDURE dbo.usp_CountPrescriptions
    @patient_id INT = NULL,
    @doctor_id INT = NULL,
    @is_dispensed BIT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SELECT COUNT(*) AS total_count
    FROM Prescriptions
    WHERE (@patient_id IS NULL OR patient_id = @patient_id)
      AND (@doctor_id IS NULL OR doctor_id = @doctor_id)
      AND (@is_dispensed IS NULL OR is_dispensed = @is_dispensed);
END
GO

IF OBJECT_ID('dbo.usp_ListPrescriptions', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_ListPrescriptions;
GO
CREATE PROCEDURE dbo.usp_ListPrescriptions
    @patient_id INT = NULL,
    @doctor_id INT = NULL,
    @is_dispensed BIT = NULL,
    @skip INT = 0,
    @take INT = 50
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        pr.prescription_id,
        pr.patient_id,
        pr.doctor_id,
        pr.appointment_id,
        pr.prescribed_date,
        pr.notes,
        pr.is_dispensed,
        CONCAT(p.first_name, ' ', p.last_name) AS patient_full_name,
        CONCAT('Dr. ', d.first_name, ' ', d.last_name) AS doctor_full_name
    FROM Prescriptions pr
    INNER JOIN Patients p ON p.patient_id = pr.patient_id
    INNER JOIN Doctors d ON d.doctor_id = pr.doctor_id
    WHERE (@patient_id IS NULL OR pr.patient_id = @patient_id)
      AND (@doctor_id IS NULL OR pr.doctor_id = @doctor_id)
      AND (@is_dispensed IS NULL OR pr.is_dispensed = @is_dispensed)
    ORDER BY pr.prescribed_date DESC
    OFFSET @skip ROWS FETCH NEXT @take ROWS ONLY;
END
GO

IF OBJECT_ID('dbo.usp_ListPrescriptionItems', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_ListPrescriptionItems;
GO
CREATE PROCEDURE dbo.usp_ListPrescriptionItems
    @prescription_id INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        pi.pres_item_id,
        pi.prescription_id,
        pi.medicine_id,
        m.name AS medicine_name,
        pi.dosage,
        pi.frequency,
        pi.duration,
        pi.quantity
    FROM Prescription_Items pi
    INNER JOIN Medicines m ON m.medicine_id = pi.medicine_id
    WHERE pi.prescription_id = @prescription_id
    ORDER BY pi.pres_item_id;
END
GO

IF OBJECT_ID('dbo.usp_ListDoctors', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_ListDoctors;
GO
CREATE PROCEDURE dbo.usp_ListDoctors
AS
BEGIN
    SET NOCOUNT ON;
    SELECT d.*, CONCAT('Dr. ', d.first_name, ' ', d.last_name) AS full_name,
           (SELECT COUNT(*) FROM Appointments a WHERE a.doctor_id = d.doctor_id) AS total_appointments
    FROM Doctors d
    ORDER BY d.specialization, d.last_name, d.first_name;
END
GO

IF OBJECT_ID('dbo.usp_CreateDoctorWithUser', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_CreateDoctorWithUser;
GO
CREATE PROCEDURE dbo.usp_CreateDoctorWithUser
    @username NVARCHAR(50), @password_hash NVARCHAR(255), @email NVARCHAR(100),
    @first_name NVARCHAR(50), @last_name NVARCHAR(50), @specialization NVARCHAR(100),
    @phone NVARCHAR(20) = NULL, @consultation_fee DECIMAL(10,2) = 0
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO Users (username, password_hash, role, email, full_name, is_active)
    VALUES (@username, @password_hash, 'doctor', @email, CONCAT(@first_name, ' ', @last_name), 1);
    DECLARE @user_id INT = CAST(SCOPE_IDENTITY() AS INT);
    INSERT INTO Doctors (user_id, first_name, last_name, specialization, phone, email, consultation_fee, availability_status)
    VALUES (@user_id, @first_name, @last_name, @specialization, @phone, @email, @consultation_fee, 1);
    SELECT CAST(SCOPE_IDENTITY() AS INT) AS id;
END
GO

IF OBJECT_ID('dbo.usp_ListNurses', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_ListNurses;
GO
CREATE PROCEDURE dbo.usp_ListNurses
AS
BEGIN
    SET NOCOUNT ON;
    SELECT n.*,
           CONCAT(n.first_name, ' ', n.last_name) AS full_name,
           (SELECT COUNT(*) FROM Admissions a WHERE a.nurse_id = n.nurse_id AND a.discharge_date IS NULL) AS active_admissions_count
    FROM Nurses n
    ORDER BY n.last_name, n.first_name;
END
GO

IF OBJECT_ID('dbo.usp_GetNurseByUserId', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetNurseByUserId;
GO
CREATE PROCEDURE dbo.usp_GetNurseByUserId
    @user_id INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT TOP 1 n.*, CONCAT(n.first_name, ' ', n.last_name) AS full_name
    FROM Nurses n
    WHERE n.user_id = @user_id;
END
GO

IF OBJECT_ID('dbo.usp_CreateNurseWithUser', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_CreateNurseWithUser;
GO
CREATE PROCEDURE dbo.usp_CreateNurseWithUser
    @username NVARCHAR(50), @password_hash NVARCHAR(255), @email NVARCHAR(100),
    @first_name NVARCHAR(50), @last_name NVARCHAR(50), @phone NVARCHAR(20) = NULL, @assigned_ward NVARCHAR(50) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO Users (username, password_hash, role, email, full_name, is_active)
    VALUES (@username, @password_hash, 'nurse', @email, CONCAT(@first_name, ' ', @last_name), 1);
    DECLARE @user_id INT = CAST(SCOPE_IDENTITY() AS INT);
    INSERT INTO Nurses (user_id, first_name, last_name, phone, email, assigned_ward)
    VALUES (@user_id, @first_name, @last_name, @phone, @email, @assigned_ward);
    SELECT CAST(SCOPE_IDENTITY() AS INT) AS id;
END
GO

IF OBJECT_ID('dbo.usp_ListUsers', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_ListUsers;
GO
CREATE PROCEDURE dbo.usp_ListUsers
AS
BEGIN
    SET NOCOUNT ON;
    SELECT user_id, username, role, email, full_name, last_login, is_active
    FROM Users
    ORDER BY role, full_name;
END
GO

IF OBJECT_ID('dbo.usp_ToggleUserActive', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_ToggleUserActive;
GO
CREATE PROCEDURE dbo.usp_ToggleUserActive
    @user_id INT
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE Users SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE user_id = @user_id;
    SELECT user_id, username, is_active FROM Users WHERE user_id = @user_id;
END
GO

IF OBJECT_ID('dbo.usp_ListDoctorSchedules', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_ListDoctorSchedules;
GO
CREATE PROCEDURE dbo.usp_ListDoctorSchedules
    @doctor_id INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT schedule_id, doctor_id, day_of_week, start_time, end_time, max_appointments
    FROM Doctor_Schedules
    WHERE doctor_id = @doctor_id;
END
GO

IF OBJECT_ID('dbo.usp_ClearDoctorSchedules', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_ClearDoctorSchedules;
GO
CREATE PROCEDURE dbo.usp_ClearDoctorSchedules
    @doctor_id INT
AS
BEGIN
    SET NOCOUNT ON;
    DELETE FROM Doctor_Schedules WHERE doctor_id = @doctor_id;
    SELECT CAST(1 AS BIT) AS success;
END
GO

IF OBJECT_ID('dbo.usp_AddDoctorSchedule', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_AddDoctorSchedule;
GO
CREATE PROCEDURE dbo.usp_AddDoctorSchedule
    @doctor_id INT, @day_of_week TINYINT, @start_time TIME, @end_time TIME, @max_appointments INT = 10
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO Doctor_Schedules (doctor_id, day_of_week, start_time, end_time, max_appointments)
    VALUES (@doctor_id, @day_of_week, @start_time, @end_time, @max_appointments);
    SELECT CAST(1 AS BIT) AS success;
END
GO

IF OBJECT_ID('dbo.usp_CountRecentUniquePatients', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_CountRecentUniquePatients;
GO
CREATE PROCEDURE dbo.usp_CountRecentUniquePatients
    @days INT = 30
AS
BEGIN
    SET NOCOUNT ON;
    SELECT COUNT(DISTINCT patient_id) AS total_count
    FROM Appointments
    WHERE appointment_date >= DATEADD(DAY, -@days, CAST(GETDATE() AS DATE));
END
GO

-- ── Admin Report Stored Procedures ──────────────────────────────

IF OBJECT_ID('dbo.usp_GetPatientCount', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetPatientCount;
GO
CREATE PROCEDURE dbo.usp_GetPatientCount
AS
BEGIN
    SET NOCOUNT ON;
    SELECT COUNT(*) AS total_count FROM Patients;
END
GO

IF OBJECT_ID('dbo.usp_GetPatientGenderSummary', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetPatientGenderSummary;
GO
CREATE PROCEDURE dbo.usp_GetPatientGenderSummary
AS
BEGIN
    SET NOCOUNT ON;
    SELECT ISNULL(gender, 'Unknown') AS gender, COUNT(*) AS patient_count
    FROM Patients
    GROUP BY gender;
END
GO

IF OBJECT_ID('dbo.usp_GetPatientBloodGroupSummary', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetPatientBloodGroupSummary;
GO
CREATE PROCEDURE dbo.usp_GetPatientBloodGroupSummary
AS
BEGIN
    SET NOCOUNT ON;
    SELECT ISNULL(blood_group, 'Unknown') AS blood_group, COUNT(*) AS patient_count
    FROM Patients
    GROUP BY blood_group;
END
GO

IF OBJECT_ID('dbo.usp_GetPatientMonthlyRegistrations', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetPatientMonthlyRegistrations;
GO
CREATE PROCEDURE dbo.usp_GetPatientMonthlyRegistrations
    @limit INT = 12
AS
BEGIN
    SET NOCOUNT ON;
    SELECT TOP (@limit)
        YEAR(registration_date) AS yr,
        MONTH(registration_date) AS mo,
        COUNT(*) AS cnt
    FROM Patients
    GROUP BY YEAR(registration_date), MONTH(registration_date)
    ORDER BY yr, mo;
END
GO

IF OBJECT_ID('dbo.usp_GetRevenueTrendDaily', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetRevenueTrendDaily;
GO
CREATE PROCEDURE dbo.usp_GetRevenueTrendDaily
    @start_date DATE
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        CAST(bill_date AS DATE) AS period,
        SUM(total_amount) AS total,
        SUM(paid_amount) AS paid
    FROM Billing
    WHERE CAST(bill_date AS DATE) >= @start_date
    GROUP BY CAST(bill_date AS DATE)
    ORDER BY CAST(bill_date AS DATE);
END
GO

IF OBJECT_ID('dbo.usp_GetRevenueTrendWeekly', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetRevenueTrendWeekly;
GO
CREATE PROCEDURE dbo.usp_GetRevenueTrendWeekly
    @start_date DATE
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        DATEPART(iso_week, bill_date) AS period,
        SUM(total_amount) AS total,
        SUM(paid_amount) AS paid
    FROM Billing
    WHERE bill_date >= @start_date
    GROUP BY DATEPART(iso_week, bill_date)
    ORDER BY DATEPART(iso_week, bill_date);
END
GO

IF OBJECT_ID('dbo.usp_GetRevenueTrendMonthly', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetRevenueTrendMonthly;
GO
CREATE PROCEDURE dbo.usp_GetRevenueTrendMonthly
    @limit INT = 12
AS
BEGIN
    SET NOCOUNT ON;
    SELECT TOP (@limit)
        YEAR(bill_date) AS yr,
        MONTH(bill_date) AS mo,
        SUM(total_amount) AS total,
        SUM(paid_amount) AS paid
    FROM Billing
    GROUP BY YEAR(bill_date), MONTH(bill_date)
    ORDER BY yr, mo;
END
GO

IF OBJECT_ID('dbo.usp_GetRevenueTotals', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetRevenueTotals;
GO
CREATE PROCEDURE dbo.usp_GetRevenueTotals
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        ISNULL(SUM(paid_amount), 0) AS total_revenue,
        ISNULL(SUM(CASE WHEN status <> 'paid' THEN total_amount - paid_amount ELSE 0 END), 0) AS total_pending
    FROM Billing;
END
GO

IF OBJECT_ID('dbo.usp_GetInventoryAll', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetInventoryAll;
GO
CREATE PROCEDURE dbo.usp_GetInventoryAll
AS
BEGIN
    SET NOCOUNT ON;
    SELECT medicine_id, name, category, manufacturer, unit_price, stock_quantity, reorder_level, expiry_date
    FROM Medicines
    ORDER BY stock_quantity;
END
GO

IF OBJECT_ID('dbo.usp_GetInventoryTotalValue', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetInventoryTotalValue;
GO
CREATE PROCEDURE dbo.usp_GetInventoryTotalValue
AS
BEGIN
    SET NOCOUNT ON;
    SELECT ISNULL(SUM(unit_price * stock_quantity), 0) AS total_value FROM Medicines;
END
GO

-- ── Missing Patient Stored Procedures ────────────────────────────

IF OBJECT_ID('dbo.usp_GetPatientById', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetPatientById;
GO
CREATE PROCEDURE dbo.usp_GetPatientById
    @patient_id INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        patient_id, user_id, first_name, last_name,
        CONCAT(first_name, ' ', last_name) AS full_name,
        dob, gender, phone, email, address,
        emergency_contact, blood_group, allergies, registration_date
    FROM Patients
    WHERE patient_id = @patient_id;
END
GO

IF OBJECT_ID('dbo.usp_GetPatientByUserId', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetPatientByUserId;
GO
CREATE PROCEDURE dbo.usp_GetPatientByUserId
    @user_id INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        patient_id, user_id, first_name, last_name,
        CONCAT(first_name, ' ', last_name) AS full_name,
        dob, gender, phone, email, address,
        emergency_contact, blood_group, allergies, registration_date
    FROM Patients
    WHERE user_id = @user_id;
END
GO

IF OBJECT_ID('dbo.usp_CreatePatient', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_CreatePatient;
GO
CREATE PROCEDURE dbo.usp_CreatePatient
    @user_id INT = NULL,
    @first_name NVARCHAR(50),
    @last_name NVARCHAR(50),
    @dob DATE,
    @gender NVARCHAR(10),
    @phone NVARCHAR(20),
    @email NVARCHAR(100) = NULL,
    @address NVARCHAR(MAX) = NULL,
    @emergency_contact NVARCHAR(100) = NULL,
    @blood_group NVARCHAR(5) = NULL,
    @allergies NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO Patients (user_id, first_name, last_name, dob, gender, phone, email, address, emergency_contact, blood_group, allergies)
    VALUES (@user_id, @first_name, @last_name, @dob, @gender, @phone, @email, @address, @emergency_contact, @blood_group, @allergies);
    SELECT CAST(SCOPE_IDENTITY() AS INT) AS id;
END
GO

IF OBJECT_ID('dbo.usp_UpdatePatient', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_UpdatePatient;
GO
CREATE PROCEDURE dbo.usp_UpdatePatient
    @patient_id INT,
    @first_name NVARCHAR(50),
    @last_name NVARCHAR(50),
    @phone NVARCHAR(20),
    @email NVARCHAR(100) = NULL,
    @address NVARCHAR(MAX) = NULL,
    @emergency_contact NVARCHAR(100) = NULL,
    @blood_group NVARCHAR(5) = NULL,
    @allergies NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE Patients
    SET first_name = @first_name,
        last_name = @last_name,
        phone = @phone,
        email = @email,
        address = @address,
        emergency_contact = @emergency_contact,
        blood_group = @blood_group,
        allergies = @allergies
    WHERE patient_id = @patient_id;
    SELECT CAST(1 AS BIT) AS success;
END
GO

-- ── Missing Doctor Lookup Stored Procedures ──────────────────────

IF OBJECT_ID('dbo.usp_GetDoctorById', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetDoctorById;
GO
CREATE PROCEDURE dbo.usp_GetDoctorById
    @doctor_id INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT d.*, CONCAT('Dr. ', d.first_name, ' ', d.last_name) AS full_name
    FROM Doctors d
    WHERE d.doctor_id = @doctor_id;
END
GO

IF OBJECT_ID('dbo.usp_GetDoctorByUserId', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetDoctorByUserId;
GO
CREATE PROCEDURE dbo.usp_GetDoctorByUserId
    @user_id INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT TOP 1 d.*, CONCAT('Dr. ', d.first_name, ' ', d.last_name) AS full_name
    FROM Doctors d
    WHERE d.user_id = @user_id;
END
GO

-- ── Missing Medicine Stored Procedures ───────────────────────────

IF OBJECT_ID('dbo.usp_GetMedicineById', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetMedicineById;
GO
CREATE PROCEDURE dbo.usp_GetMedicineById
    @medicine_id INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT medicine_id, name, category, manufacturer, unit_price, stock_quantity, reorder_level, expiry_date
    FROM Medicines
    WHERE medicine_id = @medicine_id;
END
GO

IF OBJECT_ID('dbo.usp_CreateMedicine', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_CreateMedicine;
GO
CREATE PROCEDURE dbo.usp_CreateMedicine
    @name NVARCHAR(100),
    @category NVARCHAR(50) = NULL,
    @manufacturer NVARCHAR(100) = NULL,
    @unit_price DECIMAL(10,2),
    @stock_quantity INT = 0,
    @reorder_level INT = 10,
    @expiry_date DATE = NULL
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO Medicines (name, category, manufacturer, unit_price, stock_quantity, reorder_level, expiry_date)
    VALUES (@name, @category, @manufacturer, @unit_price, @stock_quantity, @reorder_level, @expiry_date);
    SELECT CAST(SCOPE_IDENTITY() AS INT) AS id;
END
GO

IF OBJECT_ID('dbo.usp_UpdateMedicine', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_UpdateMedicine;
GO
CREATE PROCEDURE dbo.usp_UpdateMedicine
    @medicine_id INT,
    @name NVARCHAR(100),
    @category NVARCHAR(50) = NULL,
    @manufacturer NVARCHAR(100) = NULL,
    @unit_price DECIMAL(10,2),
    @reorder_level INT = 10,
    @expiry_date DATE = NULL
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE Medicines
    SET name = @name,
        category = @category,
        manufacturer = @manufacturer,
        unit_price = @unit_price,
        reorder_level = @reorder_level,
        expiry_date = @expiry_date
    WHERE medicine_id = @medicine_id;
    SELECT CAST(1 AS BIT) AS success;
END
GO

IF OBJECT_ID('dbo.usp_UpdateMedicineStock', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_UpdateMedicineStock;
GO
CREATE PROCEDURE dbo.usp_UpdateMedicineStock
    @medicine_id INT,
    @quantity INT
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE Medicines
    SET stock_quantity = stock_quantity + @quantity
    WHERE medicine_id = @medicine_id;
    SELECT CAST(1 AS BIT) AS success;
END
GO

IF OBJECT_ID('dbo.usp_GetLowStockMedicines', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetLowStockMedicines;
GO
CREATE PROCEDURE dbo.usp_GetLowStockMedicines
AS
BEGIN
    SET NOCOUNT ON;
    SELECT medicine_id, name, category, manufacturer, unit_price, stock_quantity, reorder_level, expiry_date
    FROM Medicines
    WHERE stock_quantity <= reorder_level
    ORDER BY stock_quantity;
END
GO

-- ── Missing Admission Stored Procedures ──────────────────────────

IF OBJECT_ID('dbo.usp_GetAdmissionById', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetAdmissionById;
GO
CREATE PROCEDURE dbo.usp_GetAdmissionById
    @admission_id INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT a.*,
           CONCAT(p.first_name, ' ', p.last_name) AS patient_full_name,
           CONCAT('Dr. ', d.first_name, ' ', d.last_name) AS doctor_full_name
    FROM Admissions a
    INNER JOIN Patients p ON p.patient_id = a.patient_id
    INNER JOIN Doctors d ON d.doctor_id = a.doctor_id
    WHERE a.admission_id = @admission_id;
END
GO

IF OBJECT_ID('dbo.usp_ListActiveAdmissions', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_ListActiveAdmissions;
GO
CREATE PROCEDURE dbo.usp_ListActiveAdmissions
    @skip INT = 0,
    @take INT = 50
AS
BEGIN
    SET NOCOUNT ON;
    SELECT a.*,
           CONCAT(p.first_name, ' ', p.last_name) AS patient_full_name,
           CONCAT('Dr. ', d.first_name, ' ', d.last_name) AS doctor_full_name
    FROM Admissions a
    INNER JOIN Patients p ON p.patient_id = a.patient_id
    INNER JOIN Doctors d ON d.doctor_id = a.doctor_id
    WHERE a.discharge_date IS NULL
    ORDER BY a.admission_date DESC
    OFFSET @skip ROWS FETCH NEXT @take ROWS ONLY;
END
GO

IF OBJECT_ID('dbo.usp_CreateAdmission', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_CreateAdmission;
GO
CREATE PROCEDURE dbo.usp_CreateAdmission
    @patient_id INT,
    @doctor_id INT,
    @nurse_id INT = NULL,
    @room_number NVARCHAR(20) = NULL,
    @diagnosis NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO Admissions (patient_id, doctor_id, nurse_id, room_number, diagnosis)
    VALUES (@patient_id, @doctor_id, @nurse_id, @room_number, @diagnosis);
    SELECT CAST(SCOPE_IDENTITY() AS INT) AS id;
END
GO

IF OBJECT_ID('dbo.usp_DischargePatient', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_DischargePatient;
GO
CREATE PROCEDURE dbo.usp_DischargePatient
    @admission_id INT
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE Admissions
    SET discharge_date = GETDATE()
    WHERE admission_id = @admission_id;
    SELECT CAST(1 AS BIT) AS success;
END
GO

-- ── Missing Prescription Stored Procedures ───────────────────────

IF OBJECT_ID('dbo.usp_GetPrescriptionById', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetPrescriptionById;
GO
CREATE PROCEDURE dbo.usp_GetPrescriptionById
    @prescription_id INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT pr.*,
           CONCAT(p.first_name, ' ', p.last_name) AS patient_full_name,
           CONCAT('Dr. ', d.first_name, ' ', d.last_name) AS doctor_full_name
    FROM Prescriptions pr
    INNER JOIN Patients p ON p.patient_id = pr.patient_id
    INNER JOIN Doctors d ON d.doctor_id = pr.doctor_id
    WHERE pr.prescription_id = @prescription_id;
END
GO

IF OBJECT_ID('dbo.usp_CreatePrescription', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_CreatePrescription;
GO
CREATE PROCEDURE dbo.usp_CreatePrescription
    @patient_id INT,
    @doctor_id INT,
    @appointment_id INT = NULL,
    @notes NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO Prescriptions (patient_id, doctor_id, appointment_id, notes)
    VALUES (@patient_id, @doctor_id, @appointment_id, @notes);
    SELECT CAST(SCOPE_IDENTITY() AS INT) AS id;
END
GO

IF OBJECT_ID('dbo.usp_AddPrescriptionItem', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_AddPrescriptionItem;
GO
CREATE PROCEDURE dbo.usp_AddPrescriptionItem
    @prescription_id INT,
    @medicine_id INT,
    @dosage NVARCHAR(50),
    @frequency NVARCHAR(50),
    @duration NVARCHAR(50),
    @quantity INT = 1
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO Prescription_Items (prescription_id, medicine_id, dosage, frequency, duration, quantity)
    VALUES (@prescription_id, @medicine_id, @dosage, @frequency, @duration, @quantity);
    SELECT CAST(SCOPE_IDENTITY() AS INT) AS id;
END
GO

IF OBJECT_ID('dbo.usp_MarkPrescriptionDispensed', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_MarkPrescriptionDispensed;
GO
CREATE PROCEDURE dbo.usp_MarkPrescriptionDispensed
    @prescription_id INT
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE Prescriptions
    SET is_dispensed = 1
    WHERE prescription_id = @prescription_id;
    SELECT CAST(1 AS BIT) AS success;
END
GO

PRINT 'Schema created successfully. Run seed.sql next.';
GO
