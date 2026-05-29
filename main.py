import os
import pandas as pd
from sqlalchemy import create_engine
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Configuration from .env
BASE_DIR = os.getenv("EXCEL_BASE_DIR", r"D:\kerala_excels")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", r"D:\kerala_parquets")
STATE_CODE = os.getenv("STATE_CODE", "S11")
EROLL_PUBLICATION = os.getenv("EROLL_PUBLICATION")

# DB Connection using SQLAlchemy
DB_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', 5432)}/{os.getenv('DB_NAME')}"
engine = create_engine(DB_URL)

def fetch_db_data():
    query = f"""
    SELECT 
        ac_no, booth_no, page_no, page_serial, epic_no,
        voter_name, voter_name_regional,
        relative_name, relative_name_regional,
        age as age_db, gender as gender_db, relation_type, api_extraction
    FROM public.epic_details_v2
    WHERE state_code = '{STATE_CODE}' AND eroll_publication = '{EROLL_PUBLICATION}'
    """
    
    df = pd.read_sql(query, engine)
    
    df['epic_no'] = df['epic_no'].astype(str).str.strip().str.upper()
    df['ac_no'] = df['ac_no'].astype(str).str.strip()
    df['booth_no'] = df['booth_no'].astype(str).str.strip()
    df['page_no'] = df['page_no'].astype(str).str.strip()
    df['page_serial'] = df['page_serial'].astype(int)
    
    print(f"DB rows fetched: {len(df)}\n")
    return df

def process_and_save_ac(folder_path, ac_number, db_df, output_dir):
    print(f"[AC {ac_number}] Processing...", end=" ")
    
    excel_files = list(folder_path.glob("*.xlsx")) + list(folder_path.glob("*.xls"))
    
    if not excel_files:
        print("No Excel files found. Skipping.")
        return None
    
    all_dfs = []
    for excel_file in excel_files:
        try:
            df = pd.read_excel(excel_file)
            all_dfs.append(df)
        except Exception as e:
            print(f"\n  Error reading {excel_file.name}: {e}")
    
    if not all_dfs:
        print("No valid data. Skipping.")
        return None
    
    excel_df = pd.concat(all_dfs, ignore_index=True)
    
    if excel_df.empty:
        print("No records. Skipping.")
        return None
    
    # Standardize columns
    excel_df['Epic Number'] = excel_df['Epic Number'].astype(str).str.strip().str.upper()
    excel_df['AC Number'] = excel_df['AC Number'].astype(str).str.strip()
    excel_df['Booth Number'] = excel_df['Booth Number'].astype(str).str.strip()
    excel_df['Page Number'] = excel_df['Page Number'].astype(str).str.strip()
    
    # Convert Gender: Male → M, Female → F
    excel_df['Gender'] = excel_df['Gender'].astype(str).str.strip().replace({'Male': 'M', 'Female': 'F'})
    
    # Derive page_serial using cumcount
    excel_df['page_serial'] = excel_df.groupby(['AC Number', 'Booth Number', 'Page Number']).cumcount() + 1
    
    # Add row index to track original rows
    excel_df['_row_idx'] = range(len(excel_df))
    
    # STEP 1: Match on Epic Number (drop duplicates to ensure 1:1)
    db_epic = db_df[['epic_no', 'voter_name', 'voter_name_regional', 'relative_name', 'relative_name_regional', 'age_db', 'gender_db', 'relation_type', 'api_extraction']].drop_duplicates(subset='epic_no')
    
    merged_epic = excel_df.merge(
        db_epic,
        left_on='Epic Number',
        right_on='epic_no',
        how='left'
    )
    
    # Separate matched and unmatched
    matched_epic = merged_epic[merged_epic['epic_no'].notna()].copy()
    matched_epic['match_type'] = 'epic_match'
    
    unmatched = merged_epic[merged_epic['epic_no'].isna()].copy()
    unmatched = unmatched.drop(columns=['epic_no', 'voter_name', 'voter_name_regional', 'relative_name', 'relative_name_regional', 'age_db', 'gender_db', 'relation_type', 'api_extraction'])
    
    # STEP 2: For unmatched, match on AC + Booth + Page + page_serial (drop duplicates to ensure 1:1)
    if not unmatched.empty:
        db_position = db_df.drop_duplicates(subset=['ac_no', 'booth_no', 'page_no', 'page_serial'])
        
        merged_position = unmatched.merge(
            db_position,
            left_on=['AC Number', 'Booth Number', 'Page Number', 'page_serial'],
            right_on=['ac_no', 'booth_no', 'page_no', 'page_serial'],
            how='left'
        )
        merged_position['match_type'] = merged_position['epic_no'].apply(
            lambda x: 'position_match' if pd.notna(x) else 'no_match'
        )
    else:
        merged_position = pd.DataFrame()
    
    # Combine results
    if not merged_position.empty:
        result = pd.concat([matched_epic, merged_position], ignore_index=True)
    else:
        result = matched_epic
    
    # Sort by original row order
    result = result.sort_values('_row_idx').reset_index(drop=True)
    
    # Stats
    epic_matched = (result['match_type'] == 'epic_match').sum()
    position_matched = (result['match_type'] == 'position_match').sum()
    no_match = (result['match_type'] == 'no_match').sum()
    
    # Fallback: Fill None values from Excel columns
    result['voter_name'] = result['voter_name'].replace('None', pd.NA).fillna(result['Name'])
    result['relative_name'] = result['relative_name'].replace('None', pd.NA).fillna(result["Father's/Husband's Name"])
    result['age_db'] = result['age_db'].fillna(result['Age'])
    result['gender_db'] = result['gender_db'].fillna(result['Gender'])
    result['relation_type'] = result['relation_type'].replace('None', pd.NA).fillna(result['Relation'])
    
    # Set Status='Deleted' where api_extraction='None'
    result['api_extraction'] = result['api_extraction'].astype(str)
    result.loc[result['api_extraction'] == 'None', 'Status'] = 'Deleted'
    
    # Select output columns
    output_columns = [
        'AC Number', 'Booth Number', 'Booth Section', 'Page Number', 'page_serial',
        'Epic Number', 'Relation', 'Address', 'Status',
        'voter_name', 'voter_name_regional',
        'relative_name', 'relative_name_regional', 'epic_no',
        'age_db', 'gender_db', 'relation_type', 'api_extraction'
    ]
    
    result = result[output_columns]
    
    # Convert all object columns to string
    for col in result.columns:
        if result[col].dtype == 'object':
            result[col] = result[col].astype(str)
    
    # Save
    output_path = os.path.join(output_dir, f"{ac_number}.parquet")
    result.to_parquet(output_path, index=False)
    
    print(f"{len(result)} rows | EPIC: {epic_matched} | Position: {position_matched} | None: {no_match} | Saved ✓")
    
    return {
        "rows": len(result), 
        "epic_matched": epic_matched, 
        "position_matched": position_matched,
        "no_match": no_match
    }

if __name__ == "__main__":
    print(f"State: {STATE_CODE}")
    print(f"Eroll Publication: {EROLL_PUBLICATION}")
    print(f"Source: {BASE_DIR}")
    print(f"Output: {OUTPUT_DIR}\n")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    db_df = fetch_db_data()
    
    base_path = Path(BASE_DIR)
    folders = sorted([f for f in base_path.iterdir() if f.is_dir() and f.name.isdigit()], 
                     key=lambda x: int(x.name))
    
    total_folders = len(folders)
    print(f"Found {total_folders} AC folders\n")
    print("="*80)
    
    total_rows = 0
    total_epic = 0
    total_position = 0
    total_none = 0
    
    for i, folder in enumerate(folders, 1):
        ac_number = folder.name
        
        result = process_and_save_ac(folder, ac_number, db_df, OUTPUT_DIR)
        
        if result:
            total_rows += result["rows"]
            total_epic += result["epic_matched"]
            total_position += result["position_matched"]
            total_none += result["no_match"]
        
        if i < total_folders:
            print(f"    → Moving to AC {folders[i].name}...")
    
    print("="*80)
    print(f"\nCompleted!")
    print(f"Total rows:         {total_rows}")
    print(f"EPIC matched:       {total_epic}")
    print(f"Position matched:   {total_position}")
    print(f"No match:           {total_none}")
    print(f"\nParquets saved in: {OUTPUT_DIR}")