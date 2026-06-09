def apply_dynamic_status(r_dict, live_extracted, download_report):
    key = f"{str(r_dict['state']).strip()}-{str(r_dict['el_type']).strip()}-{str(r_dict['el_year']).strip()}"
    
    current_status = r_dict.get('overall_status')
    
    # Apply download report status if present
    if key in download_report:
        csv_status = download_report[key]
        
        # Don't downgrade from higher statuses
        if current_status not in ('db_pushed', 'completed', 'extracted'):
            r_dict['overall_status'] = csv_status
            
        # If CSV says missing, it overrides even 'downloaded'
        if csv_status == 'missing' and current_status in ('downloaded', 'pending'):
            r_dict['overall_status'] = 'missing'
            
    # Apply live extracted status if present
    is_live_completed = (str(r_dict['state']).strip(), str(r_dict['el_type']).strip(), str(r_dict['el_year']).strip()) in live_extracted
    if is_live_completed:
        r_dict['overall_status'] = 'completed'
        r_dict['db_status'] = 'in_db'
        
    return r_dict
