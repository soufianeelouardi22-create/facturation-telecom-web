from flask import Blueprint, render_template, current_app, abort
from flask_login import login_required, current_user
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
def dashboard():
    from modules.database import Database
    db_path = current_app.config['DATABASE_PATH']
    db = Database(db_path)

    stats = {}
    try:
        if current_user.is_fr:
            # FR ne voit que ses propres données
            factures = db.get_factures(code_magasin=current_user.code_magasin)
            stats['mes_factures'] = len(factures)
            stats['mon_code'] = current_user.code_magasin
        else:
            magasins_best = db.get_tous_magasins('BESTMARK')
            magasins_afri = db.get_tous_magasins('AFRINETWORKS')
            factures      = db.get_factures()
            stats['magasins_best'] = len(magasins_best)
            stats['magasins_afri'] = len(magasins_afri)
            stats['total_factures'] = len(factures)
    except Exception:
        pass

    return render_template('dashboard.html', stats=stats)


@main_bp.app_errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


@main_bp.app_errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404
