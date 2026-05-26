<div align="center">

<!-- Animated Banner -->
<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,11,20&height=200&section=header&text=Hospital%20Management%20System&fontSize=40&fontColor=fff&animation=twinkling&fontAlignY=35&desc=A%20full-stack%20web%20application%20to%20digitize%20hospital%20operations&descAlignY=55&descSize=16" width="100%"/>

<br/>

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)

<br/>

> **A comprehensive, role-based Hospital Management System built with Flask & PostgreSQL, designed to digitize, automate, and streamline hospital operations from patient intake to billing.**

<br/>

[🚀 Features](#-features) · [🏗️ Architecture](#️-architecture) · [📁 Project Structure](#-project-structure) · [⚙️ Setup](#️-setup--installation) · [👥 Team](#-team)

</div>

---

## 🌐 Live Demo

**[https://hospital-management-system-flask.onrender.com](https://hospital-management-system-flask.onrender.com)**

| Role | Username | Password |
|---|---|---|
| Administrator | `admin` | `Admin@123` |
| Doctor | `dr_ahmed` | `DrAhmed@123` |
| Patient | `pt_mkhan` | `PtKhan@123` |

> ⚠️ Hosted on Render free tier — first load may take ~30 seconds to wake up.

---

## 📌 Overview

The **Hospital Management System (HMS)** is a secure, web-based platform built for small to mid-sized hospitals and clinics. It replaces fragmented, paper-based processes with a unified digital environment — covering everything from patient registration and appointment scheduling to pharmacy inventory and admin-level reporting.

The system supports **four distinct user roles** — Administrator, Doctor, Nurse, and Billing Staff — each with access scoped to their responsibilities.

---

## ✨ Features

### 🧑‍⚕️ Patient Management
- Register new patients with complete demographic and medical profiles
- Maintain detailed medical history per patient
- Track admissions and discharge records

### 📅 Appointment Scheduling
- Book, reschedule, and cancel appointments
- Automated conflict detection to prevent double-booking
- Doctor availability checks in real-time

### 👨‍💼 Doctor & Staff Management
- Manage doctor profiles, specializations, and weekly schedules
- Assign and update staff roles and access levels
- Track availability for appointment routing

### 💳 Billing & Invoice Generation
- Generate itemized invoices for consultations, procedures, and medications
- Track payment status (paid / pending / partial)
- Exportable billing records

### 💊 Pharmacy Management
- Manage medicine inventory with quantity tracking
- Process prescriptions linked to patient visits
- Automated **low-stock alerts** to prevent stockouts

### 📊 Admin Dashboard & Reports
- Role-based access control (RBAC) across all modules
- Real-time statistics: active patients, appointments today, revenue, inventory status
- Exportable reports for management and auditing

---

## 🏗️ Architecture

The system follows a layered **MVC (Model-View-Controller)** architecture:

```
┌─────────────────────────────────────────────────────────┐
│                     Client (Browser)                    │
│              HTML · CSS · Jinja2 Templates              │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP
┌────────────────────────▼────────────────────────────────┐
│                Flask Application Layer                  │
│         Routes · Controllers · Middleware (Auth)        │
└────────────────────────┬────────────────────────────────┘
                         │ ORM / Raw SQL
┌────────────────────────▼────────────────────────────────┐
│              PostgreSQL Database (Render)               │
│   Patients · Appointments · Staff · Billing · Pharmacy  │
└─────────────────────────────────────────────────────────┘
```

**Tech Stack:**

| Layer | Technology |
|---|---|
| Backend Framework | Flask (Python) |
| Database | PostgreSQL (Render) |
| Templating | Jinja2 |
| Frontend | HTML5, CSS3, JavaScript |
| Auth | Flask-Login + bcrypt |
| DB Driver | psycopg2 |

---

## 📁 Project Structure

```
hospital-management-system/
│
├── hms/                          # Flask application package
│   ├── __init__.py               # App factory & config
│   ├── models/                   # Database models
│   │   ├── patient.py
│   │   ├── doctor.py
│   │   ├── appointment.py
│   │   ├── billing.py
│   │   ├── pharmacy.py
│   │   └── user.py
│   │
│   ├── routes/                   # Blueprint route handlers
│   │   ├── auth.py               # Login / logout
│   │   ├── patients.py
│   │   ├── appointments.py
│   │   ├── staff.py
│   │   ├── billing.py
│   │   ├── pharmacy.py
│   │   └── admin.py
│   │
│   ├── templates/                # Jinja2 HTML templates
│   │   ├── base.html
│   │   ├── dashboard/
│   │   ├── patients/
│   │   ├── appointments/
│   │   ├── billing/
│   │   ├── pharmacy/
│   │   └── staff/
│   │
│   └── static/                   # CSS, JS, images
│       ├── css/
│       ├── js/
│       └── img/
│
├── database/
│   ├── schema.sql                # Full DB schema
│   └── seed.sql                  # Sample / seed data
│
├── config.py                     # Environment config
├── requirements.txt
├── app.py                        # Entry point (WSGI; Vercel uses this file)
└── README.md
```

---

## ⚙️ Setup & Installation

### Prerequisites

- Python 3.11+
- PostgreSQL (or use the hosted Render database)

### 1. Clone the repository

```bash
git clone https://github.com/hammadasher100/hospital-management-system.git
cd hospital-management-system
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the database

Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key
FLASK_ENV=development
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DB_NAME
```

Then initialize the database:

```bash
python database/init_db.py
```

### 5. Run the application

```bash
python app.py
```

Visit `http://127.0.0.1:5000` in your browser.

---

## 🧪 Design Pattern Demo & Tests

This repo includes a small runnable script + automated tests to demonstrate the implemented design patterns:

### Run the demo (prints pattern output)

```bash
python scripts/patterns_demo.py
```

### Run tests (no extra dependencies; uses built-in unittest)

```bash
python -m unittest -v tests.test_patterns
```

---

## 👥 Roles & Access

| Role | Access Scope |
|---|---|
| **Administrator** | Full access — all modules + user management |
| **Doctor** | Patient records, appointments, prescriptions |
| **Nurse** | Patient tracking, admission/discharge |
| **Billing Staff** | Invoice generation, payment tracking |

---

## 🗂️ Module Ownership

| Module | Owner |
|---|---|
| Reports, Analytics & Admin Dashboard | Muhammad Hammad Asher *(Team Lead)* |
| Patient Management & Appointment Scheduling | Asma Azam |
| Doctor & Staff Management | Alifya Shabbir |
| Billing & Pharmacy Management | Aliza Ujan |


---

## 🛣️ Roadmap

- [x] Project proposal & architecture design
- [x] Database schema design & normalization
- [x] Patient & appointment module
- [x] Doctor & staff module
- [x] Billing & pharmacy module
- [x] Admin dashboard & reports
- [x] Role-based authentication
- [x] Final integration & testing
- [x] Deployment

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,11,20&height=100&section=footer" width="100%"/>

</div>
