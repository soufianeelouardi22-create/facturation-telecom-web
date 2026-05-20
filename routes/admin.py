from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models.user import db, User, ROLES
from utils import role_required

admin_bp = Blueprint('admin', __name__)


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
    if request.method == 'POST':
        username     = request.form.get('username', '').strip()
        email        = request.form.get('email', '').strip() or None
        password     = request.form.get('password', '')
        role         = request.form.get('role', 'agent')
        societe      = request.form.get('societe', '') or None
        code_magasin = request.form.get('code_magasin', '').strip() or None

        if not username or not password:
            flash('Username et mot de passe obligatoires.', 'danger')
            return render_template('admin/user_form.html', roles=ROLES, action='Créer')

        if User.query.filter_by(username=username).first():
            flash('Ce username existe déjà.', 'danger')
            return render_template('admin/user_form.html', roles=ROLES, action='Créer')

        user = User(username=username, email=email, role=role,
                    societe=societe, code_magasin=code_magasin)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash(f'Utilisateur {username} créé.', 'success')
        return redirect(url_for('admin.users'))

    return render_template('admin/user_form.html', roles=ROLES, action='Créer', user=None)


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
