import sqlite3
import json
import os
from datetime import date
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


def _build_fr_stats(code, mois_list):
    """Calcule toutes les stats dashboard pour un utilisateur FR."""
    rows = _query(
        'SELECT mois, annee, donnees_json, fichier_pdf, id FROM factures '
        'WHERE code_magasin = ? ORDER BY annee DESC, mois DESC',
        (str(code),)
    )

    # Enrichir avec net_a_payer
    factures = []
    for r in rows:
        f = dict(r)
        try:
            d = json.loads(f.get('donnees_json') or '{}')
        except Exception:
            d = {}
        f['net_a_payer'] = float(d.get('net_a_payer') or 0)
        f['nom_magasin'] = d.get('nom_magasin', '')
        m = f.get('mois')
        f['mois_nom'] = mois_list[m - 1] if m and 1 <= m <= len(mois_list) else str(m or '')
        factures.append(f)

    today        = date.today()
    annee_cur    = today.year
    mois_cur     = today.month
    mois_prec    = mois_cur - 1 if mois_cur > 1 else 12
    annee_prec   = annee_cur if mois_cur > 1 else annee_cur - 1

    factures_annee = [f for f in factures if f['annee'] == annee_cur]
    total_annee    = sum(f['net_a_payer'] for f in factures_annee)
    nb_factures    = len(factures)

    meilleur_mois = max(factures_annee, key=lambda f: f['net_a_payer'], default=None)

    # Évolution mois courant vs mois précédent
    f_cur  = next((f for f in factures if f['mois'] == mois_cur  and f['annee'] == annee_cur),  None)
    f_prec = next((f for f in factures if f['mois'] == mois_prec and f['annee'] == annee_prec), None)
    evolution = None
    if f_cur and f_prec and f_prec['net_a_payer']:
        evolution = round((f_cur['net_a_payer'] - f_prec['net_a_payer']) / f_prec['net_a_payer'] * 100, 1)

    # 5 dernières factures
    dernieres = factures[:5]

    # Graphique 12 mois glissants
    chart_labels, chart_values = [], []
    for i in range(11, -1, -1):
        m = mois_cur - i
        a = annee_cur
        while m <= 0:
            m += 12; a -= 1
        chart_labels.append(mois_list[m - 1][:3] if mois_list else str(m))
        match = next((f for f in factures if f['mois'] == m and f['annee'] == a), None)
        chart_values.append(match['net_a_payer'] if match else 0)

    return {
        'total_annee':   total_annee,
        'nb_factures':   nb_factures,
        'meilleur_mois': meilleur_mois,
        'evolution':     evolution,
        'dernieres':     dernieres,
        'chart_labels':  chart_labels,
        'chart_values':  chart_values,
        'annee_cur':     annee_cur,
    }


@main_bp.route('/')
@login_required
def dashboard():
    stats    = {}
    fr_stats = None

    try:
        if current_user.is_fr:
            from flask import current_app
            mois_list = current_app.config['SETTINGS'].get('mois', [])
            fr_stats  = _build_fr_stats(current_user.code_magasin, mois_list)
            stats['mes_factures'] = fr_stats['nb_factures']
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

    return render_template('dashboard.html', stats=stats, fr_stats=fr_stats)


@main_bp.app_errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


@main_bp.app_errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404
