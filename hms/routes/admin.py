from flask import Blueprint, render_template, request, Response
from flask_login import login_required
from hms import db_operations
from hms.utils import admin_required
from datetime import datetime, date, timedelta
from types import SimpleNamespace
import csv, io
import base64

admin_bp = Blueprint('admin', __name__)

_plot_libs_cache = None


def _plot_libs():
    """Defer heavy plotting imports so cold starts work on small serverless bundles."""
    global _plot_libs_cache
    if _plot_libs_cache is None:
        import matplotlib

        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import pandas as pd
        import seaborn as sns

        _plot_libs_cache = (plt, sns, pd)
    return _plot_libs_cache

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


def _status_badge(status):
    badges = {'scheduled': 'primary', 'completed': 'success', 'cancelled': 'danger'}
    return badges.get((status or '').lower(), 'secondary')


def _dashboard_today_appointments(today):
    """Fetch today's appointments using user-defined function from db_operations."""
    rows = db_operations.get_dashboard_today_appointments(today, limit=5)
    return [
        SimpleNamespace(
            patient_id=row["patient_id"],
            appointment_time=row["appointment_time"],
            status=row["status"],
            status_badge=_status_badge(row["status"]),
            patient=SimpleNamespace(full_name=row["patient_name"]),
            doctor=SimpleNamespace(full_name=row["doctor_name"]),
        )
        for row in rows
    ]


def _dashboard_recent_patients():
    """Fetch recent patients using user-defined function from db_operations."""
    rows = db_operations.get_dashboard_recent_patients(limit=5)
    return [SimpleNamespace(**dict(r)) for r in rows]


def _fig_to_base64(fig):
    plt, _sns, _pd = _plot_libs()
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

    # All dashboard metrics via single stored procedure call
    metrics = db_operations.get_admin_dashboard_metrics(today)
    total_patients = metrics["total_patients"]
    today_appointments = metrics["today_appointments"]
    active_admissions = metrics["active_admissions"]
    low_stock_count = metrics["low_stock_count"]
    monthly_revenue = metrics["monthly_revenue"]
    pending_bills_count = metrics["pending_bills_count"]

    todays_appts = _dashboard_today_appointments(today)
    recent_patients = _dashboard_recent_patients()

    # Revenue last 7 days for mini chart via view
    start = today - timedelta(days=6)
    revenue_map = db_operations.get_daily_revenue_range(start, today)
    revenue_data = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        revenue_data.append({'date': d.strftime('%b %d'), 'amount': revenue_map.get(d, 0.0)})

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
    plt, sns, pd = _plot_libs()

    # All data via user-defined functions calling stored procedures
    total = db_operations.get_patient_count()
    by_gender = db_operations.get_patient_gender_summary()
    by_blood = db_operations.get_patient_blood_group_summary()
    monthly_reg = db_operations.get_patient_monthly_registrations()

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
    plt, sns, pd = _plot_libs()
    period = request.args.get('period', 'monthly')
    today = date.today()

    # Revenue trend data via user-defined functions calling stored procedures
    if period == 'daily':
        start = today - timedelta(days=30)
        normalized_data = db_operations.get_revenue_trend_daily(start)
    elif period == 'weekly':
        start = today - timedelta(weeks=12)
        normalized_data = db_operations.get_revenue_trend_weekly(start)
    else:
        normalized_data = db_operations.get_revenue_trend_monthly()

    # Revenue totals via stored procedure
    totals = db_operations.get_revenue_totals()
    total_revenue = totals["total_revenue"]
    total_pending = totals["total_pending"]

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
    # All medicines via stored procedure
    all_meds = db_operations.get_inventory_all()
    low_stock = [m for m in all_meds if m.is_low_stock()]

    # Category summary via view
    cat_rows = db_operations.get_medicine_category_summary()
    by_category = [
        (str(r['category']), int(r['medicine_count'] or 0), float(r['total_stock'] or 0))
        for r in cat_rows
    ]
    total_value = sum(float(r['total_value'] or 0) for r in cat_rows)

    return render_template('admin/report_inventory.html',
                           all_meds=all_meds, low_stock=low_stock,
                           by_category=by_category, total_value=total_value)


@admin_bp.route('/reports/appointments')
@login_required
@admin_required
def report_appointments():
    plt, sns, pd = _plot_libs()

    # Appointment summaries via user-defined functions using views
    by_status = db_operations.get_appointment_status_summary()
    by_doctor = db_operations.get_appointment_doctor_summary()

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
