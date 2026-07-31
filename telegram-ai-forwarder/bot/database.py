import sqlite3
import datetime

DB_FILE = "bot_data.sqlite3"

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS sources (channel_id TEXT PRIMARY KEY, username TEXT, enabled INTEGER DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS targets (channel_id TEXT PRIMARY KEY, username TEXT, enabled INTEGER DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS routes (source_id TEXT, target_id TEXT, enabled INTEGER DEFAULT 1, UNIQUE(source_id, target_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS filters (id INTEGER PRIMARY KEY AUTOINCREMENT, filter_type TEXT, value TEXT UNIQUE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS processed_messages (source_msg_id INTEGER, source_channel TEXT, target_channel TEXT, timestamp DATETIME)''')
    c.execute('''CREATE TABLE IF NOT EXISTS activity_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME, status TEXT, source TEXT, target TEXT, reason TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS statistics (date TEXT PRIMARY KEY, processed INTEGER, forwarded INTEGER, rejected INTEGER, errors INTEGER)''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('is_paused', '0')")
    conn.commit()
    conn.close()

def is_paused():
    conn = get_db()
    res = conn.execute("SELECT value FROM settings WHERE key='is_paused'").fetchone()
    conn.close()
    return res['value'] == '1' if res else False

def set_paused(state: bool):
    conn = get_db()
    conn.execute("UPDATE settings SET value=? WHERE key='is_paused'", ('1' if state else '0',))
    conn.commit()
    conn.close()

def add_source(channel_id, username):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO sources (channel_id, username) VALUES (?, ?)", (str(channel_id), username))
    conn.commit()
    conn.close()

def add_target(channel_id, username):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO targets (channel_id, username) VALUES (?, ?)", (str(channel_id), username))
    conn.commit()
    conn.close()

def add_route(source_id, target_id):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO routes (source_id, target_id) VALUES (?, ?)", (str(source_id), str(target_id)))
    conn.commit()
    conn.close()

def add_filter(filter_type, value):
    conn = get_db()
    try:
        conn.execute("INSERT INTO filters (filter_type, value) VALUES (?, ?)", (filter_type, value))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def log_activity(status, source, target="", reason=""):
    conn = get_db()
    now = datetime.datetime.now()
    conn.execute("INSERT INTO activity_logs (timestamp, status, source, target, reason) VALUES (?, ?, ?, ?, ?)", 
                 (now, status, str(source), str(target), reason))
    
    date_str = now.strftime("%Y-%m-%d")
    conn.execute("INSERT OR IGNORE INTO statistics (date, processed, forwarded, rejected, errors) VALUES (?, 0, 0, 0, 0)", (date_str,))
    conn.execute("UPDATE statistics SET processed = processed + 1 WHERE date=?", (date_str,))
    
    if status == 'forwarded':
        conn.execute("UPDATE statistics SET forwarded = forwarded + 1 WHERE date=?", (date_str,))
    elif status == 'rejected':
        conn.execute("UPDATE statistics SET rejected = rejected + 1 WHERE date=?", (date_str,))
    elif status == 'error':
        conn.execute("UPDATE statistics SET errors = errors + 1 WHERE date=?", (date_str,))
    
    conn.commit()
    conn.close()
