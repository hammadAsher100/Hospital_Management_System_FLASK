-- ============================================================
-- MediCore HMS - Add Missing Stored Procedures
-- Run this ONCE against HMS_DB to fix signup and other features
-- ============================================================

USE HMS_DB;
GO

-- ── Patient Stored Procedures ────────────────────────────────

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

-- ── Doctor Lookup Stored Procedures ──────────────────────────

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

-- ── Medicine Stored Procedures ───────────────────────────────

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

-- ── Admission Stored Procedures ──────────────────────────────

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

-- ── Prescription Stored Procedures ───────────────────────────

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

PRINT 'All missing stored procedures created successfully!';
GO
