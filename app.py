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

from flask import Flask, jsonify, redirect, render_template, request, send_file, session, url_for
from functools import wraps
from authlib.integrations.flask_client import OAuth
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev_secret_key_change_me_in_production')

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user'):
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

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

# ── On-demand RDS cache: refresh on reload, NOT by background polling ─────────
# Dashboard data is served from cache (memory → disk) for an instant response.
# A reload only touches RDS when the cached copy is older than CACHE_TTL_SECONDS,
# and even then the refresh runs once in the background (single-flight) so the
# request never blocks and concurrent reloads collapse into a single DB hit.
# If nobody opens the dashboard, RDS is never queried — load tracks real usage.
CACHE_TTL_SECONDS = 300   # 5 min — serve cache without hitting RDS within this window

_cache_meta_lock   = threading.Lock()
_last_refresh_ts   = {}    # name -> epoch seconds of last successful refresh
_refresh_in_flight = set() # names whose background refresh is currently running


def cache_is_fresh(name):
    """True if `name` was refreshed within the TTL (no DB hit needed)."""
    return (time.time() - _last_refresh_ts.get(name, 0)) < CACHE_TTL_SECONDS


def trigger_refresh(name, builder):
    """Stale-while-revalidate, single-flight. If `name`'s cache is stale and no
    refresh is already running, execute `builder()` once in a daemon thread.
    Returns immediately — the request is always served from the existing cache."""
    with _cache_meta_lock:
        if cache_is_fresh(name) or name in _refresh_in_flight:
            return
        _refresh_in_flight.add(name)

    def _run():
        try:
            builder()
            with _cache_meta_lock:
                _last_refresh_ts[name] = time.time()
        except Exception as e:
            print(f'[cache:{name}] refresh failed: {e}')
        finally:
            with _cache_meta_lock:
                _refresh_in_flight.discard(name)

    threading.Thread(target=_run, daemon=True, name=f'refresh-{name}').start()


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

# Canonical Assembly Constituency (AC) counts per state/UT — mirrors STATE_AC_COUNTS in static/app.js
STATE_AC_COUNTS = {
    'AP': 175, 'AR': 60,  'AS': 126, 'BR': 243, 'CG': 90,  'CT': 90,  'GA': 40,
    'GJ': 182, 'HR': 90,  'HP': 68,  'JH': 81,  'KA': 224, 'KL': 140, 'MP': 230,
    'MH': 288, 'MN': 60,  'ML': 60,  'MZ': 40,  'NL': 60,  'OR': 147, 'PB': 117,
    'RJ': 200, 'SK': 32,  'TN': 234, 'TS': 119, 'TR': 60,  'UP': 403, 'UK': 70,
    'WB': 294, 'DL': 70,  'PY': 30,  'JK': 90,  'LD': 1,   'AN': 1,   'CH': 1,
}

# ── Live AWS Caching ────────────────────────────────────────────────────────

LIVE_JSON_PATH = os.path.join(BASE_DIR, 'live_extracted.json')
AC_PC_JSON_PATH = os.path.join(BASE_DIR, 'ac_pc_extracted.json')

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
            
            cur.execute("""
                SELECT DISTINCT state_abb, el_type, el_year 
                FROM public.ac_election_mapping
            """)
            rds_acpc = cur.fetchall()
        
        extracted_list = [{"state": str(r[0]).strip(), "el_type": str(r[1]).strip(), "el_year": str(r[2]).strip()} for r in rds_data if r[0] and r[1] and r[2]]
        acpc_list = [{"state": str(r[0]).strip(), "el_type": str(r[1]).strip(), "el_year": str(r[2]).strip()} for r in rds_acpc if r[0] and r[1] and r[2]]
        
        with open(LIVE_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(extracted_list, f)
            
        with open(AC_PC_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(acpc_list, f)
            
        # Sync missing records to DB so they appear as 'Remaining' (missing)
        try:
            conn = get_db()
            existing_recs = conn.execute("SELECT key FROM records").fetchall()
            existing_keys = {r['key'] for r in existing_recs}
            
            inserted = 0
            from datetime import datetime
            today = datetime.now().strftime('%Y-%m-%d')
            now_full = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            for item in acpc_list:
                key = f"{item['state']}-{item['el_type']}-{item['el_year']}"
                if key not in existing_keys:
                    conn.execute('''
                        INSERT INTO records (state, el_type, el_year, key, overall_status, download_status, extraction_status, db_status, wip, last_updated, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (item['state'], item['el_type'], int(item['el_year']), key, 'missing', 'missing', 'pending', 'not_in_db', 0, today, now_full))
                    inserted += 1
            if inserted > 0:
                conn.commit()
            conn.close()
            if inserted > 0:
                print(f"Inserted {inserted} new AC-PC mapping elections into dashboard DB.")
        except Exception as db_e:
            print(f"Error inserting AC-PC mappings to SQLite: {db_e}")
            
    except Exception as e:
        print(f"Background thread error fetching AWS data: {e}")
    finally:
        rds_conn.close()

def _build_live():
    """Refresh the Form 20 / AC-PC JSON snapshots and sync any newly-discovered
    elections into the operational DB. Triggered on dashboard/listing reload via
    trigger_refresh('live', ...) — no longer polled every 60s."""
    fetch_live_json_sync()

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
        r_dict['overall_status'] = 'db_pushed'
        r_dict['db_status'] = 'in_db'
        
    return r_dict


# ── Routes ──────────────────────────────────────────────────────────────────

@app.before_request
def require_login():
    allowed_routes = ['login_page', 'login', 'auth_callback', 'static']
    if request.endpoint not in allowed_routes:
        if not session.get('user'):
            if request.path.startswith('/api/'):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for('login_page'))

@app.route('/login_page')
def login_page():
    if session.get('user'):
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/login')
def login():
    redirect_uri = url_for('auth_callback', _external=True, _scheme='https')
    return google.authorize_redirect(redirect_uri)

@app.route('/auth/callback')
def auth_callback():
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    # Optional: You can enforce allowed domains/emails here
    session['user'] = user_info
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login_page'))

@app.route('/')
def index():
    user = session.get('user')
    return render_template('index.html', user=user)


@app.route('/api/records', methods=['GET'])
def get_records():
    trigger_refresh('live', _build_live)   # refresh RDS snapshot on reload (if stale)
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

        if status == 'remaining':
            if r_dict['overall_status'] in ('db_pushed', 'completed'):
                continue
        elif status and r_dict['overall_status'] != status:
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

    # ── Stamp completion history only on explicit manual push ────────────────
    new_status = updates.get('overall_status', '')
    if new_status in ('db_pushed', 'completed'):
        key = f"{r_dict['state']}-{r_dict['el_type']}-{r_dict['el_year']}"
        if key not in history:
            history[key] = datetime.now().strftime('%Y-%m-%d')
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
    type_dict  = {}
    year_dict  = {}   # el_year → {total, completed}

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
                'missing': 0,
                'downloaded': 0
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
            
        # year-level tracking
        yr = r_dict.get('el_year')
        if yr is not None:
            if yr not in year_dict:
                year_dict[yr] = {'total': 0, 'completed': 0}
            year_dict[yr]['total'] += 1

        if effective_status in ('completed', 'db_pushed'):
            state_dict[state]['completed'] += 1
            type_dict[el_type_base]['completed'] += 1
            if yr is not None:
                year_dict[yr]['completed'] += 1
        if effective_status == 'extracted':
            state_dict[state]['extracted'] += 1
        if effective_status == 'missing':
            state_dict[state]['missing'] += 1
            type_dict[el_type_base]['missing'] += 1
        if effective_status == 'downloaded':
            state_dict[state]['downloaded'] += 1
            type_dict[el_type_base]['downloaded'] += 1

    total = sum(by_status.values())
    state_rows = [state_dict[s] for s in sorted(state_dict.keys())]

    total_years  = len(year_dict)
    years_in_db  = sum(1 for y in year_dict.values() if y['completed'] > 0)

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
        'bottlenecks': bottlenecks,
        'total_years': total_years,
        'years_in_db': years_in_db,
        'year_detail': sorted(year_dict.items()),
    })


@app.route('/api/glance_report')
def glance_report():
    history = get_completion_history()
    history.pop('_updated', None)

    filter_month   = request.args.get('month',   '').strip()
    filter_week    = request.args.get('week',    '').strip()   # e.g. "2026-06-01"  (week start date)
    filter_state   = request.args.get('state',   '').strip()
    filter_el_type = request.args.get('el_type', '').strip()
    hide_bp  = request.args.get('hide_bp',  '') == '1'
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
        k_state   = parts[0] if parts else ''
        # key format: STATE-ELTYPE-YEAR  or  STATE-ELTYPE-BP-YEAR
        # year is always the last segment; el_type is everything between state and year
        k_el_type = '-'.join(parts[1:-1]) if len(parts) >= 3 else ''

        if filter_state and k_state != filter_state:
            continue
        if filter_el_type and k_el_type != filter_el_type:
            continue
        if hide_bp and '-BP' in key:
            continue
        if sir_only and k_state not in sir_states:
            continue
        # Week filter: only records whose week starts on filter_week date
        if filter_week:
            try:
                fw = datetime.strptime(filter_week, '%Y-%m-%d').date()
                rec_week = d - timedelta(days=d.weekday())
                if rec_week != fw:
                    continue
            except Exception:
                pass

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

    # Glance Report accordion and trend chart show exactly the last 4 calendar weeks
    display_weeks = []
    for i in range(4):
        w_start = cur_week_start - timedelta(days=7*i)
        w_end = w_start + timedelta(days=6)
        wl = f"{w_start.strftime('%Y-%m-%d')} to {w_end.strftime('%Y-%m-%d')}"
        display_weeks.append(wl)
    
    # Ensure they exist in our dictionaries with 0 count if empty
    for w in display_weeks:
        weekly_counts.setdefault(w, 0)
        records_by_week.setdefault(w, [])

    all_weeks = [
        {
            'week': w,
            'count': weekly_counts[w],
            'is_current': w == cur_week_label,
            'records': sorted(records_by_week[w], key=lambda x: x['date'], reverse=True)
        }
        for w in display_weeks
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

    # ── All-time weekly counts (ignores filter_week so the velocity chart always
    #    shows full history context, not just the one filtered week) ───────────
    if filter_week:
        all_time_weekly = {}
        for key2, date_str2 in history.items():
            try:
                d2 = datetime.strptime(date_str2, '%Y-%m-%d').date()
            except Exception:
                continue
            parts2 = key2.split('-')
            k_st2 = parts2[0] if parts2 else ''
            k_et2 = '-'.join(parts2[1:-1]) if len(parts2) >= 3 else ''
            if filter_state   and k_st2 != filter_state:   continue
            if filter_el_type and k_et2 != filter_el_type: continue
            if hide_bp and '-BP' in key2: continue
            if sir_only and k_st2 not in sir_states: continue
            sw2 = d2 - timedelta(days=d2.weekday())
            ew2 = sw2 + timedelta(days=6)
            wl2 = f"{sw2.strftime('%Y-%m-%d')} to {ew2.strftime('%Y-%m-%d')}"
            all_time_weekly[wl2] = all_time_weekly.get(wl2, 0) + 1
    else:
        all_time_weekly = weekly_counts

    all_time_sorted = sorted(all_time_weekly.keys(), reverse=True)

    # ── Week-over-week comparison ─────────────────────────────────────────────
    # When a specific week is filtered, compare that week vs the one before it.
    # Otherwise compare the current calendar week vs last week.
    if filter_week:
        try:
            fw       = datetime.strptime(filter_week, '%Y-%m-%d').date()
            fw_end   = fw + timedelta(days=6)
            fw_label = f"{fw.strftime('%Y-%m-%d')} to {fw_end.strftime('%Y-%m-%d')}"
            pfw      = fw - timedelta(days=7)
            pfw_end  = pfw + timedelta(days=6)
            pfw_label= f"{pfw.strftime('%Y-%m-%d')} to {pfw_end.strftime('%Y-%m-%d')}"
            this_week_count  = weekly_counts.get(fw_label, 0)
            last_week_count  = all_time_weekly.get(pfw_label, 0)
            effective_cur_week = fw_label  # Period label shows the selected week
        except Exception:
            this_week_count  = 0
            last_week_count  = 0
            effective_cur_week = cur_week_label
    else:
        this_w_start = cur_week_start
        last_w_start = cur_week_start - timedelta(days=7)
        this_w_label = f"{this_w_start.strftime('%Y-%m-%d')} to {(this_w_start+timedelta(days=6)).strftime('%Y-%m-%d')}"
        last_w_label = f"{last_w_start.strftime('%Y-%m-%d')} to {(last_w_start+timedelta(days=6)).strftime('%Y-%m-%d')}"
        this_week_count  = weekly_counts.get(this_w_label, 0)
        last_week_count  = weekly_counts.get(last_w_label, 0)
        effective_cur_week = cur_week_label

    # Build available_weeks list from all-time data (most recent first)
    available_weeks = [
        {
            'label': w,
            'start': w[:10],
            'display': datetime.strptime(w[:10], '%Y-%m-%d').strftime('%d %b') + ' – ' +
                       datetime.strptime(w[14:24], '%Y-%m-%d').strftime('%d %b %Y'),
            'count': all_time_weekly[w],
            'is_current': w == cur_week_label,
        }
        for w in all_time_sorted
    ]

    return jsonify({
        'weekly_counts':     {w: weekly_counts[w] for w in display_weeks},   # filtered (accordion)
        'all_weekly_counts': {w: all_time_weekly[w] for w in all_time_sorted},  # full history (velocity chart)
        'monthly_counts':    {m: monthly_counts[m] for m in sorted_months},
        'all_weeks':         all_weeks,
        'current_week':      effective_cur_week,   # selected week label when filtered
        'filter_month':      filter_month,
        'filter_week':       filter_week,
        'weekly_in_month':   weekly_in_month,
        'available_months':  sorted_months,
        'available_weeks':   available_weeks,
        'this_week_count':   this_week_count,
        'last_week_count':   last_week_count,
        'wow_delta':         this_week_count - last_week_count,
    })



_pdf_lock = threading.Lock()


@app.route('/api/glance_report/pdf')
def glance_report_pdf():
    """Two-page management PDF:
       Page 1 — Executive summary + push velocity + pipeline status + analysis.
       Page 2 — State × Year completed elections detail table.
    """
    import io
    from collections import Counter
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyBboxPatch
    from matplotlib.backends.backend_pdf import PdfPages

    state_f = request.args.get('state', '').strip()
    type_f  = request.args.get('el_type', '').strip()
    out_fmt = 'png' if request.args.get('fmt', '').lower() == 'png' else 'pdf'

    # ── 1. Completion-history data ────────────────────────────────────────────
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
        yr = parts[-1] if len(parts) >= 2 else ''
        ty = '-'.join(parts[1:-1]) if len(parts) >= 3 else ''
        # BP filter
        if '-BP' in ty: continue
        if state_f and st != state_f: continue
        if type_f  and ty != type_f:  continue
        recs.append({'key': key, 'date': date_str, 'd': d, 'state': st, 'type': ty, 'year': yr})

    today      = datetime.now().date()
    cur_start  = today - timedelta(days=today.weekday())
    cur_end    = cur_start + timedelta(days=6)
    last_start = cur_start - timedelta(days=7)
    last_end   = last_start + timedelta(days=6)

    def wstart(d): return d - timedelta(days=d.weekday())

    weekly_all = {}
    for r in recs:
        ws = wstart(r['d'])
        weekly_all[ws] = weekly_all.get(ws, 0) + 1
    all_weeks_sorted = sorted(weekly_all.keys())

    last4 = all_weeks_sorted[-4:] if len(all_weeks_sorted) >= 4 else all_weeks_sorted

    this_week_recs = [r for r in recs if cur_start <= r['d'] <= cur_end]
    this_week  = len(this_week_recs)
    last_week  = sum(1 for r in recs if last_start <= r['d'] <= last_end)
    total      = len(recs)
    avg        = (total / len(all_weeks_sorted)) if all_weeks_sorted else 0

    if this_week_recs:
        f_start, f_end = cur_start, cur_end; f_label = 'This Week'
    elif all_weeks_sorted:
        fs = all_weeks_sorted[-1]; f_start, f_end = fs, fs + timedelta(days=6); f_label = 'Latest Active Week'
    else:
        f_start, f_end = cur_start, cur_end; f_label = 'This Week'

    # Records in the focus period (latest active week)
    focus_recs = sorted([r for r in recs if f_start <= r['d'] <= f_end], key=lambda x: x['date'])

    state_counts = Counter(r['state'] for r in recs)
    type_counts  = Counter(r['type']  for r in recs)

    # ── 2. Pipeline status from SQLite ───────────────────────────────────────
    try:
        conn = get_db()
        all_db_recs = conn.execute(
            "SELECT overall_status, COUNT(*) c FROM records WHERE el_type NOT LIKE '%-BP' GROUP BY overall_status"
        ).fetchall()
        conn.close()
        by_status = {dict(r)['overall_status']: dict(r)['c'] for r in all_db_recs}
    except Exception:
        by_status = {}
    db_total      = sum(by_status.values())
    db_pushed     = by_status.get('db_pushed', 0) + by_status.get('completed', 0)
    db_downloaded = by_status.get('downloaded', 0)
    db_extracted  = by_status.get('extracted', 0)
    db_missing    = by_status.get('missing', 0)
    db_pct        = round(db_pushed / db_total * 100) if db_total else 0

    # ── 3. Monthly trend ─────────────────────────────────────────────────────
    monthly = {}
    for r in recs:
        ml = r['d'].strftime('%Y-%m')
        monthly[ml] = monthly.get(ml, 0) + 1
    sorted_months = sorted(monthly.keys())

    # ── Colour palette ────────────────────────────────────────────────────────
    INDIGO    = '#6366f1'
    EMERALD   = '#10b981'
    AMBER     = '#f59e0b'
    BLUE      = '#3b82f6'
    RED       = '#ef4444'
    VIOLET    = '#7c3aed'
    DARK      = '#0f172a'
    SLATE     = '#1e293b'
    GRAY      = '#64748b'
    MUTED     = '#94a3b8'
    LIGHT     = '#cbd5e1'
    BORDER    = '#e2e8f0'
    BG_LIGHT  = '#f8fafc'
    BG_CARD   = '#f1f5f9'
    TYPE_COL  = {'AE': INDIGO, 'GE': BLUE}

    STATE_NAMES = {
        'AP':'Andhra Pradesh','AR':'Arunachal Pradesh','AS':'Assam','BR':'Bihar',
        'CG':'Chhattisgarh','CT':'Chhattisgarh','GA':'Goa','GJ':'Gujarat','HR':'Haryana',
        'HP':'Himachal Pradesh','JH':'Jharkhand','KA':'Karnataka','KL':'Kerala',
        'MP':'Madhya Pradesh','MH':'Maharashtra','MN':'Manipur','ML':'Meghalaya',
        'MZ':'Mizoram','NL':'Nagaland','OR':'Odisha','PB':'Punjab','RJ':'Rajasthan',
        'SK':'Sikkim','TN':'Tamil Nadu','TR':'Tripura','UP':'Uttar Pradesh',
        'UK':'Uttarakhand','WB':'West Bengal','TS':'Telangana','DL':'Delhi',
        'JK':'Jammu & Kashmir','LA':'Ladakh','AN':'Andaman & Nicobar',
        'CH':'Chandigarh','PY':'Puducherry','LD':'Lakshadweep',
    }

    def _style_ax(ax, title):
        ax.set_title(title, fontsize=8.5, fontweight='bold', color=DARK, loc='left', pad=5)
        for sp in ['top', 'right']:
            ax.spines[sp].set_visible(False)
        ax.spines['left'].set_color(BORDER)
        ax.spines['bottom'].set_color(BORDER)
        ax.tick_params(colors=GRAY, labelsize=7)

    def _header_band(fig, y_bottom, height, title, subtitle=None, right_line1=None, right_line2=None):
        """Draw a dark header band spanning the full figure width."""
        ax = fig.add_axes([0, y_bottom, 1, height])
        ax.set_facecolor(SLATE)
        ax.axis('off')
        # left accent stripe
        ax.add_patch(mpatches.Rectangle((0, 0), 0.006, 1, facecolor=EMERALD,
                                        transform=ax.transAxes, clip_on=True))
        ax.text(0.025, 0.72, 'PROJECT CLEAN ROOM', fontsize=7, fontweight='bold',
                color=MUTED, transform=ax.transAxes, va='center', family='monospace')
        ax.text(0.025, 0.28, title, fontsize=13, fontweight='bold',
                color='white', transform=ax.transAxes, va='center')
        if subtitle:
            ax.text(0.025 + 0.38, 0.28, subtitle, fontsize=9, color=LIGHT,
                    transform=ax.transAxes, va='center')
        if right_line1:
            ax.text(0.98, 0.70, right_line1, fontsize=7.5, color=MUTED,
                    transform=ax.transAxes, ha='right', va='center')
        if right_line2:
            ax.text(0.98, 0.28, right_line2, fontsize=8.5, color=LIGHT,
                    transform=ax.transAxes, ha='right', va='center')

    def _footer_band(fig, page_label, gen_ts):
        ax = fig.add_axes([0, 0, 1, 0.030])
        ax.set_facecolor(BG_LIGHT)
        ax.axis('off')
        ax.axhline(y=1.0, color=BORDER, lw=0.8)
        ax.text(0.05, 0.45, 'Project Clean Room  ·  Confidential — Internal Use Only',
                fontsize=7, color=MUTED, transform=ax.transAxes, va='center')
        ax.text(0.95, 0.45, f'{page_label}  ·  {gen_ts}',
                fontsize=7, color=MUTED, transform=ax.transAxes, ha='right', va='center')

    def _exec_kpi(fig, x, y, w, h, label, value, color, sub=None):
        """Large executive KPI card."""
        ax = fig.add_axes([x, y, w, h])
        ax.axis('off')
        # card background
        ax.add_patch(FancyBboxPatch((0.04, 0.04), 0.92, 0.92,
            boxstyle='round,pad=0.02,rounding_size=0.05',
            facecolor='white', edgecolor=BORDER, lw=0.9,
            transform=ax.transAxes, clip_on=True))
        # top accent bar
        ax.add_patch(mpatches.Rectangle((0.04, 0.86), 0.92, 0.1,
            facecolor=color, alpha=0.12, transform=ax.transAxes, clip_on=True))
        ax.add_patch(mpatches.Rectangle((0.04, 0.86), 0.14, 0.1,
            facecolor=color, transform=ax.transAxes, clip_on=True))
        ax.text(0.50, 0.62, str(value), ha='center', va='center',
                fontsize=18, color=color, fontweight='black',
                transform=ax.transAxes)
        ax.text(0.50, 0.32, label, ha='center', va='center',
                fontsize=6.5, color=GRAY, fontweight='bold',
                transform=ax.transAxes)
        if sub:
            ax.text(0.50, 0.14, sub, ha='center', va='center',
                    fontsize=6, color=MUTED, transform=ax.transAxes)

    def _mini_kpi(fig, x, y, w, h, label, value, color, sub=None):
        """Smaller pipeline-stage KPI card."""
        ax = fig.add_axes([x, y, w, h])
        ax.axis('off')
        ax.add_patch(FancyBboxPatch((0.03, 0.03), 0.94, 0.94,
            boxstyle='round,pad=0.02,rounding_size=0.05',
            facecolor=BG_CARD, edgecolor=BORDER, lw=0.7,
            transform=ax.transAxes, clip_on=True))
        # left accent
        ax.add_patch(mpatches.Rectangle((0.03, 0.03), 0.055, 0.94,
            facecolor=color, transform=ax.transAxes, clip_on=True))
        ax.text(0.55, 0.72, label, ha='center', va='center',
                fontsize=6, color=GRAY, fontweight='bold', transform=ax.transAxes)
        ax.text(0.55, 0.38, str(value), ha='center', va='center',
                fontsize=13, color=color, fontweight='black', transform=ax.transAxes)
        if sub:
            ax.text(0.55, 0.12, sub, ha='center', va='center',
                    fontsize=5.5, color=MUTED, transform=ax.transAxes)

    with _pdf_lock:
        buf = io.BytesIO()
        gen_ts  = datetime.now().strftime('%d %b %Y, %H:%M')
        wk_str  = f'{f_start.strftime("%d %b")} – {f_end.strftime("%d %b %Y")}'
        filt_str = ', '.join(
            (['State: ' + state_f] if state_f else []) +
            (['Type: ' + type_f]   if type_f  else [])
        )

        with PdfPages(buf) as pdf:

            # ══════════════════════════════════════════════════════════════════
            # PAGE 1
            # ══════════════════════════════════════════════════════════════════
            fig1 = plt.figure(figsize=(8.27, 11.69))
            fig1.patch.set_facecolor('white')

            # ── Header band ───────────────────────────────────────────────────
            _header_band(fig1, 0.934, 0.066,
                         title='Weekly Report',
                         subtitle='DB Push Analytics',
                         right_line1='Generated ' + gen_ts,
                         right_line2=('Period: ' + wk_str) + (('  |  ' + filt_str) if filt_str else ''))

            # ── A. Executive summary KPIs (4 large cards) ────────────────────
            diff  = this_week - last_week
            diff_str = ('+' if diff >= 0 else '') + str(diff)
            diff_col = EMERALD if diff > 0 else (RED if diff < 0 else GRAY)

            fig1.text(0.055, 0.913, 'EXECUTIVE SUMMARY', fontsize=7,
                      fontweight='bold', color=MUTED)
            EW = 0.198; EH = 0.072; EY = 0.832; GAP = 0.014
            exec_kpis = [
                ('CUMULATIVE PUSHED', total,         EMERALD, 'all-time records'),
                ('THIS WEEK',         this_week,     INDIGO,  f_label),
                ('WoW CHANGE',        diff_str,      diff_col,'vs previous week'),
                ('STATES ACTIVE',     len(state_counts), BLUE,'states with pushes'),
            ]
            for i, (lbl, val, col, sub) in enumerate(exec_kpis):
                _exec_kpi(fig1, 0.055 + i * (EW + GAP), EY, EW, EH, lbl, val, col, sub)

            # ── B. Weekly push velocity chart ────────────────────────────────
            fig1.text(0.055, 0.820, 'WEEKLY PUSH VELOCITY', fontsize=7,
                      fontweight='bold', color=MUTED)
            ax_wv = fig1.add_axes([0.055, 0.695, 0.595, 0.108])
            _style_ax(ax_wv, 'DB Push Count — Last 4 Weeks')
            if last4:
                w4_vals = [weekly_all[w] for w in last4]
                w4_lbls = [w.strftime('%d %b') for w in last4]
                w4_cols = [EMERALD if w == wstart(today) else '#818cf8' for w in last4]
                bars = ax_wv.bar(w4_lbls, w4_vals, color=w4_cols, width=0.5,
                                  edgecolor='white', linewidth=0.5)
                ax_wv.set_ylim(0, max(w4_vals) * 1.35 + 1)
                for xi, (bar, v) in enumerate(zip(bars, w4_vals)):
                    ax_wv.text(xi, v + ax_wv.get_ylim()[1] * 0.02, str(v),
                               ha='center', va='bottom', fontsize=9,
                               color=DARK, fontweight='bold')
                # current week label
                try:
                    cw_idx = [w == wstart(today) for w in last4].index(True)
                    ax_wv.text(cw_idx, -ax_wv.get_ylim()[1] * 0.12, 'Current',
                               ha='center', va='top', fontsize=6.5,
                               color=EMERALD, fontweight='bold')
                except ValueError:
                    pass
            else:
                ax_wv.axis('off')
                ax_wv.text(0.5, 0.5, 'No data yet', ha='center', color=MUTED, fontsize=9)

            # WoW chip beside velocity chart
            ax_wow = fig1.add_axes([0.680, 0.695, 0.265, 0.108])
            ax_wow.axis('off')
            ax_wow.set_title('Week-over-Week', fontsize=8.5, fontweight='bold',
                             color=DARK, loc='left', pad=5)
            wow_items = [
                ('This week',  this_week, INDIGO),
                ('Last week',  last_week, GRAY),
                ('Change',     diff_str,  diff_col),
                ('Weekly avg', f'{avg:.1f}', AMBER),
            ]
            for j, (lbl, val, col) in enumerate(wow_items):
                yy = 0.78 - j * 0.22
                ax_wow.text(0.0, yy, lbl, va='center', fontsize=8, color='#475569')
                ax_wow.text(0.80, yy, str(val), va='center', ha='right',
                            fontsize=9, fontweight='bold', color=col)

            # ── C. Pipeline status (5 mini cards) ────────────────────────────
            fig1.add_artist(plt.Line2D([0.055, 0.945], [0.688, 0.688],
                                       color=BORDER, lw=0.6))
            fig1.text(0.055, 0.677, 'FORM 20 PIPELINE STATUS', fontsize=7,
                      fontweight='bold', color=MUTED)
            MW = (0.890 - 0.044) / 5; MH = 0.057; MY = 0.610; MG = 0.011
            mini_kpis = [
                ('TOTAL TRACKED', db_total,      DARK,    None),
                ('DB PUSHED',     db_pushed,      EMERALD, f'{db_pct}% complete'),
                ('DOWNLOADED',    db_downloaded,  BLUE,    'Awaiting extraction'),
                ('EXTRACTED',     db_extracted,   VIOLET,  'Awaiting DB push'),
                ('REMAINING',       db_missing,     RED,     'Not yet downloaded'),
            ]
            for i, (lbl, val, col, sub) in enumerate(mini_kpis):
                _mini_kpi(fig1, 0.055 + i * (MW + MG), MY, MW, MH, lbl, val, col, sub)

            # ── D. Monthly trend + State performance ──────────────────────────
            fig1.add_artist(plt.Line2D([0.055, 0.945], [0.604, 0.604],
                                       color=BORDER, lw=0.6))
            fig1.text(0.055, 0.593, 'DETAILED ANALYSIS', fontsize=7,
                      fontweight='bold', color=MUTED)

            ax_mon = fig1.add_axes([0.055, 0.455, 0.53, 0.115])
            _style_ax(ax_mon, 'Monthly DB Push Trend')
            if sorted_months:
                mlbls = [m[5:] for m in sorted_months]
                mvals = [monthly[m] for m in sorted_months]
                max_m = max(mvals)
                bar_cols_m = [EMERALD if v == max_m else INDIGO for v in mvals]
                ax_mon.bar(mlbls, mvals, color=bar_cols_m, width=0.65,
                           edgecolor='white', linewidth=0.5)
                ax_mon.set_ylim(0, max_m * 1.3 + 1)
                for xi, v in enumerate(mvals):
                    if v:
                        ax_mon.text(xi, v, str(v), ha='center', va='bottom',
                                    fontsize=6.5, color=DARK, fontweight='bold')
            else:
                ax_mon.axis('off')
                ax_mon.text(0.5, 0.5, 'No data yet', ha='center', color=MUTED, fontsize=9)

            ax_sp = fig1.add_axes([0.650, 0.455, 0.295, 0.115])
            _style_ax(ax_sp, 'State Performance (Top 8)')
            top_s = state_counts.most_common(8)[::-1]
            if top_s:
                bars_sp = ax_sp.barh([s for s, _ in top_s],
                                     [c for _, c in top_s],
                                     color=EMERALD, height=0.55,
                                     edgecolor='white', linewidth=0.3)
                for ii, (s, c) in enumerate(top_s):
                    ax_sp.text(c + 0.05, ii, str(c), va='center',
                               fontsize=7, color=DARK, fontweight='bold')
                ax_sp.set_xlim(0, max(c for _, c in top_s) * 1.25)
            else:
                ax_sp.axis('off')
                ax_sp.text(0.5, 0.5, 'No data yet', ha='center', color=MUTED, fontsize=9)

            # ── E. Election type distribution ────────────────────────────────
            fig1.add_artist(plt.Line2D([0.055, 0.945], [0.450, 0.450],
                                       color='#f1f5f9', lw=0.5))
            ax_et = fig1.add_axes([0.055, 0.340, 0.890, 0.090])
            ax_et.axis('off')
            ax_et.set_title('Completed by Election Type', fontsize=8.5,
                            fontweight='bold', color=DARK, loc='left', pad=5)
            top_t = type_counts.most_common()
            if top_t:
                n_types = len(top_t)
                barw = 0.86 / max(n_types, 1)
                max_cnt = max(c for _, c in top_t)
                for ii, (ty, cnt) in enumerate(top_t):
                    col = TYPE_COL.get(ty, GRAY)
                    pct_t = cnt / total * 100 if total else 0
                    bx = ii * barw
                    # bar background
                    ax_et.add_patch(mpatches.Rectangle(
                        (bx + 0.01, 0.30), barw * 0.88, 0.25,
                        facecolor=BORDER, transform=ax_et.transAxes, clip_on=True))
                    # fill
                    ax_et.add_patch(mpatches.Rectangle(
                        (bx + 0.01, 0.30), barw * 0.88 * cnt / max_cnt, 0.25,
                        facecolor=col, transform=ax_et.transAxes, clip_on=True))
                    ax_et.text(bx + 0.01, 0.76, ty,
                               fontsize=9, fontweight='bold', color=col,
                               transform=ax_et.transAxes)
                    ax_et.text(bx + 0.01, 0.10,
                               f'{cnt} records  ({pct_t:.0f}%)',
                               fontsize=7.5, color=GRAY, transform=ax_et.transAxes)
                ax_et.set_xlim(0, 1)
                ax_et.set_ylim(0, 1)
            else:
                ax_et.text(0.5, 0.5, 'No data yet', ha='center', va='center',
                           color=MUTED, fontsize=9)

            # ── F. Elections pushed this period ───────────────────────────────
            fig1.add_artist(plt.Line2D([0.055, 0.945], [0.332, 0.332],
                                       color=BORDER, lw=0.6))
            period_hdr = (f'ELECTIONS PUSHED — {f_label.upper()}'
                          f'  ({len(focus_recs)} election{"s" if len(focus_recs) != 1 else ""})')
            fig1.text(0.055, 0.320, period_hdr, fontsize=7, fontweight='bold', color=MUTED)

            ax_pw = fig1.add_axes([0.055, 0.048, 0.890, 0.260])
            ax_pw.axis('off')
            ax_pw.set_title(
                f'{f_start.strftime("%d %b")} – {f_end.strftime("%d %b %Y")}',
                fontsize=9, fontweight='bold', color=DARK, loc='left', pad=5
            )

            if focus_recs:
                pw_rows = []
                for r in focus_recs:
                    sname = STATE_NAMES.get(r['state'], r['state'])
                    d_fmt = datetime.strptime(r['date'], '%Y-%m-%d').strftime('%d %b %Y')
                    pw_rows.append([r['state'], sname, r['type'], r['year'], d_fmt])

                col_labels_pw = ['Code', 'State Name', 'Type', 'Year', 'Date Pushed']
                col_widths_pw = [0.07, 0.31, 0.10, 0.09, 0.15]

                tab_pw = ax_pw.table(
                    cellText=pw_rows,
                    colLabels=col_labels_pw,
                    cellLoc='left',
                    loc='upper center',
                    colWidths=col_widths_pw,
                )
                tab_pw.auto_set_font_size(False)
                tab_pw.set_fontsize(9)
                tab_pw.scale(1, 1.55)

                for (row, col), cell in tab_pw.get_celld().items():
                    cell.set_edgecolor(BORDER)
                    if row == 0:
                        cell.set_facecolor(EMERALD)
                        cell.set_text_props(color='white', fontweight='bold', fontsize=8.5)
                    else:
                        pw_r = pw_rows[row - 1]
                        ty_col = TYPE_COL.get(pw_r[2], GRAY)
                        cell.set_facecolor('#f0fdf4' if row % 2 == 0 else 'white')
                        if col == 2:   # Type column — color by AE/GE
                            cell.set_text_props(color=ty_col, fontweight='bold')
                        if col == 0:   # State code — bold
                            cell.set_text_props(fontweight='bold')
            else:
                ax_pw.text(0.5, 0.5, 'No elections pushed this period.',
                           ha='center', va='center', fontsize=10, color=MUTED)

            # ── Footer ────────────────────────────────────────────────────────
            _footer_band(fig1, 'Page 1 of 2', gen_ts)

            pdf.savefig(fig1, facecolor='white', bbox_inches='tight')
            plt.close(fig1)

            # ══════════════════════════════════════════════════════════════════
            # PAGE 2 — State × Year completed elections detail table
            # ══════════════════════════════════════════════════════════════════
            fig2 = plt.figure(figsize=(8.27, 11.69))
            fig2.patch.set_facecolor('white')

            _header_band(fig2, 0.934, 0.066,
                         title='State-wise Completion Detail',
                         subtitle='All DB-pushed elections',
                         right_line1='Generated ' + gen_ts,
                         right_line2=wk_str)

            state_map = {}
            for r in recs:
                st, ty, yr = r['state'], r['type'], r['year']
                if st not in state_map: state_map[st] = {}
                if ty not in state_map[st]: state_map[st][ty] = set()
                state_map[st][ty].add(yr)

            sorted_states = sorted(state_map.keys())

            ax_t = fig2.add_axes([0.055, 0.060, 0.890, 0.860])
            ax_t.axis('off')
            ax_t.set_title(
                f'{len(sorted_states)} states  ·  {total} elections DB-pushed',
                fontsize=9.5, fontweight='bold', color=DARK, loc='left', pad=10
            )

            if sorted_states:
                rows_data = []
                for st in sorted_states:
                    name = STATE_NAMES.get(st, st)
                    type_strs = []
                    for ty in sorted(state_map[st].keys()):
                        years = ', '.join(sorted(state_map[st][ty]))
                        type_strs.append(f'{ty}: {years}')
                    elections_str = '  |  '.join(type_strs)
                    total_r = sum(len(v) for v in state_map[st].values())
                    rows_data.append([st, name, elections_str, str(total_r)])

                col_labels  = ['Code', 'State Name', 'Completed Elections (Type: Years)', 'Count']
                col_widths  = [0.055, 0.175, 0.640, 0.075]

                tab = ax_t.table(
                    cellText=rows_data,
                    colLabels=col_labels,
                    cellLoc='left',
                    loc='upper center',
                    colWidths=col_widths,
                )
                tab.auto_set_font_size(False)
                tab.set_fontsize(8)
                tab.scale(1, 1.5)

                for (row, col), cell in tab.get_celld().items():
                    cell.set_edgecolor(BORDER)
                    if row == 0:
                        cell.set_facecolor(SLATE)
                        cell.set_text_props(color='white', fontweight='bold', fontsize=8)
                    elif row % 2 == 0:
                        cell.set_facecolor('#f8fafc')
                    else:
                        cell.set_facecolor('white')
                    if col == 3:
                        cell.set_text_props(ha='right')
                    if col == 0:
                        cell.set_text_props(fontweight='bold', color=SLATE if row > 0 else 'white')
            else:
                ax_t.text(0.5, 0.6,
                          'No DB-pushed records yet.\nRecords appear here once elections are marked as DB Pushed.',
                          ha='center', va='center', fontsize=11, color=MUTED, linespacing=1.8)

            _footer_band(fig2, 'Page 2 of 2', gen_ts)

            pdf.savefig(fig2, facecolor='white', bbox_inches='tight')
            plt.close(fig2)

    buf.seek(0)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    if out_fmt == 'png':
        import fitz
        buf2 = io.BytesIO(buf.read())
        doc = fitz.open(stream=buf2, filetype='pdf')
        pix = doc[0].get_pixmap(dpi=150)
        png_buf = io.BytesIO(pix.tobytes('png'))
        png_buf.seek(0)
        return send_file(png_buf, mimetype='image/png')

    return send_file(buf, mimetype='application/pdf', as_attachment=True,
                     download_name=f'Weekly_Report_{f_start.strftime("%Y%m%d")}_{ts}.pdf')


ANALYTICS_CACHE_PATH = os.path.join(BASE_DIR, 'analytics_cache.json')
_analytics_cache = None


def _sanitize_db_err(err):
    """Return a safe error hint without exposing internal DB details to the client."""
    if not err:
        return 'Unavailable'
    e = str(err).lower()
    if 'permission' in e or 'denied' in e:
        return 'permission denied'
    if 'does not exist' in e or 'relation' in e:
        return 'relation does not exist'
    return 'RDS query error'


def _rds_query(cur, sql, params=()):
    try:
        cur.execute(sql, params)
        return cur.fetchall(), None
    except Exception as e:
        # rollback so the connection isn't stuck in an aborted-transaction state
        try:
            cur.execute('ROLLBACK')
        except Exception:
            pass
        return None, _sanitize_db_err(e)


def build_analytics_cache():
    """Run all RDS analytics queries and return the result dict (slow — run in background)."""
    rds = get_rds_db()
    if not rds:
        return None
    result = {}
    try:
        cur = rds.cursor()

        # ── 1. Retro coverage — AC-count level, non-BP only ─────────────────
        # Canonical AC count per state from ac_mapping (distinct constituencies).
        # If an election has any data → all canonical ACs for that state are counted.
        # This gives meaningful AC-level totals (e.g. 31,792 ACs expected).
        _RETRO_CTE = '''
            canonical AS (
                SELECT state_abb, COUNT(DISTINCT ac_no) AS ac_count
                FROM ac_mapping GROUP BY state_abb
            ),
            elections AS (
                SELECT state_abb, el_year, el_type
                FROM ac_election_mapping
                WHERE POSITION('-BP' IN el_type) = 0
                GROUP BY state_abb, el_year, el_type
            ),
            avail AS (
                SELECT DISTINCT er.state_abb, e.el_year, e.el_type
                FROM election_result er JOIN election e ON er.el_id = e.el_id
                WHERE POSITION('-BP' IN e.el_type) = 0
            )
        '''
        rows, err = _rds_query(cur, f'''
            WITH {_RETRO_CTE}
            SELECT
                SUM(c.ac_count) AS total_expected,
                SUM(CASE WHEN a.state_abb IS NOT NULL THEN c.ac_count ELSE 0 END) AS available_acs
            FROM elections el
            JOIN canonical c ON el.state_abb = c.state_abb
            LEFT JOIN avail a
                ON el.state_abb = a.state_abb
               AND el.el_year   = a.el_year
               AND el.el_type   = a.el_type
        ''')
        if rows and not err:
            ac_total, ac_avail = rows[0]
            rows2, _ = _rds_query(cur, f'''
                WITH {_RETRO_CTE}
                SELECT
                    el.el_type,
                    SUM(c.ac_count) AS total,
                    SUM(CASE WHEN a.state_abb IS NOT NULL THEN c.ac_count ELSE 0 END) AS available
                FROM elections el
                JOIN canonical c ON el.state_abb = c.state_abb
                LEFT JOIN avail a
                    ON el.state_abb = a.state_abb
                   AND el.el_year   = a.el_year
                   AND el.el_type   = a.el_type
                GROUP BY el.el_type ORDER BY total DESC
            ''')
            rows3, _ = _rds_query(cur, f'''
                WITH {_RETRO_CTE}
                SELECT
                    el.state_abb,
                    SUM(c.ac_count) AS expected_acs,
                    SUM(CASE WHEN a.state_abb IS NOT NULL THEN c.ac_count ELSE 0 END) AS available_acs,
                    CASE WHEN SUM(c.ac_count) > 0
                         THEN ROUND(100.0 * SUM(CASE WHEN a.state_abb IS NOT NULL THEN c.ac_count ELSE 0 END)
                              / SUM(c.ac_count), 1)
                         ELSE 0 END AS pct
                FROM elections el
                JOIN canonical c ON el.state_abb = c.state_abb
                LEFT JOIN avail a
                    ON el.state_abb = a.state_abb
                   AND el.el_year   = a.el_year
                   AND el.el_type   = a.el_type
                GROUP BY el.state_abb
                ORDER BY available_acs DESC LIMIT 8
            ''')
            result['retro'] = {
                'available': True,
                'ac_total':     int(ac_total or 0),
                'ac_available': int(ac_avail or 0),
                'by_type_ac': [
                    {'type': r[0], 'total': int(r[1]), 'available': int(r[2])}
                    for r in (rows2 or [])
                ],
                'top_states_ac': [
                    {'state': r[0], 'expected': int(r[1]),
                     'available': int(r[2]), 'pct': float(r[3] or 0)}
                    for r in (rows3 or [])
                ],
            }
        else:
            result['retro'] = {'available': False, 'error': err}

        # ── 1b. AC-PC mapping stats (non-BP) ─────────────────────────────────
        rows_m, err_m = _rds_query(cur, '''
            SELECT
                COUNT(DISTINCT el_year)                              AS n_years,
                COUNT(DISTINCT (state_abb || el_year || el_type))   AS n_entries
            FROM ac_election_mapping
            WHERE POSITION('-BP' IN el_type) = 0
        ''')
        if rows_m and not err_m:
            result['mapping_years']   = int(rows_m[0][0] or 0)
            result['mapping_entries'] = int(rows_m[0][1] or 0)
        else:
            result['mapping_years']   = 0
            result['mapping_entries'] = 0

        # ── 1c. Mapping breakdown by election type (non-BP) ───────────────────
        rows_mt, err_mt = _rds_query(cur, '''
            SELECT el_type, COUNT(DISTINCT (state_abb || el_year || el_type)) AS n_entries
            FROM ac_election_mapping
            WHERE POSITION('-BP' IN el_type) = 0
            GROUP BY el_type ORDER BY n_entries DESC
        ''')
        result['mapping_by_type'] = {r[0]: int(r[1]) for r in (rows_mt or [])} if not err_mt else {}

        # ── 2 & 3. Booth metadata / Voter roll — SKIPPED ──────────────────────
        # These cards were removed from the dashboard, so we no longer scan the
        # two largest RDS tables (booth_metadata, voter_details) on every refresh.
        # Keys are kept (available:False) so any cached/older client stays safe.
        result['booth']      = {'available': False, 'error': 'not tracked'}
        result['voter_roll'] = {'available': False, 'error': 'not tracked'}

        # ── 4. Caste details ──────────────────────────────────────────────────
        rows, err = _rds_query(cur, '''
            SELECT COUNT(DISTINCT state_abb), COUNT(DISTINCT (state_abb,ac_no)),
                   COUNT(DISTINCT caste_category), COUNT(*) FROM caste_details
        ''')
        if rows and not err:
            states, acs, cats, total_rows = rows[0]
            rows2, _ = _rds_query(cur, '''
                SELECT caste_category, COUNT(DISTINCT (state_abb,ac_no)), COUNT(*)
                FROM caste_details GROUP BY caste_category ORDER BY 2 DESC
            ''')
            rows3, _ = _rds_query(cur, '''
                SELECT state_abb, COUNT(DISTINCT ac_no)
                FROM caste_details GROUP BY state_abb ORDER BY 2 DESC LIMIT 10
            ''')
            result['caste'] = {
                'available': True,
                'states': int(states or 0), 'acs_with_data': int(acs or 0),
                'categories': int(cats or 0), 'total_rows': int(total_rows or 0),
                'by_category': [{'category': r[0], 'acs': int(r[1]), 'rows': int(r[2])} for r in (rows2 or [])],
                'top_states':  [{'state': r[0], 'acs': int(r[1])} for r in (rows3 or [])],
            }
        else:
            result['caste'] = {'available': False, 'error': err}

    except Exception as e:
        print(f'build_analytics_cache error: {e}')
    finally:
        rds.close()

    return result


def _build_analytics():
    """Rebuild the dashboard analytics cache from RDS and persist it to disk.
    Triggered on dashboard reload via trigger_refresh('analytics', ...) when the
    cache is older than CACHE_TTL_SECONDS — no longer polled every 10 minutes."""
    global _analytics_cache
    data = build_analytics_cache()
    if data:
        _analytics_cache = data
        try:
            with open(ANALYTICS_CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception:
            pass


@app.route('/api/dashboard/analytics')
def dashboard_analytics():
    """Return cached analytics — instant response. A reload kicks a background
    refresh only when the cache is stale (see trigger_refresh)."""
    global _analytics_cache
    trigger_refresh('analytics', _build_analytics)   # refresh-on-reload (if stale)
    # 1. In-memory cache
    if _analytics_cache:
        return jsonify(_analytics_cache)
    # 2. Disk cache (survives restarts)
    if os.path.exists(ANALYTICS_CACHE_PATH):
        try:
            with open(ANALYTICS_CACHE_PATH, 'r', encoding='utf-8') as f:
                _analytics_cache = json.load(f)
            return jsonify(_analytics_cache)
        except Exception:
            pass
    # 3. Still building — return retro only (fast enough to query live)
    rds = get_rds_db()
    if not rds:
        return jsonify({'retro': {'available': False, 'error': 'RDS not configured'},
                        'booth': {'available': False, 'error': 'cache building'},
                        'voter_roll': {'available': False, 'error': 'cache building'},
                        'caste': {'available': False, 'error': 'cache building'}}), 202
    try:
        cur = rds.cursor()
        # Fast path: AC-count level, non-BP only
        rows, err = _rds_query(cur, '''
            WITH canonical AS (
                SELECT state_abb, COUNT(DISTINCT ac_no) AS ac_count
                FROM ac_mapping GROUP BY state_abb
            ),
            elections AS (
                SELECT state_abb, el_year, el_type FROM ac_election_mapping
                WHERE POSITION('-BP' IN el_type) = 0
                GROUP BY state_abb, el_year, el_type
            ),
            avail AS (
                SELECT DISTINCT er.state_abb, e.el_year, e.el_type
                FROM election_result er JOIN election e ON er.el_id = e.el_id
                WHERE POSITION('-BP' IN e.el_type) = 0
            )
            SELECT
                SUM(c.ac_count) AS total_expected,
                SUM(CASE WHEN a.state_abb IS NOT NULL THEN c.ac_count ELSE 0 END) AS available_acs
            FROM elections el
            JOIN canonical c ON el.state_abb = c.state_abb
            LEFT JOIN avail a
                ON el.state_abb = a.state_abb
               AND el.el_year   = a.el_year
               AND el.el_type   = a.el_type
        ''')
        retro_partial = {'available': False, 'error': err}
        if rows and not err:
            ac_total, ac_avail = rows[0]
            retro_partial = {
                'available': True,
                'ac_total':     int(ac_total or 0),
                'ac_available': int(ac_avail or 0),
                'by_type_ac': [],
                'top_states_ac': [],
            }
        # Mapping stats (fast)
        rows_m, err_m = _rds_query(cur, '''
            SELECT COUNT(DISTINCT el_year),
                   COUNT(DISTINCT (state_abb || el_year || el_type))
            FROM ac_election_mapping WHERE POSITION('-BP' IN el_type) = 0
        ''')
        mapping_years   = int((rows_m or [[0,0]])[0][0]) if not err_m else 0
        mapping_entries = int((rows_m or [[0,0]])[0][1]) if not err_m else 0
        # Mapping by type (fast)
        rows_mt, err_mt = _rds_query(cur, '''
            SELECT el_type, COUNT(DISTINCT (state_abb || el_year || el_type)) AS n_entries
            FROM ac_election_mapping WHERE POSITION('-BP' IN el_type) = 0
            GROUP BY el_type ORDER BY n_entries DESC
        ''')
        mapping_by_type = {r[0]: int(r[1]) for r in (rows_mt or [])} if not err_mt else {}
        return jsonify({'retro': retro_partial,
                        'mapping_years':   mapping_years,
                        'mapping_entries': mapping_entries,
                        'mapping_by_type': mapping_by_type,
                        'booth':      {'available': False, 'error': 'analytics cache still building — refresh in ~60s'},
                        'voter_roll': {'available': False, 'error': 'analytics cache still building — refresh in ~60s'},
                        'caste':      {'available': False, 'error': 'analytics cache still building — refresh in ~60s'}}), 202
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        rds.close()


@app.route('/api/form20_card_stats')
def form20_card_stats():
    """Return Form 20 card stats computed directly from live JSON files (no RDS needed).
    - form20_entries: unique (state, el_type, year) in form20_summary_view (DB pushed)
    - acpc_entries:   unique (state, el_type, year) in ac_election_mapping (total expected)
    - by_type:        breakdown by election type (non-BP)
    - by_state:       top states in Form 20
    - years_in_form20: distinct years present in Form 20 (non-BP)
    - years_in_mapping: distinct years present in AC-PC mapping (non-BP)
    """
    trigger_refresh('live', _build_live)   # refresh RDS snapshot on reload (if stale)
    # ── Load form20 live data ────────────────────────────────────────────────
    form20_set = set()
    form20_list = []
    if os.path.exists(LIVE_JSON_PATH):
        try:
            with open(LIVE_JSON_PATH, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            for item in raw:
                state   = str(item.get('state', '')).strip()
                el_type = str(item.get('el_type', '')).strip()
                el_year = str(item.get('el_year', '')).strip()
                if state and el_type and el_year and '-BP' not in el_type:
                    form20_set.add((state, el_type, el_year))
                    form20_list.append({'state': state, 'el_type': el_type, 'el_year': el_year})
        except Exception:
            pass

    # ── Load AC-PC mapping data ──────────────────────────────────────────────
    acpc_set = set()
    if os.path.exists(AC_PC_JSON_PATH):
        try:
            with open(AC_PC_JSON_PATH, 'r', encoding='utf-8') as f:
                raw2 = json.load(f)
            for item in raw2:
                state   = str(item.get('state', '')).strip()
                el_type = str(item.get('el_type', '')).strip()
                el_year = str(item.get('el_year', '')).strip()
                if state and el_type and el_year and '-BP' not in el_type:
                    acpc_set.add((state, el_type, el_year))
        except Exception:
            pass

    # ── Compute metrics ──────────────────────────────────────────────────────
    form20_count  = len(form20_set)
    acpc_count    = len(acpc_set)
    coverage_pct  = round((form20_count / acpc_count) * 100) if acpc_count else 0

    # Distinct years (non-BP)
    years_form20   = sorted(set(int(y) for _, _, y in form20_set))
    years_mapping  = sorted(set(int(y) for _, _, y in acpc_set))

    # By election type breakdown
    from collections import Counter, defaultdict
    type_form20  = Counter(el_type for _, el_type, _ in form20_set)
    type_mapping = Counter(el_type for _, el_type, _ in acpc_set)
    all_types    = sorted(set(list(type_form20.keys()) + list(type_mapping.keys())))
    by_type = {}
    for t in all_types:
        by_type[t] = {
            'in_form20':   type_form20.get(t, 0),
            'in_mapping':  type_mapping.get(t, 0),
        }

    # Top states by count in Form 20
    state_counts = Counter(state for state, _, _ in form20_set)
    top_states   = [{'state': s, 'count': c} for s, c in state_counts.most_common(10)]

    # ── Missing entries: in mapping (262) but not yet in Form 20 ─────────────
    # For each missing (state, el_type, el_year), credit the canonical AC count
    # of that state — gives the total AC coverage still pending across the
    # 262 mapping entries.
    missing_set     = acpc_set - form20_set
    missing_acs     = sum(STATE_AC_COUNTS.get(state, 0) for state, _, _ in missing_set)
    missing_by_state = Counter(state for state, _, _ in missing_set)
    missing_states   = [
        {'state': s, 'count': c, 'acs': c * STATE_AC_COUNTS.get(s, 0)}
        for s, c in missing_by_state.most_common()
    ]

    return jsonify({
        'form20_entries':   form20_count,
        'acpc_entries':     acpc_count,
        'coverage_pct':     coverage_pct,
        'years_in_form20':  years_form20,
        'years_in_mapping': years_mapping,
        'by_type':          by_type,
        'top_states':       top_states,
        'remaining':        acpc_count - form20_count,
        'missing_acs':      missing_acs,
        'missing_states':   missing_states,
    })


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


def _build_retro():
    """Rebuild the retro metadata cache from RDS. Triggered on retro/dashboard
    reload via trigger_refresh('retro', ...) when the cache is stale — no longer
    polled every 10 minutes."""
    global retro_metadata_cache
    meta = fetch_retro_metadata_sync()
    if meta is not None:
        retro_metadata_cache = meta


@app.route('/api/retro/metadata')
def retro_metadata():
    trigger_refresh('retro', _build_retro)   # refresh-on-reload (if stale)
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
        return jsonify({'error': f'RDS query failed: {_sanitize_db_err(e)}'}), 500
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
