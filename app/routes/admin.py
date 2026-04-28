from flask import Blueprint, render_template, request, Response
from flask_login import login_required
from app import db
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.models.billing import Bill
from app.models.pharmacy import Medicine
from app.models.doctor import Doctor
from app.models.admission import Admission
from app.utils import admin_required
from datetime import datetime, date, timedelta
from sqlalchemy import func, cast, Date
import csv, io
import base64
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

admin_bp = Blueprint('admin', __name__)


def _fig_to_base64(fig):
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', bbox_inches='tight', dpi=120)
    plt.close(fig)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode('utf-8')


@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    today = date.today()
    month_start = today.replace(day=1)

    total_patients = Patient.query.count()
    today_appointments = Appointment.query.filter_by(appointment_date=today).count()
    active_admissions = Admission.query.filter_by(discharge_date=None).count()
    low_stock_count = Medicine.query.filter(
        Medicine.stock_quantity <= Medicine.reorder_level
    ).count()

    monthly_revenue = db.session.query(func.sum(Bill.paid_amount)).filter(
        Bill.bill_date >= month_start
    ).scalar() or 0

    pending_bills_count = Bill.query.filter_by(status='pending').count()

    # Today's appointments for quick view
    todays_appts = Appointment.query.filter_by(
        appointment_date=today
    ).order_by(Appointment.appointment_time).limit(5).all()

    # Recent patients
    recent_patients = Patient.query.order_by(
        Patient.registration_date.desc()
    ).limit(5).all()

    # Revenue last 7 days for mini chart
    revenue_data = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        rev = db.session.query(func.sum(Bill.paid_amount)).filter(
            cast(Bill.bill_date, Date) == d
        ).scalar() or 0
        revenue_data.append({'date': d.strftime('%b %d'), 'amount': float(rev)})

    return render_template('dashboard/admin_dashboard.html',
                           total_patients=total_patients,
                           today_appointments=today_appointments,
                           active_admissions=active_admissions,
                           low_stock_count=low_stock_count,
                           monthly_revenue=monthly_revenue,
                           pending_bills_count=pending_bills_count,
                           todays_appts=todays_appts,
                           recent_patients=recent_patients,
                           revenue_data=revenue_data)


@admin_bp.route('/reports/patients')
@login_required
@admin_required
def report_patients():
    total = Patient.query.count()
    by_gender = db.session.query(Patient.gender, func.count()).group_by(Patient.gender).all()
    by_blood = db.session.query(Patient.blood_group, func.count()).group_by(Patient.blood_group).all()

    reg_year = func.year(Patient.registration_date)
    reg_month = func.month(Patient.registration_date)
    monthly_reg = db.session.query(
        reg_year.label('yr'),
        reg_month.label('mo'),
        func.count().label('cnt')
    ).group_by(reg_year, reg_month).order_by(reg_year, reg_month).limit(12).all()

    gender_df = pd.DataFrame(by_gender, columns=['gender', 'count'])
    blood_df = pd.DataFrame(by_blood, columns=['blood_group', 'count'])
    monthly_df = pd.DataFrame(monthly_reg, columns=['yr', 'mo', 'cnt'])

    sns.set_theme(style='whitegrid')

    fig_gender, ax_gender = plt.subplots(figsize=(5, 4))
    if not gender_df.empty and gender_df['count'].sum() > 0:
        ax_gender.pie(
            gender_df['count'],
            labels=gender_df['gender'].fillna('Unknown'),
            autopct='%1.1f%%',
            startangle=140
        )
    else:
        ax_gender.text(0.5, 0.5, 'No data', ha='center', va='center')
    ax_gender.set_title('Patients by Gender')
    gender_chart = _fig_to_base64(fig_gender)

    fig_blood, ax_blood = plt.subplots(figsize=(6, 4))
    if not blood_df.empty:
        blood_df['blood_group'] = blood_df['blood_group'].fillna('Unknown')
        sns.barplot(data=blood_df, x='blood_group', y='count', ax=ax_blood, color='#ef4444')
        ax_blood.set_ylabel('Patients')
        ax_blood.set_xlabel('Blood Group')
    else:
        ax_blood.text(0.5, 0.5, 'No data', ha='center', va='center')
    ax_blood.set_title('Patients by Blood Group')
    blood_chart = _fig_to_base64(fig_blood)

    fig_monthly, ax_monthly = plt.subplots(figsize=(7, 4))
    if not monthly_df.empty:
        monthly_df['period'] = monthly_df.apply(lambda r: f"{int(r['yr'])}-{int(r['mo']):02d}", axis=1)
        sns.lineplot(data=monthly_df, x='period', y='cnt', marker='o', ax=ax_monthly, color='#4378f4')
        ax_monthly.set_ylabel('Registrations')
        ax_monthly.set_xlabel('Month')
        ax_monthly.tick_params(axis='x', rotation=45)
    else:
        ax_monthly.text(0.5, 0.5, 'No data', ha='center', va='center')
    ax_monthly.set_title('Monthly Patient Registrations')
    monthly_chart = _fig_to_base64(fig_monthly)

    return render_template(
        'admin/report_patients.html',
        total=total,
        by_gender=by_gender,
        by_blood=by_blood,
        monthly_reg=monthly_reg,
        gender_chart=gender_chart,
        blood_chart=blood_chart,
        monthly_chart=monthly_chart
    )


@admin_bp.route('/reports/revenue')
@login_required
@admin_required
def report_revenue():
    period = request.args.get('period', 'monthly')
    today = date.today()

    if period == 'daily':
        start = today - timedelta(days=30)
        bill_day = cast(Bill.bill_date, Date)
        data = db.session.query(
            bill_day.label('period'),
            func.sum(Bill.total_amount).label('total'),
            func.sum(Bill.paid_amount).label('paid')
        ).filter(bill_day >= start).group_by(bill_day).order_by(bill_day).all()
    elif period == 'weekly':
        start = today - timedelta(weeks=12)
        iso_week = func.datepart(db.text('iso_week'), Bill.bill_date)
        data = db.session.query(
            iso_week.label('period'),
            func.sum(Bill.total_amount).label('total'),
            func.sum(Bill.paid_amount).label('paid')
        ).filter(Bill.bill_date >= start).group_by(iso_week).order_by(iso_week).all()
    else:
        bill_year = func.year(Bill.bill_date)
        bill_month = func.month(Bill.bill_date)
        data = db.session.query(
            bill_year.label('yr'),
            bill_month.label('mo'),
            func.sum(Bill.total_amount).label('total'),
            func.sum(Bill.paid_amount).label('paid')
        ).group_by(bill_year, bill_month).order_by(bill_year, bill_month).limit(12).all()

    total_revenue = db.session.query(func.sum(Bill.paid_amount)).scalar() or 0
    total_pending = db.session.query(
        func.sum(Bill.total_amount - Bill.paid_amount)
    ).filter(Bill.status != 'paid').scalar() or 0

    # Normalize rows for template + plotting
    if period == 'monthly':
        normalized_data = [
            (f"{int(r[0])}-{int(r[1]):02d}", float(r[2] or 0), float(r[3] or 0))
            for r in data
        ]
    else:
        normalized_data = [
            (str(r[0]), float(r[1] or 0), float(r[2] or 0))
            for r in data
        ]

    revenue_df = pd.DataFrame(normalized_data, columns=['period', 'total', 'paid'])
    sns.set_theme(style='whitegrid')
    fig_revenue, ax_revenue = plt.subplots(figsize=(9, 4))
    if not revenue_df.empty:
        ax_revenue.bar(revenue_df['period'], revenue_df['total'], label='Billed', alpha=0.5, color='#4378f4')
        ax_revenue.plot(revenue_df['period'], revenue_df['paid'], label='Collected', marker='o', color='#10b981')
        ax_revenue.tick_params(axis='x', rotation=45)
        ax_revenue.legend()
    else:
        ax_revenue.text(0.5, 0.5, 'No revenue data', ha='center', va='center')
    ax_revenue.set_title(f'Revenue Trend ({period.title()})')
    ax_revenue.set_ylabel('Amount (Rs.)')
    revenue_chart = _fig_to_base64(fig_revenue)

    return render_template(
        'admin/report_revenue.html',
        data=normalized_data,
        period=period,
        total_revenue=total_revenue,
        total_pending=total_pending,
        revenue_chart=revenue_chart
    )


@admin_bp.route('/reports/inventory')
@login_required
@admin_required
def report_inventory():
    all_meds = Medicine.query.order_by(Medicine.stock_quantity).all()
    low_stock = [m for m in all_meds if m.is_low_stock()]
    by_category = db.session.query(
        Medicine.category, func.count(), func.sum(Medicine.stock_quantity)
    ).group_by(Medicine.category).all()
    total_value = db.session.query(
        func.sum(Medicine.unit_price * Medicine.stock_quantity)
    ).scalar() or 0

    return render_template('admin/report_inventory.html',
                           all_meds=all_meds, low_stock=low_stock,
                           by_category=by_category, total_value=total_value)


@admin_bp.route('/reports/appointments')
@login_required
@admin_required
def report_appointments():
    by_status = db.session.query(
        Appointment.status, func.count()
    ).group_by(Appointment.status).all()

    by_doctor = db.session.query(
        Doctor.first_name, Doctor.last_name, func.count(Appointment.appointment_id)
    ).join(Appointment).group_by(Doctor.doctor_id, Doctor.first_name, Doctor.last_name).all()

    status_df = pd.DataFrame(by_status, columns=['status', 'count'])
    doctor_df = pd.DataFrame(by_doctor, columns=['first_name', 'last_name', 'count'])
    if not doctor_df.empty:
        doctor_df['doctor'] = 'Dr. ' + doctor_df['first_name'] + ' ' + doctor_df['last_name']

    sns.set_theme(style='whitegrid')
    fig_status, ax_status = plt.subplots(figsize=(5, 4))
    if not status_df.empty and status_df['count'].sum() > 0:
        ax_status.pie(
            status_df['count'],
            labels=status_df['status'].str.title(),
            autopct='%1.1f%%',
            startangle=140
        )
    else:
        ax_status.text(0.5, 0.5, 'No data', ha='center', va='center')
    ax_status.set_title('Appointments by Status')
    status_chart = _fig_to_base64(fig_status)

    fig_doctor, ax_doctor = plt.subplots(figsize=(8, 4))
    if not doctor_df.empty:
        sns.barplot(data=doctor_df, x='doctor', y='count', ax=ax_doctor, color='#4378f4')
        ax_doctor.tick_params(axis='x', rotation=45)
        ax_doctor.set_ylabel('Appointments')
        ax_doctor.set_xlabel('Doctor')
    else:
        ax_doctor.text(0.5, 0.5, 'No data', ha='center', va='center')
    ax_doctor.set_title('Appointments by Doctor')
    doctor_chart = _fig_to_base64(fig_doctor)

    return render_template(
        'admin/report_appointments.html',
        by_status=by_status,
        by_doctor=by_doctor,
        status_chart=status_chart,
        doctor_chart=doctor_chart
    )
