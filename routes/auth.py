from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from models.user import db, User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.must_change_password:
            return redirect(url_for('auth.premier_login'))
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        user = User.query.filter_by(username=username, actif=True).first()

        if user and user.check_password(password):
            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user, remember=remember)
            if user.must_change_password:
                return redirect(url_for('auth.premier_login'))
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))

        flash('Identifiants incorrects.', 'danger')

    return render_template('login.html')


@auth_bp.route('/premier-login', methods=['GET', 'POST'])
@login_required
def premier_login():
    if not current_user.must_change_password:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        nom_complet  = request.form.get('nom_complet', '').strip()
        new_password = request.form.get('new_password', '')
        confirm      = request.form.get('confirm_password', '')

        errors = []
        if not nom_complet:
            errors.append('Le nom complet est obligatoire.')
        if len(new_password) < 6:
            errors.append('Le mot de passe doit contenir au moins 6 caractères.')
        if new_password != confirm:
            errors.append('Les deux mots de passe ne correspondent pas.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('premier_login.html')

        current_user.nom_complet          = nom_complet
        current_user.must_change_password = False
        current_user.set_password(new_password)
        db.session.commit()

        flash(f'Bienvenue {nom_complet} ! Votre compte est maintenant configuré.', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('premier_login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Vous avez été déconnecté.', 'info')
    return redirect(url_for('auth.login'))
