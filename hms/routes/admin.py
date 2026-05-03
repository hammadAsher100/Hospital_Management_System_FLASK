from flask import Blueprint, render_template, request, Response
from flask_login import login_required
from hms import db
from hms.models.patient import Patient
from hms.models.appointment import Appointment
from hms.models.billing import Bill
from hms.models.pharmacy import Medicine
from hms.models.doctor import Doctor
from hms.models.admission import Admission
from hms.utils import admin_required
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

HMS_COLORS = {
    'primary': '#4378f4',
    'primary_light': '#dbe7ff',
    'success': '#10b981',
    'danger': '#ef4444',
    'warning': '#f59e0b',
    'purple': '#8b5cf6',
    'teal': '#06b6d4',
    'slate': '#334155'
}

HMS_PALETTE = [
    HMS_COLORS['primary'],
    HMS_COLORS['success'],
    HMS_COLORS['purple'],
    HMS_COLORS['warning'],
    HMS_COLORS['teal'],
    HMS_COLORS['danger']
]


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

    sns.set_theme(style='whitegrid', context='talk')

    fig_gender, ax_gender = plt.subplots(figsize=(5, 4))
    if not gender_df.empty and gender_df['count'].sum() > 0:
        labels = gender_df['gender'].fillna('Unknown')
        wedges, _texts, _autotexts = ax_gender.pie(
            gender_df['count'],
            labels=labels,
            autopct='%1.1f%%',
            startangle=130,
            colors=HMS_PALETTE[:len(gender_df)],
            wedgeprops={'width': 0.46, 'edgecolor': 'white', 'linewidth': 2},
            textprops={'fontsize': 10, 'color': HMS_COLORS['slate']}
        )
        for w in wedges:
            w.set_alpha(0.95)
    else:
        ax_gender.text(0.5, 0.5, 'No data', ha='center', va='center', color=HMS_COLORS['slate'])
    ax_gender.set_title('Patients by Gender', fontsize=13, fontweight='bold', color=HMS_COLORS['slate'])
    gender_chart = _fig_to_base64(fig_gender)

    fig_blood, ax_blood = plt.subplots(figsize=(6, 4))
    if not blood_df.empty:
        blood_df['blood_group'] = blood_df['blood_group'].fillna('Unknown')
        blood_df = blood_df.sort_values('count', ascending=False)
        sns.barplot(data=blood_df, x='blood_group', y='count', ax=ax_blood, palette='Reds_r')
        ax_blood.set_ylabel('Patients')
        ax_blood.set_xlabel('Blood Group')
        for container in ax_blood.containers:
            ax_blood.bar_label(container, padding=3, fontsize=9, color=HMS_COLORS['slate'])
    else:
        ax_blood.text(0.5, 0.5, 'No data', ha='center', va='center', color=HMS_COLORS['slate'])
    ax_blood.set_title('Patients by Blood Group', fontsize=13, fontweight='bold', color=HMS_COLORS['slate'])
    ax_blood.grid(axis='x', visible=False)
    blood_chart = _fig_to_base64(fig_blood)

    fig_monthly, ax_monthly = plt.subplots(figsize=(7, 4))
    if not monthly_df.empty:
        monthly_df['period'] = monthly_df.apply(lambda r: f"{int(r['yr'])}-{int(r['mo']):02d}", axis=1)
        x_pos = list(range(len(monthly_df)))
        ax_monthly.plot(x_pos, monthly_df['cnt'], marker='o', linewidth=2.6, color=HMS_COLORS['primary'])
        ax_monthly.fill_between(x_pos, monthly_df['cnt'], color=HMS_COLORS['primary_light'], alpha=0.5)
        ax_monthly.set_xticks(x_pos)
        ax_monthly.set_xticklabels(monthly_df['period'])
        ax_monthly.set_ylabel('Registrations')
        ax_monthly.set_xlabel('Month')
        ax_monthly.tick_params(axis='x', rotation=45)
    else:
        ax_monthly.text(0.5, 0.5, 'No data', ha='center', va='center', color=HMS_COLORS['slate'])
    ax_monthly.set_title('Monthly Patient Registrations', fontsize=13, fontweight='bold', color=HMS_COLORS['slate'])
    ax_monthly.grid(axis='x', visible=False)
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
    sns.set_theme(style='whitegrid', context='talk')
    fig_revenue, ax_revenue = plt.subplots(figsize=(9, 4))
    if not revenue_df.empty:
        x_pos = list(range(len(revenue_df)))
        ax_revenue.bar(x_pos, revenue_df['total'], label='Billed', alpha=0.75, color=HMS_COLORS['primary'], edgecolor='white', linewidth=1.1)
        ax_revenue.plot(x_pos, revenue_df['paid'], label='Collected', marker='o', linewidth=2.6, color=HMS_COLORS['success'])
        ax_revenue.fill_between(x_pos, revenue_df['paid'], color='#d1fae5', alpha=0.6)
        ax_revenue.set_xticks(x_pos)
        ax_revenue.set_xticklabels(revenue_df['period'], rotation=45, ha='right')
        ax_revenue.legend(frameon=False, loc='upper left')
    else:
        ax_revenue.text(0.5, 0.5, 'No revenue data', ha='center', va='center', color=HMS_COLORS['slate'])
    ax_revenue.set_title(f'Revenue Trend ({period.title()})', fontsize=13, fontweight='bold', color=HMS_COLORS['slate'])
    ax_revenue.set_ylabel('Amount ($)')
    ax_revenue.grid(axis='x', visible=False)
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
    by_category_raw = db.session.query(
        Medicine.category, func.count(), func.sum(Medicine.stock_quantity)
    ).group_by(Medicine.category).all()
    by_category = [
        (
            str(row[0] or 'Uncategorized'),
            int(row[1] or 0),
            float(row[2] or 0)
        )
        for row in by_category_raw
    ]
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

    sns.set_theme(style='whitegrid', context='talk')
    fig_status, ax_status = plt.subplots(figsize=(5, 4))
    if not status_df.empty and status_df['count'].sum() > 0:
        status_labels = status_df['status'].str.title()
        status_colors = [
            HMS_COLORS['primary'] if s == 'Scheduled' else HMS_COLORS['success'] if s == 'Completed' else HMS_COLORS['danger']
            for s in status_labels
        ]
        ax_status.pie(
            status_df['count'],
            labels=status_labels,
            autopct='%1.1f%%',
            startangle=120,
            colors=status_colors,
            wedgeprops={'width': 0.45, 'edgecolor': 'white', 'linewidth': 2},
            textprops={'fontsize': 10, 'color': HMS_COLORS['slate']}
        )
    else:
        ax_status.text(0.5, 0.5, 'No data', ha='center', va='center', color=HMS_COLORS['slate'])
    ax_status.set_title('Appointments by Status', fontsize=13, fontweight='bold', color=HMS_COLORS['slate'])
    status_chart = _fig_to_base64(fig_status)

    fig_doctor, ax_doctor = plt.subplots(figsize=(8, 4))
    if not doctor_df.empty:
        doctor_df = doctor_df.sort_values('count', ascending=False)
        sns.barplot(data=doctor_df, x='doctor', y='count', ax=ax_doctor, palette='Blues')
        ax_doctor.tick_params(axis='x', rotation=45)
        ax_doctor.set_ylabel('Appointments')
        ax_doctor.set_xlabel('Doctor')
        for container in ax_doctor.containers:
            ax_doctor.bar_label(container, padding=3, fontsize=9, color=HMS_COLORS['slate'])
    else:
        ax_doctor.text(0.5, 0.5, 'No data', ha='center', va='center', color=HMS_COLORS['slate'])
    ax_doctor.set_title('Appointments by Doctor', fontsize=13, fontweight='bold', color=HMS_COLORS['slate'])
    ax_doctor.grid(axis='x', visible=False)
    doctor_chart = _fig_to_base64(fig_doctor)

    return render_template(
        'admin/report_appointments.html',
        by_status=by_status,
        by_doctor=by_doctor,
        status_chart=status_chart,
        doctor_chart=doctor_chart
    )
