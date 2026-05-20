import sqlite3
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models.user import db, User, ROLES
from utils import role_required

admin_bp = Blueprint('admin', __name__)

DB_PATH = os.environ.get(
    'DATABASE_PATH',
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'database.db'))
)


def _get_magasins():
    try:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT code, nom, societe FROM magasins ORDER BY societe, code"
        ).fetchall()
        con.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


@admin_bp.route('/users')
@login_required
@role_required('admin')
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users, roles=ROLES)


@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def create_user():
    magasins = _get_magasins()

    if request.method == 'POST':
        username     = request.form.get('username', '').strip()
        password     = request.form.get('password', '')
        role         = request.form.get('role', 'agent')
        societe      = request.form.get('societe', '').strip() or None
        code_magasin = request.form.get('code_magasin', '').strip() or None

        if not username or not password:
            flash('Username et mot de passe obligatoires.', 'danger')
            return render_template('admin/user_form.html', roles=ROLES,
                                   magasins=magasins, action='Créer', user=None)

        if len(password) < 6:
            flash('Mot de passe trop court (min 6 caractères).', 'danger')
            return render_template('admin/user_form.html', roles=ROLES,
                                   magasins=magasins, action='Créer', user=None)

        if User.query.filter_by(username=username).first():
            flash('Ce username existe déjà.', 'danger')
            return render_template('admin/user_form.html', roles=ROLES,
                                   magasins=magasins, action='Créer', user=None)

        # Pour rôle fr : code_magasin obligatoire
        if role == 'fr' and not code_magasin:
            flash('Un code magasin est obligatoire pour le rôle FR.', 'danger')
            return render_template('admin/user_form.html', roles=ROLES,
                                   magasins=magasins, action='Créer', user=None)

        user = User(username=username, role=role,
                    societe=societe, code_magasin=code_magasin)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash(f'Utilisateur {username} créé avec le rôle {role}.', 'success')
        return redirect(url_for('admin.users'))

    return render_template('admin/user_form.html', roles=ROLES,
                           magasins=magasins, action='Créer', user=None)


@admin_bp.route('/users/<int:uid>/toggle')
@login_required
@role_required('admin')
def toggle_user(uid):
    user = User.query.get_or_404(uid)
    if user.username == 'admin':
        flash('Impossible de désactiver le compte admin principal.', 'warning')
    else:
        user.actif = not user.actif
        db.session.commit()
        flash(f'Utilisateur {"activé" if user.actif else "désactivé"}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:uid>/delete', methods=['POST'])
@login_required
@role_required('admin')
def delete_user(uid):
    user = User.query.get_or_404(uid)
    if user.username == 'admin':
        flash('Impossible de supprimer le compte admin principal.', 'warning')
    elif user.id == current_user.id:
        flash('Vous ne pouvez pas supprimer votre propre compte.', 'warning')
    else:
        username = user.username
        db.session.delete(user)
        db.session.commit()
        flash(f'Utilisateur {username} supprimé.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:uid>/reset-password', methods=['POST'])
@login_required
@role_required('admin')
def reset_password(uid):
    user = User.query.get_or_404(uid)
    new_pass = request.form.get('new_password', '')
    if len(new_pass) < 6:
        flash('Mot de passe trop court (min 6 caractères).', 'danger')
    else:
        user.set_password(new_pass)
        db.session.commit()
        flash(f'Mot de passe de {user.username} réinitialisé.', 'success')
    return redirect(url_for('admin.users'))
