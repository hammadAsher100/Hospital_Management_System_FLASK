-- ============================================================
-- MediCore HMS - Patch: Add Missing Stored Procedures
-- Run this against your EXISTING HMS_DB database.
-- Fixes: consultation fee billing, prescription creation,
--        medicine CRUD, and admission operations.
-- ============================================================

USE HMS_DB;
GO

-- ── FIX 1: Update vw_AppointmentDetails to include consultation_fee ──
-- This is the root cause of consultation fee showing 0 in billing.
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
    d.specialization AS doctor_specialization,
    d.consultation_fee
FROM Appointments a
INNER JOIN Patients p ON p.patient_id = a.patient_id
INNER JOIN Doctors d ON d.doctor_id = a.doctor_id;
GO

-- ── FIX 2: usp_GetDoctorById (fallback for billing consultation fee) ──
IF OBJECT_ID('dbo.usp_GetDoctorById', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetDoctorById;
GO
CREATE PROCEDURE dbo.usp_GetDoctorById
    @doctor_id INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT d.*,
           CONCAT('Dr. ', d.first_name, ' ', d.last_name) AS full_name
    FROM Doctors d
    WHERE d.doctor_id = @doctor_id;
END
GO

-- ── FIX 3: Medicine CRUD Procedures ──

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
    SET name = @name, category = @category, manufacturer = @manufacturer,
        unit_price = @unit_price, reorder_level = @reorder_level, expiry_date = @expiry_date
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

-- ── FIX 4: Prescription Procedures (the main broken feature) ──

IF OBJECT_ID('dbo.usp_GetPrescriptionById', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetPrescriptionById;
GO
CREATE PROCEDURE dbo.usp_GetPrescriptionById
    @prescription_id INT
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
    INSERT INTO Prescriptions (patient_id, doctor_id, appointment_id, notes, is_dispensed)
    VALUES (@patient_id, @doctor_id, @appointment_id, @notes, 0);
    SELECT CAST(SCOPE_IDENTITY() AS INT) AS id;
END
GO

IF OBJECT_ID('dbo.usp_AddPrescriptionItem', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_AddPrescriptionItem;
GO
CREATE PROCEDURE dbo.usp_AddPrescriptionItem
    @prescription_id INT,
    @medicine_id INT,
    @dosage NVARCHAR(50) = NULL,
    @frequency NVARCHAR(50) = NULL,
    @duration NVARCHAR(50) = NULL,
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

-- ── FIX 5: Admission Procedures ──

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

PRINT 'All missing procedures patched successfully!';
GO
