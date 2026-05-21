import io
import json
import os
import sqlite3
from flask import Blueprint, render_template, request, current_app, abort, send_file
from flask_login import login_required, current_user
from utils import role_required

factures_bp = Blueprint('factures', __name__)

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


def _get_factures(code_magasin=None, mois=None, annee=None):
    sql, params = "SELECT * FROM factures WHERE 1=1", []
    if code_magasin is not None:
        sql += " AND code_magasin = ?"; params.append(str(code_magasin))
    if mois is not None:
        sql += " AND mois = ?";         params.append(mois)
    if annee is not None:
        sql += " AND annee = ?";        params.append(annee)
    sql += " ORDER BY annee DESC, mois DESC, code_magasin"
    return _query(sql, params)


def _get_facture_by_id(fact_id):
    rows = _query("SELECT * FROM factures WHERE id = ?", (fact_id,))
    return rows[0] if rows else None


def _get_magasins(societe=None):
    if societe:
        return _query("SELECT * FROM magasins WHERE societe = ? ORDER BY code", (societe,))
    return _query("SELECT * FROM magasins ORDER BY societe, code")


def _enrich(factures, mois_list):
    enriched = []
    for f in factures:
        row = dict(f)
        donnees = {}
        try:
            donnees = json.loads(row.get('donnees_json') or '{}')
        except Exception:
            pass
        row['nom_magasin']    = donnees.get('nom_magasin', '')
        row['net_a_payer']    = donnees.get('net_a_payer', 0)
        row['numero_facture'] = donnees.get('numero_facture', '')
        row['date_facture']   = donnees.get('date_facture', '')
        row['donnees']        = donnees
        m = row.get('mois')
        row['mois_nom'] = mois_list[m - 1] if m and 1 <= m <= len(mois_list) else str(m or '')
        enriched.append(row)
    return enriched


@factures_bp.route('/')
@login_required
def index():
    societe     = request.args.get('societe', '').strip()
    mois        = request.args.get('mois',  type=int)
    annee       = request.args.get('annee', type=int)
    code_search = request.args.get('code',  '').strip().upper()

    if current_user.is_fr:
        factures = _get_factures(code_magasin=current_user.code_magasin, mois=mois, annee=annee)
    else:
        factures = _get_factures(mois=mois, annee=annee)
        if societe:
            factures = [f for f in factures if f.get('societe') == societe]

    mois_list = current_app.config['SETTINGS'].get('mois', [])
    factures  = _enrich(factures, mois_list)

    if code_search and not current_user.is_fr:
        factures = [f for f in factures
                    if code_search in str(f.get('code_magasin', '')).upper()
                    or code_search in f.get('nom_magasin', '').upper()]

    return render_template('factures/index.html',
                           factures=factures,
                           mois_list=mois_list,
                           selected_societe=societe,
                           selected_mois=mois,
                           selected_annee=annee,
                           selected_code=code_search)


@factures_bp.route('/<int:fact_id>/detail')
@login_required
def detail(fact_id):
    fact = _get_facture_by_id(fact_id)
    if not fact:
        abort(404)
    if current_user.is_fr and fact.get('code_magasin') != current_user.code_magasin:
        abort(403)

    mois_list = current_app.config['SETTINGS'].get('mois', [])
    return render_template('factures/detail.html', fact=_enrich([fact], mois_list)[0])


@factures_bp.route('/<int:fact_id>/download')
@login_required
def download(fact_id):
    fact = _get_facture_by_id(fact_id)
    if not fact:
        abort(404)
    if current_user.is_fr and fact.get('code_magasin') != current_user.code_magasin:
        abort(403)

    mois_list = current_app.config['SETTINGS'].get('mois', [])
    row = _enrich([fact], mois_list)[0]

    pdf_path = (row['donnees'].get('fichier_pdf') or fact.get('fichier_pdf') or '').strip()
    if not pdf_path or not os.path.exists(pdf_path):
        return render_template('factures/pdf_unavailable.html', fact=row), 404

    return send_file(pdf_path, as_attachment=True,
                     download_name=os.path.basename(pdf_path))


@factures_bp.route('/<int:fact_id>/pdf')
@login_required
def pdf(fact_id):
    fact = _get_facture_by_id(fact_id)
    if not fact:
        abort(404)
    if current_user.is_fr and fact.get('code_magasin') != current_user.code_magasin:
        abort(403)

    try:
        donnees = json.loads(fact.get('donnees_json') or '{}')
    except Exception:
        donnees = {}

    if not donnees.get('mois_nom'):
        mois_list = current_app.config['SETTINGS'].get('mois', [])
        m = fact.get('mois')
        donnees['mois_nom'] = mois_list[m - 1] if m and 1 <= m <= len(mois_list) else str(m or '')

    from pdf_web import generate_pdf
    pdf_bytes = generate_pdf(donnees)

    num = donnees.get('numero_facture') or fact_id
    filename = f"facture_{num}.pdf"

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=False,
        download_name=filename,
    )


@factures_bp.route('/mon-espace')
@login_required
@role_required('fr')
def mon_espace():
    mois_list = current_app.config['SETTINGS'].get('mois', [])
    code      = current_user.code_magasin

    # Toutes les factures du magasin, enrichies
    factures = _enrich(_get_factures(code_magasin=code), mois_list)

    # Infos magasin
    rows = _query("SELECT nom, societe FROM magasins WHERE code = ?", (str(code),))
    magasin = rows[0] if rows else {'nom': '', 'societe': ''}

    # Année courante pour les stats
    from datetime import date
    annee_courante = date.today().year
    factures_annee = [f for f in factures if f.get('annee') == annee_courante]

    total_annee   = sum(float(f.get('net_a_payer') or 0) for f in factures_annee)
    nb_factures   = len(factures)
    derniere      = factures[0] if factures else None

    meilleur_mois = None
    if factures_annee:
        meilleur_mois = max(factures_annee, key=lambda f: float(f.get('net_a_payer') or 0))

    # Données graphique — 12 derniers mois glissants
    from datetime import date
    today  = date.today()
    labels, values = [], []
    for i in range(11, -1, -1):
        month = today.month - i
        year  = today.year
        while month <= 0:
            month += 12
            year  -= 1
        labels.append(mois_list[month - 1][:3] if mois_list else str(month))
        match = next((f for f in factures if f.get('mois') == month and f.get('annee') == year), None)
        values.append(float(match.get('net_a_payer') or 0) if match else 0)

    return render_template('factures/mon_espace.html',
                           factures=factures,
                           mois_list=mois_list,
                           magasin=magasin,
                           code=code,
                           total_annee=total_annee,
                           nb_factures=nb_factures,
                           derniere=derniere,
                           meilleur_mois=meilleur_mois,
                           annee_courante=annee_courante,
                           chart_labels=labels,
                           chart_values=values)


@factures_bp.route('/magasins')
@login_required
@role_required('admin', 'agent')
def magasins():
    societe  = request.args.get('societe')
    magasins = _get_magasins(societe or None)
    return render_template('factures/magasins.html',
                           magasins=magasins,
                           selected_societe=societe)
