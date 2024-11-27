from flask import Flask, render_template, url_for, flash, redirect, request, jsonify
from flask_login import LoginManager, login_user, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
import os
import random
from urllib.parse import urlparse
from datetime import datetime, timedelta
from sqlalchemy import func, and_
from collections import defaultdict

from models import db, User, Group, Expense, ExpenseShare, GroupInvite, FriendRequest
from forms import LoginForm, RegistrationForm, GroupForm, ExpenseForm, AddFriendForm, GroupInviteForm, ProfileForm

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///splitwise.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

db.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def generate_username_suggestions(base_username):
    """Generate username suggestions when the requested username is taken."""
    suggestions = []
    
    # Add numbered versions
    counter = 1
    while len(suggestions) < 2 and counter < 100:
        suggestion = f"{base_username}{counter}"
        if User.query.filter_by(username=suggestion).first() is None:
            suggestions.append(suggestion)
        counter += 1
    
    # Add cool variations
    cool_suffixes = [
        "ninja", "pro", "master", "star", "ace", 
        "hero", "prime", "elite", "phoenix", "dragon",
        "champion", "legend", "warrior", "titan", "boss"
    ]
    
    while len(suggestions) < 3:
        suffix = random.choice(cool_suffixes)
        suggestion = f"{base_username}_{suffix}"
        if User.query.filter_by(username=suggestion).first() is None and suggestion not in suggestions:
            suggestions.append(suggestion)
    
    return suggestions

@app.route('/check_username')
def check_username():
    """Check if a username is available and return suggestions if it's taken."""
    username = request.args.get('username', '')
    
    if not username:
        return jsonify({'available': False, 'message': 'Username is required'})
    
    if len(username) < 2:
        return jsonify({'available': False, 'message': 'Username must be at least 2 characters long'})
    
    if not username.isalnum():
        return jsonify({'available': False, 'message': 'Username can only contain letters and numbers'})
    
    existing_user = User.query.filter_by(username=username).first()
    
    if existing_user is None:
        return jsonify({'available': True})
    else:
        suggestions = generate_username_suggestions(username)
        return jsonify({
            'available': False,
            'message': 'This username is already taken. Here are some suggestions:',
            'suggestions': suggestions
        })

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data)
        user = User(
            username=form.username.data,
            email=form.email.data or None,  # Convert empty string to None
            password=hashed_password
        )
        try:
            db.session.add(user)
            db.session.commit()
            flash('Your account has been created! You can now log in.', 'success')
            return redirect(url_for('login'))
        except IntegrityError:
            db.session.rollback()
            flash('An error occurred. Please try again.', 'danger')
            return render_template('register.html', form=form)
            
    return render_template('register.html', form=form)

@app.route('/profile/setup', methods=['GET', 'POST'])
@login_required
def profile_setup():
    # If user already has a display name, redirect to dashboard
    if current_user.display_name:
        return redirect(url_for('dashboard'))
    
    form = ProfileForm()
    if form.validate_on_submit():
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.display_name = f"{form.first_name.data} {form.last_name.data}"
        
        try:
            db.session.commit()
            flash('Your profile has been set up!', 'success')
            return redirect(url_for('dashboard'))
        except:
            db.session.rollback()
            flash('An error occurred. Please try again.', 'danger')
    
    return render_template('profile_setup.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if not current_user.display_name:
            return redirect(url_for('profile_setup'))
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                if not user.display_name:
                    next_page = url_for('profile_setup')
                else:
                    next_page = url_for('dashboard')
            return redirect(next_page)
        flash('Invalid username or password', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/search_users')
@login_required
def search_users():
    query = request.args.get('query', '')
    if len(query) < 2:
        return jsonify([])
    
    users = User.query.filter(
        User.username.ilike(f'%{query}%'),
        User.id != current_user.id
    ).limit(5).all()
    
    return jsonify([{
        'id': user.id,
        'username': user.username,
        'is_friend': user in current_user.friends
    } for user in users])

@app.route('/dashboard')
@login_required
def dashboard():
    groups = current_user.groups
    pending_invites = GroupInvite.query.filter_by(invitee=current_user, status='pending').all()
    return render_template('dashboard.html', groups=groups, pending_invites=pending_invites)

@app.route('/friends')
@login_required
def friends():
    friends = current_user.friends
    sent_requests = FriendRequest.query.filter_by(sender=current_user, status='pending').all()
    received_requests = FriendRequest.query.filter_by(receiver=current_user, status='pending').all()
    return render_template('friends.html', 
                         friends=friends,
                         sent_requests=sent_requests,
                         received_requests=received_requests)

@app.route('/send_friend_request/<int:user_id>', methods=['POST'])
@login_required
def send_friend_request(user_id):
    user = User.query.get_or_404(user_id)
    
    # Check if request already exists
    existing_request = FriendRequest.query.filter_by(
        sender=current_user,
        receiver=user,
        status='pending'
    ).first()
    
    if existing_request:
        flash('Friend request already sent!', 'info')
        return redirect(url_for('friends'))
    
    # Check if they're already friends
    if user in current_user.friends:
        flash('You are already friends!', 'info')
        return redirect(url_for('friends'))
    
    friend_request = FriendRequest(sender=current_user, receiver=user)
    db.session.add(friend_request)
    db.session.commit()
    
    flash(f'Friend request sent to {user.username}!', 'success')
    return redirect(url_for('friends'))

@app.route('/handle_friend_request/<int:request_id>/<string:action>')
@login_required
def handle_friend_request(request_id, action):
    friend_request = FriendRequest.query.get_or_404(request_id)
    
    if friend_request.receiver != current_user:
        flash('Invalid friend request.', 'danger')
        return redirect(url_for('friends'))
    
    if action == 'accept':
        # Add to friends list
        current_user.friends.append(friend_request.sender)
        friend_request.sender.friends.append(current_user)
        friend_request.status = 'accepted'
        flash('Friend request accepted!', 'success')
    else:
        friend_request.status = 'rejected'
        flash('Friend request rejected.', 'info')
    
    db.session.commit()
    return redirect(url_for('friends'))

@app.route('/group/new', methods=['GET', 'POST'])
@login_required
def create_group():
    form = GroupForm()
    form.members.choices = [(f.id, f.username) for f in current_user.friends.all()]
    
    if form.validate_on_submit():
        group = Group(name=form.name.data, created_by=current_user)
        group.members.append(current_user)
        for member_id in form.members.data:
            member = User.query.get(member_id)
            if member:
                group.members.append(member)
        db.session.add(group)
        db.session.commit()
        flash(f'Group "{group.name}" has been created!', 'success')
        return redirect(url_for('group_details', group_id=group.id))
    return render_template('create_group.html', form=form)

@app.route('/group/<int:group_id>')
@login_required
def group_details(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        flash('You are not a member of this group.', 'danger')
        return redirect(url_for('dashboard'))
    
    expenses = group.expenses
    invite_form = GroupInviteForm()
    invite_form.friend.choices = [(f.id, f.username) for f in current_user.friends.all() 
                                if f not in group.members]
    
    return render_template('group_details.html', group=group, expenses=expenses, invite_form=invite_form)

@app.route('/group/<int:group_id>/invite', methods=['POST'])
@login_required
def invite_to_group(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        flash('You are not a member of this group.', 'danger')
        return redirect(url_for('dashboard'))
    
    form = GroupInviteForm()
    form.friend.choices = [(f.id, f.username) for f in current_user.friends.all() 
                          if f not in group.members]
    
    if form.validate_on_submit():
        friend = User.query.get(form.friend.data)
        if friend:
            invite = GroupInvite(group=group, inviter=current_user, invitee=friend)
            db.session.add(invite)
            db.session.commit()
            flash(f'Invitation sent to {friend.username}!', 'success')
    return redirect(url_for('group_details', group_id=group_id))

@app.route('/invite/<int:invite_id>/<action>')
@login_required
def handle_invite(invite_id, action):
    invite = GroupInvite.query.get_or_404(invite_id)
    if invite.invitee != current_user:
        flash('Invalid invitation.', 'danger')
        return redirect(url_for('dashboard'))
    
    if action == 'accept':
        invite.status = 'accepted'
        invite.group.members.append(current_user)
        flash(f'You have joined {invite.group.name}!', 'success')
    elif action == 'reject':
        invite.status = 'rejected'
        flash('Invitation rejected.', 'info')
    
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/group/<int:group_id>/add_expense', methods=['GET', 'POST'])
@login_required
def add_expense(group_id):
    group = Group.query.get_or_404(group_id)
    if current_user not in group.members:
        flash('You are not a member of this group.', 'danger')
        return redirect(url_for('dashboard'))
    
    form = ExpenseForm()
    form.participants.choices = [(user.id, user.display_name or user.username) for user in group.members]
    
    if form.validate_on_submit():
        expense = Expense(
            description=form.description.data,
            amount=form.amount.data,
            category=form.category.data,
            paid_by=current_user,
            group=group
        )
        db.session.add(expense)
        
        participants = [User.query.get(user_id) for user_id in form.participants.data]
        if not participants:
            participants = group.members
            
        if form.split_type.data == 'equal':
            # Split equally among participants
            share_amount = expense.amount / len(participants)
            for user in participants:
                share = ExpenseShare(
                    expense=expense,
                    user=user,
                    amount=share_amount
                )
                db.session.add(share)
        else:
            # Custom split - redirect to custom split form
            try:
                db.session.commit()
                return redirect(url_for('custom_split', expense_id=expense.id))
            except:
                db.session.rollback()
                flash('An error occurred. Please try again.', 'danger')
                return render_template('add_expense.html', form=form, group=group)
        
        try:
            db.session.commit()
            flash('Expense added successfully!', 'success')
            return redirect(url_for('group_details', group_id=group.id))
        except:
            db.session.rollback()
            flash('An error occurred. Please try again.', 'danger')
    
    return render_template('add_expense.html', form=form, group=group)

@app.route('/expense/<int:expense_id>/custom_split', methods=['GET', 'POST'])
@login_required
def custom_split(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    if current_user not in expense.group.members:
        flash('You are not a member of this group.', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        total_percentage = 0
        shares = []
        
        for user in expense.group.members:
            percentage = float(request.form.get(f'share_{user.id}', 0))
            total_percentage += percentage
            shares.append((user, percentage))
        
        if abs(total_percentage - 100) > 0.01:  # Allow for small floating-point errors
            flash('Total percentage must equal 100%.', 'danger')
            return render_template('custom_split.html', expense=expense)
        
        # Create expense shares
        for user, percentage in shares:
            share_amount = (percentage / 100) * expense.amount
            share = ExpenseShare(
                expense=expense,
                user=user,
                amount=share_amount
            )
            db.session.add(share)
        
        try:
            db.session.commit()
            flash('Custom split saved successfully!', 'success')
            return redirect(url_for('group_details', group_id=expense.group.id))
        except:
            db.session.rollback()
            flash('An error occurred. Please try again.', 'danger')
    
    return render_template('custom_split.html', expense=expense)

@app.route('/expense/<int:expense_id>/settle', methods=['POST'])
@login_required
def settle_expense(expense_id):
    share = ExpenseShare.query.filter_by(
        expense_id=expense_id,
        user=current_user
    ).first_or_404()
    
    share.paid = True
    db.session.commit()
    flash('Payment marked as settled!', 'success')
    return redirect(url_for('group_details', group_id=share.expense.group_id))

@app.route('/analytics')
@login_required
def analytics():
    # Default to monthly view
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # Get spending data
    expenses = Expense.query.filter(
        and_(
            Expense.date >= start_date,
            Expense.date <= end_date,
            Expense.paid_by_id == current_user.id
        )
    ).order_by(Expense.date).all()
    
    dates = []
    spending_data = []
    daily_totals = defaultdict(float)
    
    for expense in expenses:
        date_str = expense.date.strftime('%Y-%m-%d')
        daily_totals[date_str] += expense.amount
    
    for date in (start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)):
        date_str = date.strftime('%Y-%m-%d')
        dates.append(date_str)
        spending_data.append(daily_totals[date_str])
    
    # Get top spenders
    top_spenders = db.session.query(
        User,
        func.sum(Expense.amount).label('total_amount')
    ).join(Expense, User.id == Expense.paid_by_id)\
     .group_by(User.id)\
     .order_by(func.sum(Expense.amount).desc())\
     .limit(5).all()
    
    spenders_labels = [s[0].display_name or s[0].username for s in top_spenders]
    spenders_data = [float(s[1]) for s in top_spenders]
    
    # Get category breakdown
    category_totals = defaultdict(float)
    for expense in Expense.query.filter(Expense.paid_by_id == current_user.id).all():
        category_totals[expense.category] += expense.amount
    
    category_labels = list(category_totals.keys())
    category_data = [float(category_totals[cat]) for cat in category_labels]
    
    # Calculate balances
    balances = []
    for friend in current_user.friends:
        you_owe = sum(share.amount for share in ExpenseShare.query.join(Expense)
                     .filter(ExpenseShare.user_id == current_user.id,
                            Expense.paid_by_id == friend.id))
        
        owes_you = sum(share.amount for share in ExpenseShare.query.join(Expense)
                      .filter(ExpenseShare.user_id == friend.id,
                             Expense.paid_by_id == current_user.id))
        
        net = owes_you - you_owe
        balances.append({
            'friend_name': friend.display_name or friend.username,
            'you_owe': you_owe,
            'owes_you': owes_you,
            'net': net
        })
    
    return render_template('analytics.html',
                         dates=dates,
                         spending_data=spending_data,
                         spenders_labels=spenders_labels,
                         spenders_data=spenders_data,
                         category_labels=category_labels,
                         category_data=category_data,
                         balances=balances)

@app.route('/api/analytics')
@login_required
def api_analytics():
    timeframe = request.args.get('timeframe', 'month')
    
    end_date = datetime.now()
    if timeframe == 'month':
        start_date = end_date - timedelta(days=30)
    elif timeframe == 'year':
        start_date = end_date - timedelta(days=365)
    else:  # all time
        start_date = datetime.min
    
    # Get spending data
    expenses = Expense.query.filter(
        and_(
            Expense.date >= start_date,
            Expense.date <= end_date,
            Expense.paid_by_id == current_user.id
        )
    ).order_by(Expense.date).all()
    
    dates = []
    spending_data = []
    daily_totals = defaultdict(float)
    
    for expense in expenses:
        date_str = expense.date.strftime('%Y-%m-%d')
        daily_totals[date_str] += expense.amount
    
    for date in (start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)):
        date_str = date.strftime('%Y-%m-%d')
        dates.append(date_str)
        spending_data.append(daily_totals[date_str])
    
    # Get top spenders for the timeframe
    top_spenders = db.session.query(
        User,
        func.sum(Expense.amount).label('total_amount')
    ).join(Expense, User.id == Expense.paid_by_id)\
     .filter(Expense.date >= start_date)\
     .group_by(User.id)\
     .order_by(func.sum(Expense.amount).desc())\
     .limit(5).all()
    
    spenders_labels = [s[0].display_name or s[0].username for s in top_spenders]
    spenders_data = [float(s[1]) for s in top_spenders]
    
    # Get category breakdown for the timeframe
    category_totals = defaultdict(float)
    for expense in Expense.query.filter(
        and_(
            Expense.date >= start_date,
            Expense.paid_by_id == current_user.id
        )
    ).all():
        category_totals[expense.category] += expense.amount
    
    category_labels = list(category_totals.keys())
    category_data = [float(category_totals[cat]) for cat in category_labels]
    
    return jsonify({
        'dates': dates,
        'spending_data': spending_data,
        'spenders_labels': spenders_labels,
        'spenders_data': spenders_data,
        'category_labels': category_labels,
        'category_data': category_data
    })

@app.route('/api/user/<username>')
@login_required
def get_user_id(username):
    user = User.query.filter_by(username=username).first()
    if user and user != current_user and user not in current_user.friends:
        return jsonify({'user_id': user.id})
    return jsonify({'user_id': None})

@app.route('/remove_friend/<int:friend_id>', methods=['POST'])
@login_required
def remove_friend(friend_id):
    friend = User.query.get_or_404(friend_id)
    if friend in current_user.friends:
        current_user.friends.remove(friend)
        friend.friends.remove(current_user)
        db.session.commit()
        flash(f'Removed {friend.display_name or friend.username} from your friends.', 'success')
    return redirect(url_for('friends'))

@app.cli.command("init-db")
def init_db():
    """Clear the existing data and create new tables."""
    db.drop_all()
    db.create_all()
    print('Initialized the database.')

if __name__ == '__main__':
    app.run(debug=True)
