import pytest
from app import get_db, LocalPostgresConnectionWrapper

def test_db_connection():
    """Verify that get_db successfully returns the LocalPostgresConnectionWrapper"""
    db = get_db()
    assert isinstance(db, LocalPostgresConnectionWrapper)

def test_insert_and_retrieve_download_tracking():
    """Test inserting and fetching from download_tracking using the ? param syntax"""
    db = get_db()
    
    # Clean up before test
    db.execute("DELETE FROM download_tracking WHERE record_key = ?", ('TEST-123',))
    db.commit()

    # Insert test data using SQLite parameter syntax (?) which our wrapper should translate to %s
    query = '''
        INSERT INTO download_tracking 
        (assembly_constituency, state, type, record_key) 
        VALUES (?, ?, ?, ?)
    '''
    db.execute(query, ('Test AC', 'Test State', 'AE', 'TEST-123'))
    db.commit()

    # Retrieve data
    cursor = db.execute("SELECT * FROM download_tracking WHERE record_key = ?", ('TEST-123',))
    row = cursor.fetchone()
    
    assert row is not None
    assert row['assembly_constituency'] == 'Test AC'
    assert row['state'] == 'Test State'
    assert row['type'] == 'AE'
    assert row['record_key'] == 'TEST-123'
    
    # Clean up after test
    db.execute("DELETE FROM download_tracking WHERE record_key = ?", ('TEST-123',))
    db.commit()
    db.close()

def test_activity_log_insertion():
    """Test inserting into activity_log"""
    db = get_db()
    
    query = '''
        INSERT INTO activity_log (record_key, action, changed_by)
        VALUES (?, ?, ?)
    '''
    db.execute(query, ('TEST-123', 'status_change', 'test_user'))
    db.commit()
    
    cursor = db.execute("SELECT * FROM activity_log WHERE record_key = ? ORDER BY id DESC LIMIT 1", ('TEST-123',))
    row = cursor.fetchone()
    
    assert row is not None
    assert row['action'] == 'status_change'
    assert row['changed_by'] == 'test_user'
    
    db.execute("DELETE FROM activity_log WHERE record_key = ?", ('TEST-123',))
    db.commit()
    db.close()
