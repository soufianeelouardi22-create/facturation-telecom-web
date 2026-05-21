"""
Application Web — Facturation Telecom
Flask + Flask-Login + SQLAlchemy
"""
import os
import sys
import json
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

# Ajouter le dossier parent au path pour accéder aux modules desktop
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import config
from models.user import db, User
from utils import role_required  # noqa: F401 — re-exporté pour blueprints


def create_app(env='default'):
    app = Flask(__name__)
    app.config.from_object(config[env])

    # ── Extensions ─────────────────────────────────────────────────
    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ── Charger settings.json ───────────────────────────────────────
    try:
        with open(app.config['SETTINGS_PATH'], encoding='utf-8') as f:
            app.config['SETTINGS'] = json.load(f)
    except Exception:
        app.config['SETTINGS'] = {}

    # ── Context processor (variables globales templates) ───────────
    @app.context_processor
    def inject_globals():
        return {
            'societes': app.config['SETTINGS'].get('societes', {}),
            'now': datetime.utcnow(),
        }

    # ── Blueprints ──────────────────────────────────────────────────
    from routes.auth    import auth_bp
    from routes.main    import main_bp
    from routes.admin   import admin_bp
    from routes.factures import factures_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp,    url_prefix='/admin')
    app.register_blueprint(factures_bp, url_prefix='/factures')

    # ── Créer tables + admin par défaut ────────────────────────────
    with app.app_context():
        db.create_all()
        _creer_admin_defaut()

    return app


def _creer_admin_defaut():
    """Crée admin par défaut s'il n'existe pas encore."""
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            email='admin@facturation.local',
            role='admin',
            actif=True,
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('[INFO] Admin par défaut créé: admin / admin123')



if __name__ == '__main__':
    env  = os.environ.get('FLASK_ENV', 'development')
    port = int(os.environ.get('PORT', 5000))
    app  = create_app('production' if env == 'production' else 'development')
    app.run(host='0.0.0.0', port=port, debug=(env != 'production'))
