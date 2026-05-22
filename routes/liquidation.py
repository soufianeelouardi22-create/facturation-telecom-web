import io
import json
import os
import sqlite3
import sys
from datetime import datetime

from flask import (Blueprint, render_template, request, current_app,
                   abort, send_file, flash, redirect, url_for)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from utils import role_required

liquidation_bp = Blueprint('liquidation', __name__)

MOIS_NOMS = [
    'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
    'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]

# Racine du projet (C:\FacturationTelecom\)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

DB_PATH = os.environ.get(
    'DATABASE_PATH',
    os.path.join(os.path.dirname(__file__), '..', 'config', 'database_web.db')
)

# Fichiers uploadés dans data/uploads/liquidation/SOCIETE/ANNEE/MM/
UPLOAD_BASE = os.path.join(_PROJECT_ROOT, 'data', 'uploads', 'liquidation')

# Préfixe PythonAnywhere pour la conversion des chemins desktop
_PA_ROOT = '/home/soufianeelouardi/facturation-telecom-web'


def _localiser_chemin(stored_path):
    """Traduit un chemin desktop stocké vers le chemin local valide.

    Sur Windows (desktop) le chemin existe tel quel.
    Sur PythonAnywhere, remplace C:\\FacturationTelecom\\ par /home/.../facturation-telecom-web/.
    Retourne None si le chemin est vide ou non résolvable.
    """
    if not stored_path:
        return None
    if os.path.exists(stored_path):
        return stored_path
    # Normaliser les séparateurs puis remplacer le préfixe Windows
    p = stored_path.replace('\\', '/')
    for win_pfx in ('C:/FacturationTelecom', 'c:/facturationtelecom'):
        if p.lower().startswith(win_pfx.lower()):
            return _PA_ROOT + p[len(win_pfx):]
    return None

# Colonnes de primes : (clé_json, libellé_affiché)
COLONNES = [
    ('airtime_prepaye',       'Airtime Prépayé'),
    ('airtime_postpaye',      'Airtime Postpayé'),
    ('prime_inscription',     'Prime Inscription'),
    ('qte_inscription',       'Qté Inscr.'),
    ('prime_acces',           "Prime d'Accès"),
    ('prime_enseigne_mobile', 'Enseigne Mobile'),
    ('prime_enseigne_fixe',   'Enseigne Fixe'),
    ('comm_fixe_global',      'Comm. Fixe'),
    ('pa_fixe_global',        'PA Fixe'),
    ('prime_objectif_mobile', 'Obj. Mobile'),
    ('prime_objectif_fixe',   'Obj. Fixe'),
    ('penalite',              'Pénalité'),
]

CHAMPS_MONTANT = [k for k, _ in COLONNES if k != 'qte_inscription']


# ── Helpers DB ───────────────────────────────────────────────────────────────

def _db():
    con = sqlite3.connect(os.path.abspath(DB_PATH))
    con.row_factory = sqlite3.Row
    return con


def init_tables():
    """Crée la table liquidations si absente. Appelée depuis app.py au démarrage."""
    con = sqlite3.connect(os.path.abspath(DB_PATH))
    con.execute('''
        CREATE TABLE IF NOT EXISTS liquidations (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            mois              INTEGER NOT NULL,
            annee             INTEGER NOT NULL,
            societe           TEXT    NOT NULL,
            nb_codes          INTEGER DEFAULT 0,
            total_commissions REAL    DEFAULT 0,
            resultats_json    TEXT,
            created_at        TEXT,
            created_by        TEXT,
            UNIQUE(mois, annee, societe)
        )
    ''')
    con.commit()
    con.close()


def _total(primes):
    """Somme des champs montant d'un dict de primes."""
    return sum(float(primes.get(k) or 0) for k in CHAMPS_MONTANT)


# ── Adaptateur DB pour LiquidationProcessor ─────────────────────────────────

class _DBAdapter:
    """Fournit get_connection() attendu par LiquidationProcessor._get_codes_fr()."""
    def __init__(self, path):
        self._path = path

    def get_connection(self):
        return sqlite3.connect(self._path)


# ── Traitement fichiers liquidation ─────────────────────────────────────────

def _charger_processor():
    """Importe LiquidationProcessor depuis les modules desktop via sys.path."""
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)

    from modules.liquidation_processor import LiquidationProcessor
    proc = LiquidationProcessor()

    # Charger les vrais coefficients si disponibles (sinon fallback interne)
    coef_path = os.path.join(_PROJECT_ROOT, 'config', 'coefficients.json')
    if os.path.exists(coef_path):
        with open(coef_path, 'r', encoding='utf-8') as f:
            proc.coefficients = json.load(f)

    return proc


def _traiter_fichiers(paths, societe):
    """
    Lance LiquidationProcessor sur les 4 fichiers Excel et retourne
    l'état complet {code: {prime: valeur, ...}} pour tous les codes FR.
    """
    proc = _charger_processor()

    mobile_data = proc.lire_fichier_mobile(paths['mobile'])      if paths.get('mobile')    else {}
    darbox_data = proc.lire_fichier_darbox(paths['darbox'])      if paths.get('darbox')    else {}
    b2b_data    = proc.lire_fichier_fixe_b2b(paths['fixe_b2b']) if paths.get('fixe_b2b') else {}
    b2c_data    = proc.lire_fichier_fixe_b2c(paths['fixe_b2c']) if paths.get('fixe_b2c') else {}

    return proc.calculer_etat_complet(
        mobile_data, darbox_data, b2b_data, b2c_data,
        _DBAdapter(os.path.abspath(DB_PATH)),
        societe,
    )


# ── Routes ───────────────────────────────────────────────────────────────────

@liquidation_bp.route('/')
@login_required
@role_required('admin', 'agent')
def index():
    f_mois    = request.args.get('mois',    type=int)
    f_annee   = request.args.get('annee',   type=int)
    f_societe = request.args.get('societe', '').strip()

    con = _db()

    # ── 1. Lire fichiers_liquidation (synced depuis desktop) ──────────
    sql    = 'SELECT * FROM fichiers_liquidation WHERE 1=1'
    params = []
    if f_mois:
        sql += ' AND mois = ?';    params.append(f_mois)
    if f_annee:
        sql += ' AND annee = ?';   params.append(f_annee)
    if f_societe:
        sql += ' AND societe = ?'; params.append(f_societe)
    sql += ' ORDER BY annee DESC, mois DESC, societe'

    try:
        fl_rows = con.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        fl_rows = []  # table pas encore synchronisée depuis le desktop

    # ── 2. Index des calculs déjà effectués (table web) ───────────────
    try:
        liq_rows  = con.execute(
            'SELECT mois, annee, societe, nb_codes, total_commissions FROM liquidations'
        ).fetchall()
        liq_index = {(r['mois'], r['annee'], r['societe']): dict(r) for r in liq_rows}
    except sqlite3.OperationalError:
        liq_index = {}

    con.close()

    liquidations = []
    for r in fl_rows:
        d = dict(r)
        m = d.get('mois')
        d['mois_nom']   = MOIS_NOMS[m - 1] if m and 1 <= m <= 12 else str(m or '')
        d['a_mobile']   = bool(_localiser_chemin(d.get('fichier_mobile')))
        d['a_darbox']   = bool(_localiser_chemin(d.get('fichier_darbox')))
        d['a_fixe_b2b'] = bool(_localiser_chemin(d.get('fichier_fixe_b2b')))
        d['a_fixe_b2c'] = bool(_localiser_chemin(d.get('fichier_fixe_b2c')))
        d['calcule']    = liq_index.get((d['mois'], d['annee'], d['societe']))
        liquidations.append(d)

    return render_template('liquidation/index.html',
                           liquidations=liquidations,
                           MOIS_NOMS=MOIS_NOMS,
                           f_mois=f_mois,
                           f_annee=f_annee,
                           f_societe=f_societe)


@liquidation_bp.route('/import', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'agent')
def import_liq():
    # Pré-remplissage depuis query string (lien "Calculer" du tableau index)
    pre_mois    = request.args.get('mois',    type=int)
    pre_annee   = request.args.get('annee',   type=int)
    pre_societe = request.args.get('societe', '')

    if request.method == 'POST':
        mois    = request.form.get('mois',    type=int)
        annee   = request.form.get('annee',   type=int)
        societe = request.form.get('societe', '').strip()

        if not mois or not annee or not societe:
            flash('Mois, année et société sont obligatoires.', 'danger')
            return render_template('liquidation/import.html',
                                   MOIS_NOMS=MOIS_NOMS,
                                   pre_mois=mois, pre_annee=annee, pre_societe=societe)

        # ── Sauvegarder les fichiers dans data/uploads/liquidation/SOCIETE/ANNEE/MM/
        dossier = os.path.join(UPLOAD_BASE, societe, str(annee), f"{mois:02d}")
        os.makedirs(dossier, exist_ok=True)

        paths = {}
        for champ in ('mobile', 'darbox', 'fixe_b2b', 'fixe_b2c'):
            f = request.files.get(champ)
            if f and f.filename:
                nom  = secure_filename(f"{champ}_{f.filename}")
                dest = os.path.join(dossier, nom)
                f.save(dest)
                paths[champ] = dest

        # Fallback : utiliser les chemins depuis fichiers_liquidation si disponibles sur ce serveur
        if not paths:
            try:
                con_fl = _db()
                fl = con_fl.execute(
                    'SELECT * FROM fichiers_liquidation WHERE mois=? AND annee=? AND societe=?',
                    (mois, annee, societe)
                ).fetchone()
                con_fl.close()
                if fl:
                    for champ, col in [('mobile',   'fichier_mobile'),
                                       ('darbox',   'fichier_darbox'),
                                       ('fixe_b2b', 'fichier_fixe_b2b'),
                                       ('fixe_b2c', 'fichier_fixe_b2c')]:
                        resolved = _localiser_chemin(fl[col] if fl[col] else None)
                        if resolved:
                            paths[champ] = resolved
            except Exception:
                pass

        if not paths:
            flash('Aucun fichier uploadé et aucun fichier trouvé en base.', 'danger')
            return render_template('liquidation/import.html',
                                   MOIS_NOMS=MOIS_NOMS,
                                   pre_mois=mois, pre_annee=annee, pre_societe=societe)

        # ── Traitement
        try:
            etat = _traiter_fichiers(paths, societe)
        except ImportError:
            flash("Module liquidation_processor introuvable. "
                  "Vérifiez que le dossier modules/ est accessible depuis le web.", 'danger')
            return render_template('liquidation/import.html',
                                   MOIS_NOMS=MOIS_NOMS,
                                   pre_mois=mois, pre_annee=annee, pre_societe=societe)
        except Exception as e:
            flash(f'Erreur traitement fichiers : {e}', 'danger')
            return render_template('liquidation/import.html',
                                   MOIS_NOMS=MOIS_NOMS,
                                   pre_mois=mois, pre_annee=annee, pre_societe=societe)

        nb_codes = len(etat)
        total    = sum(_total(v) for v in etat.values())

        # ── Sauvegarder en DB (remplace si même mois/annee/societe)
        con = _db()
        con.execute('''
            INSERT OR REPLACE INTO liquidations
            (mois, annee, societe, nb_codes, total_commissions,
             resultats_json, created_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            mois, annee, societe, nb_codes, total,
            json.dumps(etat, ensure_ascii=False),
            datetime.now().isoformat(timespec='seconds'),
            current_user.username,
        ))
        con.commit()
        con.close()

        flash(
            f'Liquidation {MOIS_NOMS[mois - 1]} {annee} — {societe} calculée : '
            f'{nb_codes} codes, total {total:,.2f} MAD.',
            'success'
        )
        return redirect(url_for('liquidation.detail',
                                mois=mois, annee=annee, societe=societe))

    return render_template('liquidation/import.html',
                           MOIS_NOMS=MOIS_NOMS,
                           pre_mois=pre_mois,
                           pre_annee=pre_annee,
                           pre_societe=pre_societe)


@liquidation_bp.route('/<int:mois>/<int:annee>/<societe>/detail')
@login_required
@role_required('admin', 'agent')
def detail(mois, annee, societe):
    con = _db()
    row      = con.execute(
        'SELECT * FROM liquidations WHERE mois=? AND annee=? AND societe=?',
        (mois, annee, societe)
    ).fetchone()
    mag_rows = con.execute('SELECT code, nom FROM magasins').fetchall()
    con.close()

    if not row:
        abort(404)

    mag_noms = {str(r['code']): r['nom'] for r in mag_rows}
    mois_nom = MOIS_NOMS[mois - 1] if 1 <= mois <= 12 else str(mois)

    try:
        etat = json.loads(row['resultats_json'] or '{}')
    except Exception:
        etat = {}

    lignes = []
    for code, primes in sorted(etat.items()):
        lignes.append({
            'code':   code,
            'nom':    mag_noms.get(str(code), ''),
            'primes': primes,
            'total':  _total(primes),
        })

    # Totaux par colonne (calculés en Python, pas en Jinja2)
    col_totals = {
        champ: sum(float(l['primes'].get(champ) or 0) for l in lignes)
        for champ, _ in COLONNES
    }
    total_global = sum(l['total'] for l in lignes)

    return render_template('liquidation/detail.html',
                           row=dict(row),
                           mois_nom=mois_nom,
                           lignes=lignes,
                           colonnes=COLONNES,
                           col_totals=col_totals,
                           total_global=total_global)


@liquidation_bp.route('/<int:mois>/<int:annee>/<societe>/export')
@login_required
@role_required('admin', 'agent')
def export(mois, annee, societe):
    con      = _db()
    row      = con.execute(
        'SELECT * FROM liquidations WHERE mois=? AND annee=? AND societe=?',
        (mois, annee, societe)
    ).fetchone()
    mag_rows = con.execute('SELECT code, nom FROM magasins').fetchall()
    con.close()

    if not row:
        abort(404)

    mag_noms = {str(r['code']): r['nom'] for r in mag_rows}
    mois_nom = MOIS_NOMS[mois - 1] if 1 <= mois <= 12 else str(mois)

    try:
        etat = json.loads(row['resultats_json'] or '{}')
    except Exception:
        etat = {}

    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{mois_nom[:3]} {annee}"

    hdr_fill = PatternFill('solid', fgColor='1E3A5F')
    hdr_font = Font(bold=True, color='FFFFFF', size=10)
    num_fmt  = '#,##0.00'

    headers = ['Code', 'Nom Magasin'] + [lbl for _, lbl in COLONNES] + ['TOTAL']
    for ci, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=ci, value=h)
        cell.font      = hdr_font
        cell.fill      = hdr_fill
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
    ws.row_dimensions[1].height = 30

    total_global = 0.0
    col_totals   = {champ: 0.0 for champ, _ in COLONNES}

    for ri, (code, primes) in enumerate(sorted(etat.items()), 2):
        total = _total(primes)
        total_global += total
        vals = [code, mag_noms.get(str(code), '')]
        for champ, _ in COLONNES:
            v = round(float(primes.get(champ) or 0), 2)
            col_totals[champ] += v
            vals.append(v)
        vals.append(round(total, 2))
        for ci, v in enumerate(vals, 1):
            cell = ws.cell(row=ri, column=ci, value=v)
            if ci > 2:
                cell.number_format = num_fmt

    # ── Ligne totaux
    last       = len(etat) + 2
    tot_fill   = PatternFill('solid', fgColor='EFF6FF')
    tot_font   = Font(bold=True, color='1E40AF', size=10)
    ws.cell(row=last, column=2, value='TOTAL').font = tot_font
    for ci, (champ, _) in enumerate(COLONNES, 3):
        cell = ws.cell(row=last, column=ci, value=round(col_totals[champ], 2))
        cell.font          = tot_font
        cell.fill          = tot_fill
        cell.number_format = num_fmt
    grand = ws.cell(row=last, column=len(headers), value=round(total_global, 2))
    grand.font          = tot_font
    grand.fill          = tot_fill
    grand.number_format = num_fmt

    # ── Largeurs colonnes
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 24
    for ci in range(3, len(headers) + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(ci)].width = 15

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"liquidation_{societe}_{annee}_{mois:02d}.xlsx"
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename,
    )
