import re
import os

app_path = r"d:\Others\Varahe Work\Tasks\Form 20 Backlog Dashboard\app.py"

with open(app_path, "r", encoding="utf-8") as f:
    content = f.read()

# We need to enhance get_stats() to include:
# 1. by_type (AE vs GE breakdown)
# 2. missing_bottlenecks (top states with missing records)

old_loop_init = """    by_status = {'downloaded': 0, 'extracted': 0, 'missing': 0, 'pending': 0, 'completed': 0, 'db_pushed': 0}
    sir_by_status = {'downloaded': 0, 'extracted': 0, 'missing': 0, 'pending': 0, 'completed': 0, 'db_pushed': 0}
    wip_count = 0
    state_dict = {}"""

new_loop_init = """    by_status = {'downloaded': 0, 'extracted': 0, 'missing': 0, 'pending': 0, 'completed': 0, 'db_pushed': 0}
    sir_by_status = {'downloaded': 0, 'extracted': 0, 'missing': 0, 'pending': 0, 'completed': 0, 'db_pushed': 0}
    wip_count = 0
    state_dict = {}
    type_dict = {}"""

content = content.replace(old_loop_init, new_loop_init)

old_loop_body = """        if state not in state_dict:
            state_dict[state] = {
                'state': state,
                'state_name': r_dict['state_name'],
                'total': 0,
                'completed': 0,
                'extracted': 0
            }
            
        state_dict[state]['total'] += 1
        
        effective_status = r_dict['overall_status']"""

new_loop_body = """        if state not in state_dict:
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
        
        effective_status = r_dict['overall_status']"""

content = content.replace(old_loop_body, new_loop_body)


old_loop_end = """        if effective_status in ('completed', 'db_pushed'):
            state_dict[state]['completed'] += 1
        if effective_status == 'extracted':
            state_dict[state]['extracted'] += 1

    total = sum(by_status.values())
    state_rows = [state_dict[s] for s in sorted(state_dict.keys())]"""

new_loop_end = """        if effective_status in ('completed', 'db_pushed'):
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
    bottlenecks = sorted(state_rows, key=lambda x: x['missing'], reverse=True)[:5]"""

content = content.replace(old_loop_end, new_loop_end)

old_return = """    return jsonify({
        'total': total,
        'by_status': by_status,
        'sir_by_status': sir_by_status,
        'wip_count': wip_count,
        'by_state': state_rows,
    })"""

new_return = """    return jsonify({
        'total': total,
        'by_status': by_status,
        'sir_by_status': sir_by_status,
        'wip_count': wip_count,
        'by_state': state_rows,
        'by_type': type_dict,
        'bottlenecks': bottlenecks
    })"""

content = content.replace(old_return, new_return)


with open(app_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Backend API patched to include deep analytics.")
