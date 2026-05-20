from flask import Blueprint, render_template, request, current_app, abort, send_file
from flask_login import login_required, current_user
from utils import role_required
import os, sys, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

factures_bp = Blueprint('factures', __name__)


def _get_db():
    from modules.database import Database
    return Database(current_app.config['DATABASE_PATH'])


def _enrich(factures, mois_list):
    """Parse donnees_json and add nom_magasin / net_a_payer to each facture dict."""
    enriched = []
    for f in factures:
        row = dict(f)
        donnees = {}
        try:
            raw = row.get('donnees_json') or '{}'
            donnees = json.loads(raw)
        except Exception:
            pass
        row['nom_magasin']  = donnees.get('nom_magasin', '')
        row['net_a_payer']  = donnees.get('net_a_payer', 0)
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
    db = _get_db()
    societe      = request.args.get('societe', '').strip()
    mois         = request.args.get('mois',  type=int)
    annee        = request.args.get('annee', type=int)
    code_search  = request.args.get('code',  '').strip().upper()

    if current_user.is_fr:
        factures = db.get_factures(code_magasin=current_user.code_magasin,
                                   mois=mois, annee=annee)
    else:
        factures = db.get_factures(mois=mois, annee=annee)
        if societe:
            factures = [f for f in factures if f.get('societe') == societe]

    settings  = current_app.config['SETTINGS']
    mois_list = settings.get('mois', [])

    factures = _enrich(factures, mois_list)

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
    db = _get_db()
    factures = db.get_factures()
    fact = next((f for f in factures if f['id'] == fact_id), None)

    if not fact:
        abort(404)

    if current_user.is_fr and fact.get('code_magasin') != current_user.code_magasin:
        abort(403)

    settings  = current_app.config['SETTINGS']
    mois_list = settings.get('mois', [])

    row = _enrich([fact], mois_list)[0]
    return render_template('factures/detail.html', fact=row)


@factures_bp.route('/<int:fact_id>/download')
@login_required
def download(fact_id):
    db = _get_db()
    factures = db.get_factures()
    fact = next((f for f in factures if f['id'] == fact_id), None)

    if not fact:
        abort(404)

    if current_user.is_fr and fact.get('code_magasin') != current_user.code_magasin:
        abort(403)

    settings  = current_app.config['SETTINGS']
    mois_list = settings.get('mois', [])
    row = _enrich([fact], mois_list)[0]

    # Lire le chemin PDF depuis donnees_json en priorité, sinon colonne fichier_pdf
    pdf_path = (row['donnees'].get('fichier_pdf') or fact.get('fichier_pdf') or '').strip()

    if not pdf_path or not os.path.exists(pdf_path):
        return render_template('factures/pdf_unavailable.html', fact=row), 404

    return send_file(pdf_path, as_attachment=True,
                     download_name=os.path.basename(pdf_path))


@factures_bp.route('/magasins')
@login_required
@role_required('admin', 'agent')
def magasins():
    db = _get_db()
    societe  = request.args.get('societe')
    magasins = db.get_tous_magasins(societe if societe else None)
    return render_template('factures/magasins.html',
                           magasins=magasins,
                           selected_societe=societe)
