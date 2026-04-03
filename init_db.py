import sqlite3

def init_db():
    conn = sqlite3.connect('agent_storage.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT,
            input_text TEXT,
            output_text TEXT,
            model_used TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized: agent_storage.db")

if __name__ == "__main__":
    init_db()
