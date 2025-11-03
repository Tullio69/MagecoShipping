#!/usr/bin/env python3
"""
Script di migrazione database per aggiungere supporto batch.
"""
import sqlite3
from pathlib import Path
from magecoshipping.db.schema import DB_PATH


def check_column_exists(cursor, table_name: str, column_name: str) -> bool:
    """Verifica se una colonna esiste in una tabella."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def migrate_add_batch_support():
    """
    Migrazione: Aggiunge supporto per batch al database esistente.
    - Crea tabella batches se non esiste
    - Aggiunge colonna batch_id alla tabella documents se non esiste
    """
    print("🔄 Avvio migrazione database...")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        # 1. Crea tabella batches se non esiste
        cur.execute("""
            CREATE TABLE IF NOT EXISTS batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_name TEXT NOT NULL,
                num_documents INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending' NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Tabella 'batches' verificata/creata")

        # 2. Verifica se la colonna batch_id esiste già
        if not check_column_exists(cur, 'documents', 'batch_id'):
            print("⚙️  Aggiunta colonna 'batch_id' alla tabella 'documents'...")

            # SQLite non supporta ALTER TABLE con FOREIGN KEY direttamente
            # Dobbiamo aggiungere la colonna senza constraint prima
            cur.execute("ALTER TABLE documents ADD COLUMN batch_id INTEGER")
            print("✅ Colonna 'batch_id' aggiunta con successo")
        else:
            print("ℹ️  Colonna 'batch_id' già esistente, skip")

        conn.commit()
        print("✅ Migrazione completata con successo!")

    except Exception as e:
        conn.rollback()
        print(f"❌ Errore durante la migrazione: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    print("🚀 Script di migrazione database MagecoShipping\n")
    migrate_add_batch_support()
    print("\n✨ Database aggiornato e pronto per l'uso!")
