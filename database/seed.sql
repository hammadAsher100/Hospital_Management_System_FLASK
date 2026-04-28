-- ============================================================
-- MediCore HMS - Seed Data
-- Run AFTER schema.sql
-- NOTE: Password hashes below are bcrypt hashes for the credentials listed at the end of this file.
-- Generate fresh hashes using: python generate_hashes.py
-- ============================================================

USE HMS_DB;
GO

-- ── Users ─────────────────────────────────────────────────────
-- Distinct credentials are used for each seeded user (bcrypt hashed).
INSERT INTO Users (username, password_hash, role, email, full_name)
VALUES
('admin',      '$2b$12$rRzT/HlU8BFzTyQ1LW.Hrec8nZ3cWwqWYy4oVKgp6tgpYqrXQCNYW', 'admin',   'admin@medicore.com',    'System Administrator'),
('dr_ahmed',   '$2b$12$LVEGBSMccyDQ6oVpr7M0Yug.EH55njhqpa1.QTvLtWlsWz3ddQJxy', 'doctor',  'ahmed@medicore.com',    'Dr. Salman Ahmed'),
('dr_fatima',  '$2b$12$ByWjUwekDDcLasjC4cX5Nuofgok0kja4y7gS5QDmcLnd0ZnJ/wwo6', 'doctor',  'fatima@medicore.com',   'Dr. Fatima Malik'),
('dr_omar',    '$2b$12$3hO28iFGpj/yyBrGhP0iDekjEveXVBIrUniyuSPBmK3uqcvlx4uZO', 'doctor',  'omar@medicore.com',     'Dr. Omar Siddiqui'),
('nurse_sara', '$2b$12$tvOGyhOQMVT/hZhMLqU04ukUy/YUOKjpkko87Xupk8h3tVsbO3XtS', 'nurse',   'sara@medicore.com',     'Sara Hassan'),
('nurse_ali',  '$2b$12$HIjerITiApHDqhckD9BDEeRAFvVObFieifjVc2OqK9yVkWNAKjm0y', 'nurse',   'ali@medicore.com',      'Ali Raza'),
('billing1',   '$2b$12$ud1Upvj1Ynu1IX2PHkcaT.c5xrBxga7JDbICaPvokMjgeo1EnvwGK', 'billing', 'billing@medicore.com',  'Billing Staff'),
('pt_mkhan',   '$2b$12$NdgPSP1ztEt6Nghb1e.1VOvpPGNmmMUUu35zVCCQoqOmG7.SOWf5m', 'patient', 'mkhan@email.com',       'Muhammad Khan'),
('pt_ayesha',  '$2b$12$YqWkSXR.E8zARK2jQLJWu.XaJo1qOegODNtaNPe/gJlkcG5KB3ip6', 'patient', 'ayesha@email.com',      'Ayesha Siddiqui'),
('pt_zainab',  '$2b$12$g8YJdcoSZcwR7gfaTj/GIe4x.eIoWGMa12jUIoph0thOQnVt8HEZe', 'patient', 'zainab@email.com',      'Zainab Ahmed');
GO

-- ── Doctors ───────────────────────────────────────────────────
INSERT INTO Doctors (user_id, first_name, last_name, specialization, phone, email, consultation_fee, availability_status)
VALUES
(2, 'Salman',  'Ahmed',    'General Physician',   '0300-1234567', 'ahmed@medicore.com',  1500.00, 1),
(3, 'Fatima',  'Malik',    'Cardiologist',        '0301-2345678', 'fatima@medicore.com', 3000.00, 1),
(4, 'Omar',    'Siddiqui', 'Pediatrician',        '0302-3456789', 'omar@medicore.com',   2000.00, 1);
GO

-- ── Nurses ────────────────────────────────────────────────────
INSERT INTO Nurses (user_id, first_name, last_name, phone, email, assigned_ward)
VALUES
(5, 'Sara', 'Hassan', '0303-4567890', 'sara@medicore.com', 'General Ward'),
(6, 'Ali',  'Raza',   '0304-5678901', 'ali@medicore.com',  'ICU');
GO

-- ── Doctor Schedules ──────────────────────────────────────────
-- Dr. Salman: Mon-Fri 9-5
INSERT INTO Doctor_Schedules (doctor_id, day_of_week, start_time, end_time, max_appointments)
VALUES
(1, 0, '09:00', '17:00', 12),
(1, 1, '09:00', '17:00', 12),
(1, 2, '09:00', '17:00', 12),
(1, 3, '09:00', '17:00', 12),
(1, 4, '09:00', '17:00', 12);

-- Dr. Fatima: Mon, Wed, Fri 10-4
INSERT INTO Doctor_Schedules (doctor_id, day_of_week, start_time, end_time, max_appointments)
VALUES
(2, 0, '10:00', '16:00', 8),
(2, 2, '10:00', '16:00', 8),
(2, 4, '10:00', '16:00', 8);

-- Dr. Omar: Tue, Thu, Sat 9-1
INSERT INTO Doctor_Schedules (doctor_id, day_of_week, start_time, end_time, max_appointments)
VALUES
(3, 1, '09:00', '13:00', 10),
(3, 3, '09:00', '13:00', 10),
(3, 5, '09:00', '13:00', 10);
GO

-- ── Patients ──────────────────────────────────────────────────
INSERT INTO Patients (user_id, first_name, last_name, dob, gender, phone, email, address, emergency_contact, blood_group, allergies)
VALUES
(8, 'Muhammad', 'Khan',    '1985-03-15', 'Male',   '0300-1111111', 'mkhan@email.com',  '12 Gulshan-e-Iqbal, Karachi', 'Zara Khan: 0301-1111112',   'O+',  'Penicillin'),
(9, 'Ayesha',   'Siddiqui','1992-07-22', 'Female', '0301-2222222', 'ayesha@email.com', '45 Defence Phase 5, Karachi', 'Tariq Siddiqui: 0302-2222', 'A+',  NULL),
(NULL, 'Hassan',   'Raza',    '1975-11-08', 'Male',   '0302-3333333', NULL,               '8 PECHS Block 2, Karachi',    'Fatima Raza: 0303-3333',   'B+',  'Sulfa drugs'),
(10, 'Zainab',   'Ahmed',   '2001-04-30', 'Female', '0303-4444444', 'zainab@email.com', '22 Clifton Block 9, Karachi', 'Ahmad: 0304-4444444',       'AB+', NULL),
(NULL, 'Ibrahim',  'Malik',   '1968-09-12', 'Male',   '0304-5555555', NULL,               '99 North Nazimabad, Karachi', 'Sana Malik: 0305-5555',    'O-',  'Aspirin, NSAIDs');
GO

-- ── Medicines ─────────────────────────────────────────────────
INSERT INTO Medicines (name, category, manufacturer, unit_price, stock_quantity, reorder_level, expiry_date)
VALUES
('Paracetamol 500mg',      'Analgesic',     'Getz Pharma',     12.00,  500, 50, '2026-12-31'),
('Amoxicillin 500mg',      'Antibiotic',    'Abbott',          45.00,   8,  20, '2025-08-31'),  -- low stock
('Metformin 500mg',        'Antidiabetic',  'AGP',             25.00, 200, 30, '2026-06-30'),
('Atorvastatin 20mg',      'Statin',        'Sanofi',          55.00,  80, 15, '2026-09-30'),
('Omeprazole 20mg',        'Antacid',       'Highnoon',        30.00,  150, 25, '2026-11-30'),
('Ibuprofen 400mg',        'NSAID',         'Sami',            20.00,  300, 40, '2027-03-31'),
('Cetirizine 10mg',        'Antihistamine', 'ICI Pakistan',    18.00,   5,  20, '2025-10-31'),  -- low stock
('Lisinopril 10mg',        'ACE Inhibitor', 'Getz Pharma',     40.00,  120, 20, '2026-07-31'),
('Salbutamol Inhaler',     'Bronchodilator','GSK',            280.00,  35, 10, '2026-04-30'),
('ORS Sachets',            'Rehydration',   'National Foods',   8.00,  400, 100,'2027-01-31'),
('Vitamin D3 1000IU',      'Supplement',    'Abbott',          60.00,   0,  30, '2026-05-31'), -- out of stock
('Metronidazole 400mg',    'Antibiotic',    'Sami',            22.00,  175, 30, '2026-08-31');
GO

-- ── Appointments (sample mix of past/upcoming) ─────────────
DECLARE @today DATE = CAST(GETDATE() AS DATE);

INSERT INTO Appointments (patient_id, doctor_id, appointment_date, appointment_time, status, reason, notes)
VALUES
(1, 1, DATEADD(DAY, -7, @today), '10:00', 'completed', 'General checkup',         'Patient reports fatigue. BP normal. Advised rest.'),
(2, 2, DATEADD(DAY, -3, @today), '11:00', 'completed', 'Chest pain follow-up',    'ECG normal. Continue current medications.'),
(3, 1, DATEADD(DAY, -1, @today), '14:00', 'completed', 'Diabetes management',     'HbA1c slightly elevated. Increased Metformin dose.'),
(4, 3, @today,                   '09:00', 'scheduled', 'Child vaccination',        NULL),
(5, 2, @today,                   '11:00', 'scheduled', 'Cardiac consultation',     NULL),
(1, 1, DATEADD(DAY, 2, @today),  '10:30', 'scheduled', 'Follow-up blood test',     NULL),
(2, 1, DATEADD(DAY, 5, @today),  '09:00', 'scheduled', 'Routine checkup',          NULL),
(3, 3, DATEADD(DAY, -10,@today), '10:00', 'cancelled', 'Appointment for flu',      NULL);
GO

-- ── Bills ─────────────────────────────────────────────────────
INSERT INTO Billing (patient_id, appointment_id, total_amount, paid_amount, status, payment_method)
VALUES
(1, 1, 2000.00, 2000.00, 'paid',    'Cash'),
(2, 2, 4500.00, 4500.00, 'paid',    'Card'),
(3, 3, 1800.00,  900.00, 'partial', 'Cash'),
(5, 5, 3200.00,    0.00, 'pending', NULL);
GO

INSERT INTO Bill_Items (bill_id, description, quantity, unit_price, total_price)
VALUES
(1, 'Consultation Fee - Dr. Salman Ahmed',   1, 1500.00, 1500.00),
(1, 'Blood Sugar Test',                      1,  300.00,  300.00),
(1, 'Paracetamol 500mg x10',                 1,  200.00,  200.00),
(2, 'Consultation Fee - Dr. Fatima Malik',   1, 3000.00, 3000.00),
(2, 'ECG',                                   1, 1000.00, 1000.00),
(2, 'Atorvastatin 20mg x30',                 1,  500.00,  500.00),
(3, 'Consultation Fee - Dr. Salman Ahmed',   1, 1500.00, 1500.00),
(3, 'HbA1c Test',                            1,  300.00,  300.00),
(4, 'Consultation Fee - Dr. Fatima Malik',   1, 3000.00, 3000.00),
(4, 'Cardiac Stress Test',                   1,  200.00,  200.00);
GO

-- ── Prescriptions ─────────────────────────────────────────────
INSERT INTO Prescriptions (patient_id, doctor_id, appointment_id, notes, is_dispensed)
VALUES
(1, 1, 1, 'Take with food. Avoid alcohol.',     1),
(2, 2, 2, 'Continue current cardiac regimen.',  1),
(3, 1, 3, 'Increase Metformin to twice daily.', 0);
GO

INSERT INTO Prescription_Items (prescription_id, medicine_id, dosage, frequency, duration, quantity)
VALUES
(1, 1,  '500mg',  'Twice daily',   '5 days',   10),  -- Paracetamol
(1, 6,  '400mg',  'Thrice daily',  '3 days',   9),   -- Ibuprofen
(2, 4,  '20mg',   'Once daily',    '30 days',  30),  -- Atorvastatin
(2, 8,  '10mg',   'Once daily',    '30 days',  30),  -- Lisinopril
(3, 3,  '500mg',  'Twice daily',   '30 days',  60),  -- Metformin
(3, 5,  '20mg',   'Once at night', '30 days',  30);  -- Omeprazole
GO

PRINT 'Seed data inserted successfully!';
PRINT 'Login credentials:';
PRINT '  Admin:    admin      / Admin@123';
PRINT '  Doctor 1: dr_ahmed   / DrAhmed@123';
PRINT '  Doctor 2: dr_fatima  / DrFatima@123';
PRINT '  Doctor 3: dr_omar    / DrOmar@123';
PRINT '  Patient 1: pt_mkhan  / PtKhan@123';
PRINT '  Patient 2: pt_ayesha / PtAyesha@123';
PRINT '  Patient 3: pt_zainab / PtZainab@123';
PRINT '  Nurse 1:  nurse_sara / NurseSara@123';
PRINT '  Billing:  billing1   / Billing@123';
PRINT '';
PRINT 'IMPORTANT: Rotate these credentials in production.';
PRINT 'To regenerate password hashes, run: python generate_hashes.py';
GO
