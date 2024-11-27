from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

# Association tables
friendships = db.Table('friendships',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('friend_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

group_members = db.Table('group_members',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('group.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    display_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password = db.Column(db.String(255), nullable=False)
    
    # Relationships
    expenses_paid = db.relationship('Expense', back_populates='paid_by')
    groups = db.relationship('Group', secondary=group_members, back_populates='members')
    friends = db.relationship('User', 
        secondary=friendships,
        primaryjoin='User.id==friendships.c.user_id',
        secondaryjoin='User.id==friendships.c.friend_id',
        lazy='dynamic'
    )
    # Friend requests
    friend_requests_sent = db.relationship('FriendRequest',
        foreign_keys='FriendRequest.sender_id',
        backref=db.backref('sender', lazy=True),
        lazy='dynamic'
    )
    friend_requests_received = db.relationship('FriendRequest',
        foreign_keys='FriendRequest.receiver_id',
        backref=db.backref('receiver', lazy=True),
        lazy='dynamic'
    )
    # Group invites
    group_invites_received = db.relationship('GroupInvite', 
        foreign_keys='GroupInvite.invitee_id',
        back_populates='invitee'
    )
    group_invites_sent = db.relationship('GroupInvite',
        foreign_keys='GroupInvite.inviter_id',
        back_populates='inviter'
    )
    
    def add_friend(self, friend):
        if friend not in self.friends:
            self.friends.append(friend)
            friend.friends.append(self)

    def remove_friend(self, friend):
        if friend in self.friends:
            self.friends.remove(friend)
            friend.friends.remove(self)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    members = db.relationship('User', secondary=group_members, back_populates='groups')
    expenses = db.relationship('Expense', back_populates='group')
    invites = db.relationship('GroupInvite', back_populates='group')
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    
    def __repr__(self):
        return f'<Group {self.name}>'

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)  # Keep both for backward compatibility
    category = db.Column(db.String(50), nullable=False, default='Other')
    paid_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)

    # Relationships
    paid_by = db.relationship('User', back_populates='expenses_paid')
    group = db.relationship('Group', back_populates='expenses')
    shares = db.relationship('ExpenseShare', back_populates='expense', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Expense {self.description}>'

class ExpenseShare(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    paid = db.Column(db.Boolean, default=False)
    
    # Foreign Keys
    expense_id = db.Column(db.Integer, db.ForeignKey('expense.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    expense = db.relationship('Expense', back_populates='shares')
    user = db.relationship('User')
    
    def __repr__(self):
        return f'<ExpenseShare {self.amount}>'

class GroupInvite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'accepted', 'rejected'
    
    # Foreign Keys
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    inviter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    invitee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    group = db.relationship('Group', back_populates='invites')
    inviter = db.relationship('User', foreign_keys=[inviter_id], back_populates='group_invites_sent')
    invitee = db.relationship('User', foreign_keys=[invitee_id], back_populates='group_invites_received')
    
    def __repr__(self):
        return f'<GroupInvite {self.group.name}>'

class FriendRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<FriendRequest {self.sender_id} -> {self.receiver_id}>'
