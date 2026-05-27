"""
app.py — Form 20 Backlog Dashboard
Flask backend with SQLite. Run: python app.py
"""

import csv
import io
import os
from datetime import datetime

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


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/records')
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
    if status:
        query += ' AND overall_status = ?'; params.append(status)
    elif not search:
        query += " AND overall_status != 'db_pushed'"
    if sir_only == '1':
        query += ' AND is_sir_state = 1'
    if request.args.get('wip') == '1':
        query += ' AND wip = 1'
    if search:
        like = f'%{search}%'
        query += (' AND (state LIKE ? OR state_name LIKE ?'
                  ' OR key LIKE ? OR assigned_to LIKE ? OR remark LIKE ?)')
        params.extend([like, like, like, like, like])

    query += ' ORDER BY state, el_type, el_year'

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


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
    return jsonify(dict(row))


@app.route('/api/stats')
def get_stats():
    conn = get_db()

    status_rows = conn.execute(
        'SELECT overall_status, COUNT(*) AS cnt FROM records GROUP BY overall_status'
    ).fetchall()
    by_status = {r['overall_status']: r['cnt'] for r in status_rows}

    sir_rows = conn.execute(
        'SELECT overall_status, COUNT(*) AS cnt FROM records '
        'WHERE is_sir_state=1 GROUP BY overall_status'
    ).fetchall()
    sir_by_status = {r['overall_status']: r['cnt'] for r in sir_rows}
    
    wip_count = conn.execute('SELECT COUNT(*) as cnt FROM records WHERE wip=1').fetchone()['cnt']

    state_rows = conn.execute(
        'SELECT state, state_name, COUNT(*) AS total, '
        'SUM(CASE WHEN overall_status="db_pushed" THEN 1 ELSE 0 END) AS completed, '
        'SUM(CASE WHEN overall_status="extracted" THEN 1 ELSE 0 END) AS extracted '
        'FROM records GROUP BY state ORDER BY state'
    ).fetchall()

    conn.close()

    total = sum(by_status.values())
    return jsonify({
        'total': total,
        'by_status': by_status,
        'sir_by_status': sir_by_status,
        'wip_count': wip_count,
        'by_state': [dict(r) for r in state_rows],
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
    records = [dict(r) for r in rows]
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


retro_metadata_cache = None

@app.route('/api/retro/metadata')
def retro_metadata():
    global retro_metadata_cache
    if retro_metadata_cache is None:
        import csv
        try:
            retro_path = os.path.join(BASE_DIR, 'RETRO.csv')
            metadata = {}
            with open(retro_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                try:
                    headers = next(reader)
                except StopIteration:
                    return jsonify({'error': 'RETRO.csv is empty'}), 500
                
                try:
                    state_idx = headers.index('state_abb')
                    type_idx = headers.index('el_type')
                    year_idx = headers.index('el_year')
                except ValueError:
                    return jsonify({'error': 'Invalid RETRO.csv format'}), 500

                for row in reader:
                    if len(row) > max(state_idx, type_idx, year_idx):
                        s = row[state_idx].strip()
                        t = row[type_idx].strip()
                        y = row[year_idx].strip()
                        if not s or not t or not y:
                            continue
                        
                        if s not in metadata:
                            metadata[s] = {}
                        if t not in metadata[s]:
                            metadata[s][t] = {}
                        if y not in metadata[s][t]:
                            metadata[s][t][y] = 0
                        metadata[s][t][y] += 1
                        
            retro_metadata_cache = metadata
        except Exception as e:
            return jsonify({'error': str(e)}), 500
            
    return jsonify(retro_metadata_cache)


@app.route('/api/retro/export')
def export_retro():
    import csv, io, openpyxl
    state = request.args.get('state', '').strip()
    el_type = request.args.get('el_type', '').strip()
    year = request.args.get('year', '').strip()
    fmt = request.args.get('format', 'csv').strip().lower()

    if not state or not el_type or not year:
        return jsonify({'error': 'Missing required filters: state, el_type, year'}), 400

    try:
        retro_path = os.path.join(BASE_DIR, 'RETRO.csv')
        if not os.path.exists(retro_path):
            return jsonify({'error': 'RETRO.csv not found'}), 404

        filtered_rows = []
        headers = []
        with open(retro_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            try:
                headers = next(reader)
            except StopIteration:
                return jsonify({'error': 'RETRO.csv is empty'}), 500
                
            try:
                state_idx = headers.index('state_abb')
                type_idx = headers.index('el_type')
                year_idx = headers.index('el_year')
            except ValueError:
                return jsonify({'error': 'Invalid RETRO.csv format: missing columns'}), 500

            for row in reader:
                if len(row) > max(state_idx, type_idx, year_idx):
                    if row[state_idx] == state and row[type_idx] == el_type and row[year_idx] == year:
                        filtered_rows.append(row)

        if not filtered_rows:
            return jsonify({'error': 'No retro data found for this filter combination.'}), 404

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"Retro_{state}_{el_type}_{year}_{ts}"

        if fmt == 'xlsx':
            output = io.BytesIO()
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Retro Data"
            
            from openpyxl.styles import Font, PatternFill
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
            
            ws.append(headers)
            for cell in ws[1]:
                cell.font = header_font
                cell.fill = header_fill
                
            for row in filtered_rows:
                ws.append(row)
                
            ws.freeze_panes = "A2"
            for col in ws.columns:
                max_length = 0
                column = col[0].column_letter
                for cell in col:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                ws.column_dimensions[column].width = min(max_length + 2, 50)
                
            wb.save(output)
            output.seek(0)
            return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=f"{filename}.xlsx")
        else:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(headers)
            writer.writerows(filtered_rows)
            return send_file(io.BytesIO(output.getvalue().encode('utf-8-sig')), mimetype='text/csv', as_attachment=True, download_name=f"{filename}.csv")

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/retro/filters')
def get_retro_filters():
    retro_path = os.path.join(BASE_DIR, 'RETRO.csv')
    if not os.path.exists(retro_path):
        return jsonify({'error': 'RETRO.csv not found'}), 404

    try:
        state_param   = request.args.get('state', '').strip() or None
        el_type_param = request.args.get('el_type', '').strip() or None

        with open(retro_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            try:
                headers = next(reader)
            except StopIteration:
                return jsonify({'states': [], 'el_types': [], 'years': []}), 200

            try:
                state_idx   = headers.index('state_abb')
                el_type_idx = headers.index('el_type')
                el_year_idx = headers.index('el_year')
            except ValueError:
                return jsonify({'error': 'Invalid RETRO.csv format: missing columns'}), 500

            all_states   = set()
            all_el_types = set()
            all_years    = set()

            for row in reader:
                if len(row) <= max(state_idx, el_type_idx, el_year_idx):
                    continue
                row_state   = row[state_idx]
                row_el_type = row[el_type_idx]
                row_year    = row[el_year_idx]

                all_states.add(row_state)

                # el_types: filtered by state when state param is given
                if state_param is None or row_state == state_param:
                    all_el_types.add(row_el_type)

                # years: filtered by state+el_type intersection, or state-only,
                # or el_type-only, or all — depending on which params are present
                state_match   = (state_param is None   or row_state   == state_param)
                el_type_match = (el_type_param is None or row_el_type == el_type_param)
                if state_match and el_type_match:
                    all_years.add(row_year)

        return jsonify({
            'states':   sorted(all_states),
            'el_types': sorted(all_el_types),
            'years':    sorted(all_years, key=lambda y: int(y)),
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/retro/count')
def retro_count():
    state   = request.args.get('state',   '').strip()
    el_type = request.args.get('el_type', '').strip()
    year    = request.args.get('year',    '').strip()

    # Validate year when provided
    if year:
        try:
            year_int = int(year)
            if not (1900 <= year_int <= 2100):
                raise ValueError
        except ValueError:
            return jsonify({'error': 'Invalid year parameter'}), 400

    retro_path = os.path.join(BASE_DIR, 'RETRO.csv')
    if not os.path.exists(retro_path):
        return jsonify({'error': 'RETRO.csv not found'}), 404

    try:
        count = 0
        with open(retro_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            try:
                headers = next(reader)
            except StopIteration:
                # Completely empty file — treat as header-only
                return jsonify({'count': 0})

            try:
                state_idx = headers.index('state_abb')
                type_idx  = headers.index('el_type')
                year_idx  = headers.index('el_year')
            except ValueError:
                return jsonify({'error': 'Invalid RETRO.csv format: missing columns'}), 500

            for row in reader:
                if len(row) <= max(state_idx, type_idx, year_idx):
                    continue
                if state   and row[state_idx] != state:
                    continue
                if el_type and row[type_idx]  != el_type:
                    continue
                if year    and row[year_idx]  != year:
                    continue
                count += 1

        return jsonify({'count': count})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
