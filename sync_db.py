"""
sync_db.py — Synchronise les tables métier depuis la DB desktop vers la DB web.

Usage :
    python sync_db.py
    python sync_db.py --src /chemin/vers/database.db --dst /chemin/vers/database_web.db

Tables copiées  : magasins, factures, types_magasins
Tables ignorées : web_users (gérée exclusivement par Flask-SQLAlchemy)
"""

import sqlite3
import os
import shutil
import argparse
from datetime import datetime

BASE_DIR   = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DEFAULT_SRC = os.environ.get(
    'DATABASE_PATH',
    os.path.join(BASE_DIR, 'config', 'database.db')
)
DEFAULT_DST = os.environ.get(
    'DATABASE_WEB_PATH',
    os.path.join(os.path.dirname(__file__), 'config', 'database_web.db')
)

TABLES_TO_SYNC = ('magasins', 'factures', 'types_magasins')


def get_create_sql(src_con, table):
    row = src_con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row[0] if row else None


def sync(src_path=DEFAULT_SRC, dst_path=DEFAULT_DST, verbose=True):
    def log(msg):
        if verbose:
            print(msg)

    # Vérifications
    if not os.path.exists(src_path):
        raise FileNotFoundError(f'DB source introuvable : {src_path}')

    os.makedirs(os.path.dirname(dst_path), exist_ok=True)

    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(dst_path)
    src.row_factory = sqlite3.Row

    log(f'\n[sync_db] {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    log(f'  Source : {src_path}')
    log(f'  Dest   : {dst_path}')
    log(f'  Tables : {", ".join(TABLES_TO_SYNC)}\n')

    total_rows = 0

    for table in TABLES_TO_SYNC:
        # Récupérer le CREATE TABLE depuis la source
        create_sql = get_create_sql(src, table)
        if not create_sql:
            log(f'  [SKIP] {table} — table absente dans la source')
            continue

        # Recréer la table dans la destination (DROP + CREATE pour rester en sync)
        dst.execute(f'DROP TABLE IF EXISTS {table}')
        dst.execute(create_sql)

        # Copier toutes les lignes
        rows = src.execute(f'SELECT * FROM {table}').fetchall()
        if rows:
            placeholders = ', '.join(['?'] * len(rows[0]))
            dst.executemany(
                f'INSERT INTO {table} VALUES ({placeholders})',
                [tuple(r) for r in rows]
            )

        dst.commit()
        log(f'  [OK] {table:25s} {len(rows):>6} lignes copiées')
        total_rows += len(rows)

    # S'assurer que web_users existe dans la destination (sans la toucher si elle existe déjà)
    dst.execute('''
        CREATE TABLE IF NOT EXISTS web_users (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            username       TEXT    NOT NULL UNIQUE,
            email          TEXT,
            password_hash  TEXT    NOT NULL,
            role           TEXT    NOT NULL DEFAULT 'agent',
            societe        TEXT,
            code_magasin   TEXT,
            actif          INTEGER NOT NULL DEFAULT 1,
            created_at     TEXT,
            last_login     TEXT
        )
    ''')
    dst.commit()

    src.close()
    dst.close()

    log(f'\n  Total : {total_rows} lignes synchronisées.')
    log(f'  web_users : préservée (non synchronisée depuis le desktop).\n')
    return total_rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Sync desktop DB → web DB')
    parser.add_argument('--src', default=DEFAULT_SRC, help='Chemin DB source (desktop)')
    parser.add_argument('--dst', default=DEFAULT_DST, help='Chemin DB destination (web)')
    args = parser.parse_args()

    try:
        sync(src_path=args.src, dst_path=args.dst)
    except FileNotFoundError as e:
        print(f'[ERREUR] {e}')
        raise SystemExit(1)
