"""
app.py — Form 20 Backlog Dashboard
Flask backend with SQLite. Run: python app.py
"""

import csv
import io
import os
import json
import threading
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, redirect, render_template, request, send_file

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data.db')
EXCEL_PATH = os.path.join(BASE_DIR, 'Form20 Backlog Tracker.xlsx')


# ── DB helpers ──────────────────────────────────────────────────────────────

class TursoCursorWrapper:
    def __init__(self, result_set):
        self.result_set = result_set
    
    def fetchall(self):
        cols = self.result_set.columns
        return [dict(zip(cols, list(r))) for r in self.result_set.rows]
        
    def fetchone(self):
        if not self.result_set.rows: return None
        cols = self.result_set.columns
        return dict(zip(cols, list(self.result_set.rows[0])))

class TursoConnectionWrapper:
    def __init__(self, client):
        self.client = client
    
    def execute(self, query, params=()):
        result_set = self.client.execute(query, list(params))
        return TursoCursorWrapper(result_set)
        
    def close(self):
        self.client.close()
        
    def commit(self):
        pass

def get_db():
    import os
    turso_url = os.environ.get('TURSO_DATABASE_URL')
    turso_token = os.environ.get('TURSO_AUTH_TOKEN')
    
    if turso_url and turso_token:
        import libsql_client
        # Ensure HTTPS for robust connection
        turso_url = turso_url.replace('libsql://', 'https://')
        client = libsql_client.create_client_sync(url=turso_url, auth_token=turso_token)
        return TursoConnectionWrapper(client)
    else:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def get_rds_db():
    import os
    import psycopg2
    from psycopg2.extras import DictCursor
    
    # Credentials from AWS RDS
    db_host = os.environ.get('DB_HOST')
    db_port = os.environ.get('DB_PORT', '5432')
    db_user = os.environ.get('DB_USER')
    db_pass = os.environ.get('DB_PASSWORD')
    db_name = os.environ.get('DB_NAME')
    
    if not all([db_host, db_user, db_pass, db_name]):
        return None
        
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_pass,
        dbname=db_name
    )
    conn.autocommit = True
    return conn

# Standard ECI state codes mapping
STATE_TO_ECI = {
    'AP': 'S01', 'AR': 'S02', 'AS': 'S03', 'BR': 'S04', 'GA': 'S05',
    'GJ': 'S06', 'HR': 'S07', 'HP': 'S08', 'KA': 'S10', 'KL': 'S11',
    'MP': 'S12', 'MH': 'S13', 'MN': 'S14', 'ML': 'S15', 'MZ': 'S16',
    'NL': 'S17', 'OR': 'S18', 'PB': 'S19', 'RJ': 'S20', 'SK': 'S21',
    'TN': 'S22', 'TR': 'S23', 'UP': 'S24', 'WB': 'S25', 'CG': 'S26',
    'JH': 'S27', 'UK': 'S28', 'TS': 'S29',
    'AN': 'U01', 'CH': 'U02', 'DD': 'U03', 'DN': 'U03', 'DL': 'U05',
    'LD': 'U06', 'PY': 'U07', 'JK': 'U08', 'LA': 'U09'
}

# ── Live AWS Caching ────────────────────────────────────────────────────────

LIVE_JSON_PATH = os.path.join(BASE_DIR, 'live_extracted.json')

def fetch_live_json_sync():
    rds_conn = get_rds_db()
    if not rds_conn:
        return
    try:
        with rds_conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT state_abb, el_type, el_year 
                FROM public.form20_summary_view
            """)
            rds_data = cur.fetchall()
        
        extracted_list = [{"state": str(r[0]).strip(), "el_type": str(r[1]).strip(), "el_year": str(r[2]).strip()} for r in rds_data if r[0] and r[1] and r[2]]
        
        with open(LIVE_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(extracted_list, f)
    except Exception as e:
        print(f"Background thread error fetching AWS data: {e}")
    finally:
        rds_conn.close()

def update_live_extracted_json():
    while True:
        fetch_live_json_sync()
        time.sleep(60) # sync every 60 seconds

bg_thread = threading.Thread(target=update_live_extracted_json, daemon=True)
bg_thread.start()

def get_live_extracted_set():
    if not os.path.exists(LIVE_JSON_PATH):
        return set()
    try:
        with open(LIVE_JSON_PATH, 'r', encoding='utf-8') as f:
            extracted_list = json.load(f)
        return set((item['state'], item['el_type'], item['el_year']) for item in extracted_list)
    except Exception:
        return set()

DOWNLOAD_JSON_PATH = os.path.join(BASE_DIR, 'download_report.json')

def get_download_report_dict():
    if not os.path.exists(DOWNLOAD_JSON_PATH):
        return {}
    try:
        with open(DOWNLOAD_JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

HISTORY_JSON_PATH = os.path.join(BASE_DIR, 'completion_history.json')
def get_completion_history():
    if not os.path.exists(HISTORY_JSON_PATH):
        return {}
    try:
        with open(HISTORY_JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_completion_history(history):
    try:
        with open(HISTORY_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass

def apply_dynamic_status(r_dict, live_extracted, download_report, history=None):
    key = f"{str(r_dict['state']).strip()}-{str(r_dict['el_type']).strip()}-{str(r_dict['el_year']).strip()}"
    
    current_status = r_dict.get('overall_status')
    
    # 1. Apply download report status if present
    if key in download_report:
        csv_status = download_report[key]
        if current_status not in ('db_pushed', 'completed', 'extracted'):
            r_dict['overall_status'] = csv_status
        if csv_status == 'missing' and current_status in ('downloaded', 'pending'):
            r_dict['overall_status'] = 'missing'
        
    # 2. Apply live extracted status if present
    aws_el_type = str(r_dict['el_type']).strip().replace('-BP', '')
    is_live_completed = (str(r_dict['state']).strip(), aws_el_type, str(r_dict['el_year']).strip()) in live_extracted
    if is_live_completed:
        r_dict['overall_status'] = 'completed'
        r_dict['db_status'] = 'in_db'
        
    if history is not None and r_dict['overall_status'] == 'db_pushed':
        if key not in history:
            history[key] = datetime.now().strftime('%Y-%m-%d')
            history['_updated'] = True
            
    return r_dict


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/records', methods=['GET'])
def get_records():
    conn = get_db()
    query = 'SELECT * FROM records WHERE 1=1'
    params = []

    state    = request.args.get('state', '').strip()
    el_type  = request.args.get('el_type', '').strip()
    year     = request.args.get('year', '').strip()
    status   = request.args.get('status', '').strip()
    sir_only = request.args.get('sir_only', '')
    search   = request.args.get('search', '').strip()

    if state:
        query += ' AND state = ?'; params.append(state)
    if el_type:
        query += ' AND el_type = ?'; params.append(el_type)
    if year:
        query += ' AND el_year = ?'; params.append(int(year))
    if sir_only == '1':
        query += ' AND is_sir_state = 1'
    if request.args.get('wip') == '1':
        query += ' AND wip = 1'
    hide_bp = request.args.get('hide_bp', '')
    if hide_bp == '1':
        query += " AND el_type NOT LIKE '%-BP'"
    if search:
        like = f'%{search}%'
        query += (' AND (state LIKE ? OR state_name LIKE ?'
                  ' OR key LIKE ? OR assigned_to LIKE ? OR remark LIKE ?)')
        params.extend([like, like, like, like, like])

    query += ' ORDER BY state, el_type, el_year'

    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    live_extracted = get_live_extracted_set()
    download_report = get_download_report_dict()
    history = get_completion_history()
    filtered_rows = []
    
    for r in rows:
        r_dict = dict(r)
        r_dict = apply_dynamic_status(r_dict, live_extracted, download_report, history)
            
        if status:
            if r_dict['overall_status'] != status:
                continue
        elif not search:
            if r_dict['overall_status'] in ('db_pushed', 'completed') or r_dict['db_status'] == 'in_db':
                continue
                
        filtered_rows.append(r_dict)
        
    if history.pop('_updated', False):
        save_completion_history(history)
        
    return jsonify(filtered_rows)


@app.route('/api/records/<int:record_id>', methods=['PATCH'])
def update_record(record_id):
    import sqlite3
    data = request.get_json() or {}
    allowed = {'overall_status', 'assigned_to', 'remark',
                'retro_ready', 'wip', 'extraction_status', 'db_status'}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({'error': 'No valid fields'}), 400

    updates['last_updated'] = datetime.now().strftime('%Y-%m-%d')
    set_clause = ', '.join(f'{k} = ?' for k in updates)
    vals = list(updates.values()) + [record_id]

    conn = get_db()
    conn.execute(f'UPDATE records SET {set_clause} WHERE id = ?', vals)
    conn.commit()
    row = conn.execute('SELECT * FROM records WHERE id = ?', [record_id]).fetchone()
    conn.close()
    
    r_dict = dict(row)
    live_extracted = get_live_extracted_set()
    download_report = get_download_report_dict()
    history = get_completion_history()
    r_dict = apply_dynamic_status(r_dict, live_extracted, download_report, history)
    if history.pop('_updated', False):
        save_completion_history(history)
        
    return jsonify(r_dict)


@app.route('/api/stats')
def get_stats():
    conn = get_db()
    query = 'SELECT * FROM records WHERE 1=1'
    params = []

    state    = request.args.get('state', '').strip()
    el_type  = request.args.get('el_type', '').strip()
    year     = request.args.get('year', '').strip()
    sir_only = request.args.get('sir_only', '')
    search   = request.args.get('search', '').strip()
    hide_bp  = request.args.get('hide_bp', '')

    if state:
        query += ' AND state = ?'; params.append(state)
    if el_type:
        query += ' AND el_type = ?'; params.append(el_type)
    if year:
        query += ' AND el_year = ?'; params.append(int(year))
    if sir_only == '1':
        query += ' AND is_sir_state = 1'
    if hide_bp == '1':
        query += " AND el_type NOT LIKE '%-BP'"
    if search:
        like = f'%{search}%'
        query += (' AND (state LIKE ? OR state_name LIKE ?'
                  ' OR key LIKE ? OR assigned_to LIKE ? OR remark LIKE ?)')
        params.extend([like, like, like, like, like])

    all_records = conn.execute(query, params).fetchall()
    conn.close()

    live_extracted = get_live_extracted_set()
    download_report = get_download_report_dict()
    history = get_completion_history()

    by_status = {'downloaded': 0, 'extracted': 0, 'missing': 0, 'pending': 0, 'completed': 0, 'db_pushed': 0}
    sir_by_status = {'downloaded': 0, 'extracted': 0, 'missing': 0, 'pending': 0, 'completed': 0, 'db_pushed': 0}
    wip_count = 0
    state_dict = {}
    type_dict = {}

    for r in all_records:
        r_dict = dict(r)
        r_dict = apply_dynamic_status(r_dict, live_extracted, download_report, history)
        
        state = r_dict['state']
        
        if state not in state_dict:
            state_dict[state] = {
                'state': state,
                'state_name': r_dict['state_name'],
                'total': 0,
                'completed': 0,
                'extracted': 0,
                'missing': 0
            }
            
        state_dict[state]['total'] += 1
        
        el_type_base = r_dict['el_type'].split('-')[0] if r_dict['el_type'] else 'Unknown'
        if el_type_base not in type_dict:
            type_dict[el_type_base] = {
                'total': 0,
                'completed': 0,
                'missing': 0,
                'downloaded': 0
            }
        type_dict[el_type_base]['total'] += 1
        
        effective_status = r_dict['overall_status']
        
        by_status[effective_status] = by_status.get(effective_status, 0) + 1
        if r_dict['is_sir_state'] == 1:
            sir_by_status[effective_status] = sir_by_status.get(effective_status, 0) + 1
            
        if r_dict['wip'] == 1 and effective_status != 'completed':
            wip_count += 1
            
        if effective_status in ('completed', 'db_pushed'):
            state_dict[state]['completed'] += 1
            type_dict[el_type_base]['completed'] += 1
        if effective_status == 'extracted':
            state_dict[state]['extracted'] += 1
        if effective_status == 'missing':
            state_dict[state]['missing'] += 1
            type_dict[el_type_base]['missing'] += 1
        if effective_status == 'downloaded':
            type_dict[el_type_base]['downloaded'] += 1

    total = sum(by_status.values())
    state_rows = [state_dict[s] for s in sorted(state_dict.keys())]
    
    # Calculate bottlenecks (top 5 states with most missing records)
    bottlenecks = sorted(state_rows, key=lambda x: x['missing'], reverse=True)[:5]

    if history.pop('_updated', False):
        save_completion_history(history)

    return jsonify({
        'total': total,
        'by_status': by_status,
        'sir_by_status': sir_by_status,
        'wip_count': wip_count,
        'by_state': state_rows,
        'by_type': type_dict,
        'bottlenecks': bottlenecks
    })


@app.route('/api/glance_report')
def glance_report():
    history = get_completion_history()
    history.pop('_updated', None)

    filter_month = request.args.get('month', '').strip()
    filter_state = request.args.get('state', '').strip()
    filter_el_type = request.args.get('el_type', '').strip()
    hide_bp = request.args.get('hide_bp', '') == '1'
    sir_only = request.args.get('sir_only', '') == '1'

    # SIR state set (only loaded when filtering by SIR)
    sir_states = set()
    if sir_only:
        try:
            conn = get_db()
            sir_rows = conn.execute("SELECT DISTINCT state FROM records WHERE is_sir_state = 1").fetchall()
            conn.close()
            sir_states = {str(dict(r)['state']).strip() for r in sir_rows}
        except Exception:
            sir_states = set()

    weekly_counts  = {}
    records_by_week  = {}
    monthly_counts = {}
    records_by_month = {}

    today = datetime.now().date()
    cur_week_start = today - timedelta(days=today.weekday())
    cur_week_end   = cur_week_start + timedelta(days=6)
    cur_week_label = f"{cur_week_start.strftime('%Y-%m-%d')} to {cur_week_end.strftime('%Y-%m-%d')}"

    for key, date_str in history.items():
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
        except Exception:
            continue
            
        parts = key.split('-')
        k_state = parts[0] if len(parts) > 0 else ''
        k_el_type = parts[1] if len(parts) > 1 else ''

        if filter_state and k_state != filter_state:
            continue
        if filter_el_type and k_el_type != filter_el_type:
            continue
        if hide_bp and '-BP' in key:
            continue
        if sir_only and k_state not in sir_states:
            continue

        # Weekly bucket
        sw = d - timedelta(days=d.weekday())
        ew = sw + timedelta(days=6)
        wl = f"{sw.strftime('%Y-%m-%d')} to {ew.strftime('%Y-%m-%d')}"
        weekly_counts[wl] = weekly_counts.get(wl, 0) + 1
        records_by_week.setdefault(wl, []).append({'key': key, 'date': date_str})

        # Monthly bucket
        ml = d.strftime('%Y-%m')
        monthly_counts[ml] = monthly_counts.get(ml, 0) + 1
        records_by_month.setdefault(ml, []).append({'key': key, 'date': date_str})

    sorted_weeks  = sorted(weekly_counts.keys(), reverse=True)
    sorted_months = sorted(monthly_counts.keys(), reverse=True)

    all_weeks = [
        {
            'week': w,
            'count': weekly_counts[w],
            'is_current': w == cur_week_label,
            'records': sorted(records_by_week[w], key=lambda x: x['date'], reverse=True)
        }
        for w in sorted_weeks
    ]

    # Weekly breakdown inside a selected month
    weekly_in_month = {}
    if filter_month:
        for rec in records_by_month.get(filter_month, []):
            try:
                d2 = datetime.strptime(rec['date'], '%Y-%m-%d').date()
                sw2 = d2 - timedelta(days=d2.weekday())
                ew2 = sw2 + timedelta(days=6)
                wl2 = f"{sw2.strftime('%Y-%m-%d')} to {ew2.strftime('%Y-%m-%d')}"
                weekly_in_month[wl2] = weekly_in_month.get(wl2, 0) + 1
            except Exception:
                continue
        weekly_in_month = dict(sorted(weekly_in_month.items()))

    return jsonify({
        'weekly_counts':    {w: weekly_counts[w] for w in sorted_weeks},
        'monthly_counts':   {m: monthly_counts[m] for m in sorted_months},
        'all_weeks':        all_weeks,
        'current_week':     cur_week_label,
        'filter_month':     filter_month,
        'weekly_in_month':  weekly_in_month,
        'available_months': sorted_months,
    })



_pdf_lock = threading.Lock()


@app.route('/api/glance_report/pdf')
def glance_report_pdf():
    """Analytics-driven Weekly Glance Report PDF (this week in focus)."""
    import io
    from collections import Counter
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    state_f = request.args.get('state', '').strip()
    type_f  = request.args.get('el_type', '').strip()

    history = get_completion_history()
    history.pop('_updated', None)

    recs = []
    for key, date_str in history.items():
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
        except Exception:
            continue
        parts = key.split('-')
        st = parts[0] if parts else ''
        ty = parts[1] if len(parts) > 1 else ''
        if state_f and st != state_f:
            continue
        if type_f and ty != type_f:
            continue
        recs.append({'key': key, 'date': date_str, 'd': d, 'state': st, 'type': ty})

    today = datetime.now().date()
    cur_start = today - timedelta(days=today.weekday())
    cur_end   = cur_start + timedelta(days=6)
    last_start = cur_start - timedelta(days=7)
    last_end   = last_start + timedelta(days=6)

    def wstart(d):
        return d - timedelta(days=d.weekday())

    weekly = {}
    for r in recs:
        ws = wstart(r['d'])
        weekly[ws] = weekly.get(ws, 0) + 1
    weeks_sorted = sorted(weekly.keys())

    this_week_recs = [r for r in recs if cur_start <= r['d'] <= cur_end]
    this_week = len(this_week_recs)
    last_week = sum(1 for r in recs if last_start <= r['d'] <= last_end)
    total = len(recs)
    avg = (total / len(weeks_sorted)) if weeks_sorted else 0

    if this_week_recs:
        focus = this_week_recs; f_start, f_end = cur_start, cur_end; f_label = 'This Week'
    elif weeks_sorted:
        fs = weeks_sorted[-1]; f_start, f_end = fs, fs + timedelta(days=6)
        focus = [r for r in recs if f_start <= r['d'] <= f_end]; f_label = 'Latest Active Week'
    else:
        focus = []; f_start, f_end = cur_start, cur_end; f_label = 'This Week'

    state_counts = Counter(r['state'] for r in recs)
    type_counts  = Counter(r['type'] for r in recs)

    INDIGO, EMERALD, AMBER, BLUE, RED = '#6366f1', '#10b981', '#f59e0b', '#3b82f6', '#ef4444'
    DARK, GRAY, LIGHT = '#111827', '#6b7280', '#9ca3af'

    with _pdf_lock:
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.patch.set_facecolor('white')

        # Header
        fig.text(0.07, 0.965, 'Form 20 — Weekly Glance Report', fontsize=20, fontweight='bold', color=DARK)
        fig.text(0.07, 0.945, 'DB-Pushed Records · Analytical Summary', fontsize=10.5, color=GRAY)
        fig.text(0.93, 0.966, 'Generated ' + datetime.now().strftime('%d %b %Y, %H:%M'),
                 fontsize=8.5, color=LIGHT, ha='right')
        wk = f"{f_label}:  {f_start.strftime('%d %b')} - {f_end.strftime('%d %b %Y')}"
        filt = []
        if state_f: filt.append('State=' + state_f)
        if type_f:  filt.append('Type=' + type_f)
        fig.text(0.93, 0.946, wk + ('   |   ' + ', '.join(filt) if filt else ''),
                 fontsize=8.5, color=GRAY, ha='right')
        fig.add_artist(plt.Line2D([0.07, 0.93], [0.93, 0.93], color='#e5e7eb', lw=1))

        # KPI cards
        kpis = [
            ('THIS WEEK',    str(this_week), INDIGO),
            ('VS LAST WEEK', ('+' if this_week - last_week >= 0 else '') + str(this_week - last_week),
                             EMERALD if this_week >= last_week else RED),
            ('WEEKLY AVG',   f'{avg:.1f}', AMBER),
            ('CUMULATIVE',   str(total), DARK),
            ('STATES',       str(len(state_counts)), BLUE),
        ]
        n = len(kpis); x0, x1, gapw = 0.07, 0.93, 0.012
        cw = ((x1 - x0) - (n - 1) * gapw) / n
        for i, (lab, val, col) in enumerate(kpis):
            cx = x0 + i * (cw + gapw)
            ax = fig.add_axes([cx, 0.855, cw, 0.052]); ax.axis('off')
            ax.add_patch(FancyBboxPatch((0.02, 0.04), 0.96, 0.92,
                         boxstyle="round,pad=0,rounding_size=0.12", transform=ax.transAxes,
                         facecolor='#f9fafb', edgecolor='#e5e7eb', lw=0.8))
            ax.text(0.5, 0.70, lab, ha='center', va='center', fontsize=6.8, color=GRAY, fontweight='bold')
            ax.text(0.5, 0.33, val, ha='center', va='center', fontsize=15, color=col, fontweight='bold')

        gs = fig.add_gridspec(3, 2, left=0.07, right=0.93, top=0.78, bottom=0.065,
                              hspace=0.5, wspace=0.22, height_ratios=[1, 1, 1.3])

        def style(ax, title):
            ax.set_title(title, fontsize=10.5, fontweight='bold', color=DARK, loc='left', pad=8)
            for sp in ['top', 'right']:
                ax.spines[sp].set_visible(False)
            ax.spines['left'].set_color('#e5e7eb'); ax.spines['bottom'].set_color('#e5e7eb')
            ax.tick_params(colors=GRAY, labelsize=8)

        # Weekly trend
        axw = fig.add_subplot(gs[0, 0]); style(axw, 'Weekly Push Trend')
        if weeks_sorted:
            vals = [weekly[w] for w in weeks_sorted]
            axw.bar(range(len(vals)), vals, color=INDIGO, width=0.6)
            axw.set_xticks(range(len(vals)))
            axw.set_xticklabels([w.strftime('%d %b') for w in weeks_sorted], fontsize=7)
            for i, v in enumerate(vals):
                axw.text(i, v, str(v), ha='center', va='bottom', fontsize=7, color=DARK)
            axw.set_ylim(0, max(vals) * 1.25)
        else:
            axw.axis('off'); axw.text(0.5, 0.5, 'No data', ha='center', color=LIGHT)

        # State performance
        axs = fig.add_subplot(gs[0, 1]); style(axs, 'State Performance (cumulative)')
        top_states = state_counts.most_common(8)[::-1]
        if top_states:
            axs.barh([s for s, _ in top_states], [c for _, c in top_states], color=EMERALD, height=0.6)
            for i, (s, c) in enumerate(top_states):
                axs.text(c, i, ' ' + str(c), va='center', fontsize=7, color=DARK)
        else:
            axs.axis('off'); axs.text(0.5, 0.5, 'No data', ha='center', color=LIGHT)

        # Type distribution
        axt = fig.add_subplot(gs[1, 0]); style(axt, 'Election Type Distribution')
        top_types = type_counts.most_common()[::-1]
        if top_types:
            axt.barh([t for t, _ in top_types], [c for _, c in top_types], color=INDIGO, height=0.55)
            for i, (t, c) in enumerate(top_types):
                pct = (c / total * 100) if total else 0
                axt.text(c, i, f' {c} ({pct:.0f}%)', va='center', fontsize=7, color=DARK)
        else:
            axt.axis('off'); axt.text(0.5, 0.5, 'No data', ha='center', color=LIGHT)

        # Focus week by state
        axf = fig.add_subplot(gs[1, 1]); style(axf, f'{f_label} · by State')
        fc = Counter(r['state'] for r in focus)
        if fc:
            items = fc.most_common()[::-1]
            axf.barh([s for s, _ in items], [c for _, c in items], color=AMBER, height=0.6)
            for i, (s, c) in enumerate(items):
                axf.text(c, i, ' ' + str(c), va='center', fontsize=7, color=DARK)
        else:
            axf.axis('off')
            axf.text(0.5, 0.5, 'No records pushed\nin focus week', ha='center', va='center', fontsize=9, color=LIGHT)

        # Records table
        axtab = fig.add_subplot(gs[2, :]); axtab.axis('off')
        axtab.set_title(f'{f_label} · Records ({len(focus)})', fontsize=10.5, fontweight='bold',
                        color=DARK, loc='left', pad=6)
        focus_sorted = sorted(focus, key=lambda r: r['date'], reverse=True)
        cap = 24
        cell = [[r['key'], r['state'], r['type'], r['date']] for r in focus_sorted[:cap]]
        if cell:
            tab = axtab.table(cellText=cell, colLabels=['Election Key', 'State', 'Type', 'Date Pushed'],
                              cellLoc='left', loc='upper center', colWidths=[0.40, 0.16, 0.16, 0.28])
            tab.auto_set_font_size(False); tab.set_fontsize(8); tab.scale(1, 1.4)
            for (row, _ci), cellobj in tab.get_celld().items():
                cellobj.set_edgecolor('#e5e7eb')
                if row == 0:
                    cellobj.set_facecolor('#111827'); cellobj.set_text_props(color='white', fontweight='bold')
                else:
                    cellobj.set_facecolor('#ffffff' if row % 2 else '#f9fafb')
            if len(focus_sorted) > cap:
                axtab.text(0.5, 0.0, f'… and {len(focus_sorted) - cap} more records',
                           ha='center', fontsize=8, color=GRAY, transform=axtab.transAxes)
        else:
            axtab.text(0.5, 0.6, 'No records pushed in the focus week.', ha='center', fontsize=10, color=LIGHT)

        fig.text(0.07, 0.03, 'Form 20 Backlog Tracker · Confidential', fontsize=7.5, color=LIGHT)

        out_fmt = 'png' if request.args.get('fmt', '').lower() == 'png' else 'pdf'
        buf = io.BytesIO()
        fig.savefig(buf, format=out_fmt, facecolor='white', dpi=130 if out_fmt == 'png' else None)
        plt.close(fig)

    buf.seek(0)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    if out_fmt == 'png':
        return send_file(buf, mimetype='image/png')
    return send_file(buf, mimetype='application/pdf', as_attachment=True,
                     download_name=f'Glance_Report_{f_start.strftime("%Y%m%d")}_{ts}.pdf')


@app.route('/api/filters')
def get_filters():
    conn = get_db()
    rows = conn.execute('SELECT state, state_name, el_type, el_year, COUNT(*) as cnt FROM records GROUP BY state, state_name, el_type, el_year').fetchall()
    conn.close()
    
    metadata = {}
    state_names = {}
    for r in rows:
        s = r['state']
        s_name = r['state_name']
        t = r['el_type']
        y = r['el_year']
        
        state_names[s] = s_name
        
        if s not in metadata:
            metadata[s] = {}
        if t not in metadata[s]:
            metadata[s][t] = {}
        metadata[s][t][y] = r['cnt']
        
    return jsonify({
        'metadata': metadata,
        'state_names': state_names
    })


@app.route('/api/sync-rds', methods=['POST'])
def sync_rds():
    """Syncs the 'in_db' status from AWS RDS Postgres."""
    # Force an immediate JSON sync
    fetch_live_json_sync()
    
    rds_conn = get_rds_db()
    if not rds_conn:
        return jsonify({'success': False, 'message': 'AWS RDS credentials not configured'}), 400
        
    try:
        # Fetch distinct state_abb, el_type, and el_year combinations
        with rds_conn.cursor() as cur:
            cur.execute("SELECT DISTINCT state_abb, el_type, el_year FROM public.ac_election_mapping")
            rds_data = cur.fetchall()
            
        # rds_data contains tuples of (state_abb, el_type, el_year), e.g., ('MH', 'AE-BP', 2010)
        rds_set = set((str(row[0]).strip(), str(row[1]).strip(), str(row[2]).strip()) for row in rds_data if row[0] and row[1] and row[2])
        
        turso_conn = get_db()
        turso_records = turso_conn.execute("SELECT id, state, el_type, el_year FROM records").fetchall()
        
        updates = []
        for rec in turso_records:
            state = str(rec['state']).strip()
            el_type = str(rec['el_type']).strip()
            el_year = str(rec['el_year']).strip()
            
            # If this exact combination exists in RDS, mark it as in_db
            if (state, el_type, el_year) in rds_set:
                updates.append(rec['id'])
                
        if updates:
            # Batch update in Turso
            placeholders = ','.join(['?'] * len(updates))
            turso_conn.execute(f"UPDATE records SET db_status = 'in_db', overall_status = 'completed', retro_ready = 1 WHERE id IN ({placeholders})", updates)
            
            # Log this action
            for rec_id in updates:
                turso_conn.execute(
                    "INSERT INTO activity_log (record_key, action, old_value, new_value, changed_by) VALUES (?, ?, ?, ?, ?)",
                    [f"ID:{rec_id}", 'sync_rds', 'not_in_db', 'in_db', 'System Sync']
                )
                
        return jsonify({'success': True, 'synced_count': len(updates), 'message': f'Successfully synced {len(updates)} records from AWS RDS.'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        rds_conn.close()


@app.route('/api/export', methods=['POST'])
def export_records():
    import openpyxl
    data       = request.get_json() or {}
    record_ids = data.get('ids', [])
    fmt        = data.get('format', 'csv')

    conn = get_db()
    if record_ids:
        ph   = ','.join('?' * len(record_ids))
        rows = conn.execute(f'SELECT * FROM records WHERE id IN ({ph})', record_ids).fetchall()
    else:
        rows = conn.execute('SELECT * FROM records ORDER BY state, el_type, el_year').fetchall()
    live_extracted = get_live_extracted_set()
    download_report = get_download_report_dict()
    records = []
    for r in rows:
        r_dict = dict(r)
        r_dict = apply_dynamic_status(r_dict, live_extracted, download_report)
        records.append(r_dict)
    conn.close()

    # Friendly column names for export
    EXPORT_COLS = [
        ('state', 'State'),
        ('state_name', 'State Name'),
        ('el_type', 'Election Type'),
        ('el_year', 'Election Year'),
        ('overall_status', 'Status'),
        ('is_sir_state', 'SIR State'),
        ('download_status', 'Download Status'),
        ('extraction_status', 'Extraction Status'),
        ('db_status', 'DB Status'),
        ('wip', 'WIP'),
        ('assigned_to', 'Assigned To'),
        ('remark', 'Remark'),
        ('retro_ready', 'Retro Ready'),
        ('last_updated', 'Last Updated'),
    ]

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    if fmt == 'csv':
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[c[1] for c in EXPORT_COLS])
        writer.writeheader()
        for rec in records:
            writer.writerow({label: rec.get(col) for col, label in EXPORT_COLS})
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'form20_export_{ts}.csv',
        )

    elif fmt == 'xlsx':
        output = io.BytesIO()
        wb     = openpyxl.Workbook()
        ws     = wb.active
        ws.title = 'Form 20 Export'

        # Import styles locally
        import openpyxl.styles as styles
        
        header_fill = styles.PatternFill('solid', fgColor='059669') # emerald-600
        header_font = styles.Font(color='FFFFFF', bold=True, size=12)
        center_align = styles.Alignment(horizontal='center', vertical='center')
        wrap_align = styles.Alignment(wrap_text=True, vertical='top')
        thin_border = styles.Border(
            left=styles.Side(style='thin', color='E5E7EB'),
            right=styles.Side(style='thin', color='E5E7EB'),
            top=styles.Side(style='thin', color='E5E7EB'),
            bottom=styles.Side(style='thin', color='E5E7EB')
        )

        # Header row
        headers = [label for _, label in EXPORT_COLS]
        ws.append(headers)
        
        ws.row_dimensions[1].height = 25
        ws.freeze_panes = 'A2'

        for cell in ws[1]:
            cell.font      = header_font
            cell.fill      = header_fill
            cell.alignment = center_align
            cell.border    = thin_border

        for r_idx, rec in enumerate(records, start=2):
            ws.append([rec.get(col) for col, _ in EXPORT_COLS])
            for cell in ws[r_idx]:
                cell.alignment = wrap_align
                cell.border = thin_border

        # Auto-width calculation
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            # Add padding and scaling for proportional fonts, cap at 50 wide
            ws.column_dimensions[col[0].column_letter].width = min((max_len * 1.15) + 4, 50)

        wb.save(output)
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'form20_export_{ts}.xlsx',
        )

    return jsonify({'error': 'Unsupported format'}), 400


# ── Retro Export (live from AWS RDS: election_result ⋈ election) ─────────────

RETRO_META_JSON_PATH = os.path.join(BASE_DIR, 'retro_metadata.json')

# Canonical column order — mirrors the historical "SELECT er.*, e.*" shape so the
# exported file stays compatible with the previous RETRO.csv (el_id appears twice).
RETRO_HEADERS = [
    'el_res_id', 'ca_full_name', 'party_abb', 'party_id', 'el_vote_count',
    'el_vote_perc', 'el_rank', 'el_id', 'ac_no', 'state_abb',
    'original_ca_full_name', 'original_party_abb', 'caste', 'caste_category',
    'gender', 'age', 'incumbency', 'el_id', 'el_year', 'el_type',
]

RETRO_SELECT = (
    "SELECT er.el_res_id, er.ca_full_name, er.party_abb, er.party_id, er.el_vote_count, "
    "er.el_vote_perc, er.el_rank, er.el_id, er.ac_no, er.state_abb, "
    "er.original_ca_full_name, er.original_party_abb, er.caste, er.caste_category, "
    "er.gender, er.age, er.incumbency, e.el_id, e.el_year, e.el_type "
    "FROM election_result er JOIN election e ON er.el_id = e.el_id"
)

retro_metadata_cache = None


def fetch_retro_metadata_sync():
    """Build {state: {el_type: {year: count}}} live from RDS. Full scan — cached."""
    conn = get_rds_db()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT er.state_abb, e.el_type, e.el_year, COUNT(*) "
            "FROM election_result er JOIN election e ON er.el_id = e.el_id "
            "GROUP BY er.state_abb, e.el_type, e.el_year"
        )
        meta = {}
        for state, el_type, el_year, cnt in cur.fetchall():
            if state is None or el_type is None or el_year is None:
                continue
            s, t, y = str(state).strip(), str(el_type).strip(), str(el_year).strip()
            meta.setdefault(s, {}).setdefault(t, {})[y] = cnt
        try:
            with open(RETRO_META_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(meta, f)
        except Exception:
            pass
        return meta
    except Exception as e:
        print(f"fetch_retro_metadata_sync error: {e}")
        return None
    finally:
        conn.close()


def get_retro_metadata_dict():
    """Return cached retro metadata, falling back to disk, then a one-time live build."""
    global retro_metadata_cache
    if retro_metadata_cache is not None:
        return retro_metadata_cache
    if os.path.exists(RETRO_META_JSON_PATH):
        try:
            with open(RETRO_META_JSON_PATH, 'r', encoding='utf-8') as f:
                retro_metadata_cache = json.load(f)
                return retro_metadata_cache
        except Exception:
            pass
    retro_metadata_cache = fetch_retro_metadata_sync() or {}
    return retro_metadata_cache


def refresh_retro_metadata_loop():
    global retro_metadata_cache
    while True:
        meta = fetch_retro_metadata_sync()
        if meta is not None:
            retro_metadata_cache = meta
        time.sleep(600)  # refresh every 10 minutes — retro data keeps updating


retro_meta_thread = threading.Thread(target=refresh_retro_metadata_loop, daemon=True)
retro_meta_thread.start()


@app.route('/api/retro/metadata')
def retro_metadata():
    return jsonify(get_retro_metadata_dict())


@app.route('/api/retro/export')
def export_retro():
    import io, csv, openpyxl
    state   = request.args.get('state', '').strip()
    el_type = request.args.get('el_type', '').strip()
    year    = request.args.get('year', '').strip()
    fmt     = request.args.get('format', 'csv').strip().lower()

    if not state or not el_type or not year:
        return jsonify({'error': 'Missing required filters: state, el_type, year'}), 400
    try:
        year_int = int(year)
    except ValueError:
        return jsonify({'error': 'Invalid year parameter'}), 400

    conn = get_rds_db()
    if not conn:
        return jsonify({'error': 'AWS RDS not configured — cannot export live retro data'}), 503
    try:
        cur = conn.cursor()
        cur.execute(
            RETRO_SELECT + " WHERE er.state_abb = %s AND e.el_type = %s AND e.el_year = %s "
            "ORDER BY er.ac_no, er.el_rank",
            (state, el_type, year_int),
        )
        rows = cur.fetchall()
    except Exception as e:
        return jsonify({'error': f'RDS query failed: {e}'}), 500
    finally:
        conn.close()

    if not rows:
        return jsonify({'error': 'No retro data found for this filter combination.'}), 404

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"Retro_{state}_{el_type}_{year}_{ts}"

    if fmt == 'xlsx':
        from openpyxl.styles import Font, PatternFill
        output = io.BytesIO()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Retro Data"
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        ws.append(RETRO_HEADERS)
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
        for row in rows:
            ws.append(list(row))
        ws.freeze_panes = "A2"
        wb.save(output)
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True, download_name=f"{filename}.xlsx",
        )
    else:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(RETRO_HEADERS)
        writer.writerows(rows)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv', as_attachment=True, download_name=f"{filename}.csv",
        )


@app.route('/api/retro/filters')
def get_retro_filters():
    meta = get_retro_metadata_dict()
    state_param   = request.args.get('state', '').strip() or None
    el_type_param = request.args.get('el_type', '').strip() or None

    all_states, all_el_types, all_years = set(), set(), set()
    for s, types in meta.items():
        all_states.add(s)
        for t, years in types.items():
            if state_param is None or s == state_param:
                all_el_types.add(t)
            if (state_param is None or s == state_param) and (el_type_param is None or t == el_type_param):
                all_years.update(years.keys())

    def year_key(y):
        try:
            return int(y)
        except ValueError:
            return 0

    return jsonify({
        'states':   sorted(all_states),
        'el_types': sorted(all_el_types),
        'years':    sorted(all_years, key=year_key),
    }), 200


@app.route('/api/retro/count')
def retro_count():
    state   = request.args.get('state', '').strip()
    el_type = request.args.get('el_type', '').strip()
    year    = request.args.get('year', '').strip()
    if year:
        try:
            yi = int(year)
            if not (1900 <= yi <= 2100):
                raise ValueError
        except ValueError:
            return jsonify({'error': 'Invalid year parameter'}), 400

    meta = get_retro_metadata_dict()
    count = 0
    for s, types in meta.items():
        if state and s != state:
            continue
        for t, years in types.items():
            if el_type and t != el_type:
                continue
            for y, c in years.items():
                if year and y != year:
                    continue
                count += c
    return jsonify({'count': count})


@app.route('/api/reload', methods=['POST'])
def reload_database():
    try:
        from init_db import init_database
        init_database(EXCEL_PATH, DB_PATH)
        return jsonify({'success': True, 'message': 'Database reloaded from Excel'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        print("No database found — initialising from Excel...")
        from init_db import init_database
        init_database(EXCEL_PATH, DB_PATH)

    print("\n  Form 20 Backlog Dashboard")
    print("  Running locally at: http://127.0.0.1:5050")
    print("  Network listening at: http://0.0.0.0:5050\n")
    app.run(host='0.0.0.0', debug=True, port=5050, use_reloader=False)
