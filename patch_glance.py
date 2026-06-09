import re
import os

app_path = r"d:\Others\Varahe Work\Tasks\Form 20 Backlog Dashboard\app.py"

with open(app_path, "r", encoding="utf-8") as f:
    content = f.read()

old_glance_start = """@app.route('/api/glance_report')
def glance_report():
    history = get_completion_history()
    history.pop('_updated', None)

    filter_month = request.args.get('month', '').strip()"""

new_glance_start = """@app.route('/api/glance_report')
def glance_report():
    history = get_completion_history()
    history.pop('_updated', None)

    filter_month = request.args.get('month', '').strip()
    filter_state = request.args.get('state', '').strip()
    filter_el_type = request.args.get('el_type', '').strip()"""

content = content.replace(old_glance_start, new_glance_start)

old_glance_loop = """    for key, date_str in history.items():
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
        except Exception:
            continue

        # Weekly bucket
        sw = d - timedelta(days=d.weekday())
        ew = sw + timedelta(days=6)"""

new_glance_loop = """    for key, date_str in history.items():
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

        # Weekly bucket
        sw = d - timedelta(days=d.weekday())
        ew = sw + timedelta(days=6)"""

content = content.replace(old_glance_loop, new_glance_loop)

with open(app_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Glance Report API patched to include state and el_type filters.")
