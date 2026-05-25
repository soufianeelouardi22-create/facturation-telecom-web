"""
sync_db.py — Synchronise les tables métier depuis la DB desktop vers la DB web,
             puis upload vers PythonAnywhere et recharge l'app.

Usage :
    python sync_db.py                            # sync locale uniquement
    python sync_db.py --src /chemin/database.db  # source custom
    python sync_db.py --upload                   # sync + upload PythonAnywhere
"""

import sqlite3
import os
import argparse
import urllib.parse
from datetime import datetime

BASE_DIR    = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DEFAULT_SRC = os.environ.get(
    'DATABASE_PATH',
    os.path.join(BASE_DIR, 'config', 'database.db')
)
DEFAULT_DST = os.environ.get(
    'DATABASE_WEB_PATH',
    os.path.join(os.path.dirname(__file__), 'config', 'database_web.db')
)

TABLES_TO_SYNC = (
    'magasins',
    'factures',
    'types_magasins',
    'liquidation_mobile',
    'liquidation_darbox',
    'liquidation_fixe_b2b',
    'liquidation_fixe_b2c',
    'fichiers_liquidation',
    'parametres',
    'liquidations_web',
)

# ── PythonAnywhere ──────────────────────────────────────────────────────────
PA_USERNAME = 'soufianeelouardi'
PA_TOKEN    = '882c64f647961f73bfca9a7325851b23235466e3'
PA_BASE     = f'https://www.pythonanywhere.com/api/v0/user/{PA_USERNAME}'
PA_FILE_URL = (f'{PA_BASE}/files/path/home/{PA_USERNAME}/'
               'facturation-telecom-web/config/database_web.db')
PA_RELOAD_URL = f'{PA_BASE}/webapps/{PA_USERNAME}.pythonanywhere.com/reload/'


def get_create_sql(src_con, table):
    row = src_con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row[0] if row else None


def sync(src_path=DEFAULT_SRC, dst_path=DEFAULT_DST, verbose=True):
    def log(msg):
        if verbose:
            print(msg)

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
        create_sql = get_create_sql(src, table)
        if not create_sql:
            log(f'  [SKIP] {table} — table absente dans la source')
            continue

        dst.execute(f'DROP TABLE IF EXISTS {table}')
        dst.execute(create_sql)

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


def _multipart_upload(url, local_path, headers, log):
    """Upload un fichier local vers PythonAnywhere via multipart/form-data. Retourne True si OK."""
    import urllib.request
    import urllib.error

    with open(local_path, 'rb') as f:
        file_data = f.read()

    boundary  = b'----PASyncBoundary'
    fname     = os.path.basename(local_path).encode()
    body = (
        b'--' + boundary + b'\r\n'
        b'Content-Disposition: form-data; name="content"; filename="' + fname + b'"\r\n'
        b'Content-Type: application/octet-stream\r\n\r\n'
        + file_data + b'\r\n'
        b'--' + boundary + b'--\r\n'
    )
    req = urllib.request.Request(
        url, data=body,
        headers={**headers, 'Content-Type': f'multipart/form-data; boundary={boundary.decode()}'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        if e.code not in (200, 201):
            log(f'    [ERREUR] HTTP {e.code} — {e.read().decode()[:200]}')
            return False
        status = e.code
    log(f'    [OK] HTTP {status}')
    return True


def nettoyer_pa_liquidation(verbose=True):
    """Supprime data/liquidation/ sur PythonAnywhere pour libérer le quota."""
    import urllib.request
    import urllib.error
    import json as _json

    def log(msg):
        if verbose:
            print(msg)

    headers  = {'Authorization': f'Token {PA_TOKEN}'}
    pa_dir   = f'/home/{PA_USERNAME}/facturation-telecom-web/data/liquidation'
    tree_url = f'{PA_BASE}/files/tree/?path={pa_dir}'

    log(f'[cleanup] Listage de {pa_dir}...')
    req = urllib.request.Request(tree_url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            fichiers = _json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log('[cleanup] Dossier introuvable sur PA — rien à supprimer.')
            return True
        log(f'[cleanup] Erreur listing : HTTP {e.code} — {e.read().decode()[:200]}')
        return False

    if not fichiers:
        log('[cleanup] Dossier déjà vide.')
        return True

    log(f'[cleanup] {len(fichiers)} fichier(s) à supprimer...')
    count = 0
    for fpath in fichiers:
        url = ('https://www.pythonanywhere.com/api/v0/user/{}/files/path{}'.format(
            PA_USERNAME, urllib.parse.quote(fpath, safe='/')))
        req = urllib.request.Request(url, headers=headers, method='DELETE')
        try:
            with urllib.request.urlopen(req) as _:
                pass
            log(f'  [DEL] {fpath}')
            count += 1
        except urllib.error.HTTPError as e:
            log(f'  [ERREUR] DELETE {fpath} : HTTP {e.code}')

    log(f'[cleanup] {count} fichier(s) supprimé(s).\n')
    return True


def upload_to_pythonanywhere(dst_path=DEFAULT_DST, verbose=True):
    """Sync locale → upload database_web.db → reload webapp PythonAnywhere."""
    def log(msg):
        if verbose:
            print(msg)

    import urllib.request
    import urllib.error

    headers = {'Authorization': f'Token {PA_TOKEN}'}

    # ── 1. Sync locale (database.db → database_web.db) ─────────────
    sync(dst_path=dst_path, verbose=verbose)

    # ── 2. Upload database_web.db ───────────────────────────────────
    log(f'[upload] Envoi database_web.db vers PythonAnywhere...')
    log(f'  URL : {PA_FILE_URL}')
    if not _multipart_upload(PA_FILE_URL, dst_path, headers, log):
        return False
    log(f'  [OK] Base de données uploadée')

    # ── 3. Reload webapp ────────────────────────────────────────────
    log(f'[reload] Rechargement de {PA_USERNAME}.pythonanywhere.com...')

    req = urllib.request.Request(
        PA_RELOAD_URL,
        data=b'',
        headers=headers,
        method='POST'
    )
    try:
        with urllib.request.urlopen(req) as resp:
            reload_status = resp.status
    except urllib.error.HTTPError as e:
        if e.code not in (200, 201):
            log(f'  [ERREUR] Reload échoué : HTTP {e.code} — {e.read().decode()}')
            return False
        reload_status = e.code

    log(f'  [OK] Webapp rechargée (HTTP {reload_status})')
    log('\n  Sync terminee\n')
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Sync desktop DB -> web DB (+ PythonAnywhere)')
    parser.add_argument('--src',     default=DEFAULT_SRC,  help='Chemin DB source (desktop)')
    parser.add_argument('--dst',     default=DEFAULT_DST,  help='Chemin DB destination (web)')
    parser.add_argument('--upload',  action='store_true',  help='Upload vers PythonAnywhere après sync')
    parser.add_argument('--cleanup', action='store_true',  help='Supprimer data/liquidation/ sur PA')
    args = parser.parse_args()

    try:
        if args.cleanup:
            ok = nettoyer_pa_liquidation()
            raise SystemExit(0 if ok else 1)
        elif args.upload:
            ok = upload_to_pythonanywhere(dst_path=args.dst)
            raise SystemExit(0 if ok else 1)
        else:
            sync(src_path=args.src, dst_path=args.dst)
    except FileNotFoundError as e:
        print(f'[ERREUR] {e}')
        raise SystemExit(1)
