import sqlite3
from flask import current_app


def _connect():
    path = current_app.config['DATABASE_PATH']
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def get_factures(code_magasin=None, mois=None, annee=None):
    sql    = "SELECT * FROM factures WHERE 1=1"
    params = []
    if code_magasin is not None:
        sql += " AND code_magasin = ?"
        params.append(str(code_magasin))
    if mois is not None:
        sql += " AND mois = ?"
        params.append(mois)
    if annee is not None:
        sql += " AND annee = ?"
        params.append(annee)
    sql += " ORDER BY annee DESC, mois DESC, code_magasin"
    with _connect() as con:
        rows = con.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_facture_by_id(fact_id):
    with _connect() as con:
        row = con.execute("SELECT * FROM factures WHERE id = ?", (fact_id,)).fetchone()
    return dict(row) if row else None


def get_tous_magasins(societe=None):
    sql    = "SELECT * FROM magasins WHERE 1=1"
    params = []
    if societe:
        sql += " AND societe = ?"
        params.append(societe)
    sql += " ORDER BY societe, code"
    with _connect() as con:
        rows = con.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
