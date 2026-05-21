from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

ROLES = ('admin', 'agent', 'fr')

class User(UserMixin, db.Model):
    __tablename__ = 'web_users'

    id          = db.Column(db.Integer, primary_key=True)
    username    = db.Column(db.String(64),  unique=True, nullable=False)
    email       = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role        = db.Column(db.String(16),  nullable=False, default='agent')  # admin | agent | fr
    societe     = db.Column(db.String(32),  nullable=True)   # BESTMARK | AFRINETWORKS (pour role fr)
    code_magasin = db.Column(db.String(16), nullable=True)   # code POS (pour role fr)
    nom_complet          = db.Column(db.String(128), nullable=True)
    actif                = db.Column(db.Boolean, default=True)
    must_change_password = db.Column(db.Boolean, default=False)
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)
    last_login           = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # ── Helpers rôles ──────────────────────────────────────────────
    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_agent(self):
        return self.role == 'agent'

    @property
    def is_fr(self):
        return self.role == 'fr'

    def can(self, action):
        """Vérifie permission selon rôle."""
        permissions = {
            'admin': {'view_all', 'generate', 'manage_users', 'manage_magasins',
                      'liquidation', 'historique', 'export'},
            'agent': {'view_all', 'generate', 'manage_magasins',
                      'liquidation', 'historique', 'export'},
            'fr':    {'view_own', 'historique_own'},
        }
        return action in permissions.get(self.role, set())

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'
