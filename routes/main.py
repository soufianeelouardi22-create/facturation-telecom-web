import sqlite3
import os
from flask import Blueprint, render_template
from flask_login import login_required, current_user

main_bp = Blueprint('main', __name__)

DB_PATH = os.environ.get(
    'DATABASE_PATH',
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'database.db'))
)


def _query(sql, params=()):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(sql, params).fetchall()
    con.close()
    return [dict(r) for r in rows]


@main_bp.route('/')
@login_required
def dashboard():
    stats = {}
    try:
        if current_user.is_fr:
            factures = _query(
                "SELECT id FROM factures WHERE code_magasin = ?",
                (current_user.code_magasin,)
            )
            stats['mes_factures'] = len(factures)
            stats['mon_code']     = current_user.code_magasin
        else:
            stats['magasins_best']  = _query(
                "SELECT COUNT(*) AS n FROM magasins WHERE societe = ?", ('BESTMARK',)
            )[0]['n']
            stats['magasins_afri']  = _query(
                "SELECT COUNT(*) AS n FROM magasins WHERE societe = ?", ('AFRINETWORKS',)
            )[0]['n']
            stats['total_factures'] = _query(
                "SELECT COUNT(*) AS n FROM factures"
            )[0]['n']
    except Exception:
        pass

    return render_template('dashboard.html', stats=stats)


@main_bp.app_errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


@main_bp.app_errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404
