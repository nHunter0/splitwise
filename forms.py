from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FloatField, SelectField, SelectMultipleField, BooleanField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError, Optional, Email, NumberRange
from models import User

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(), 
        Length(min=2, max=20)
    ])
    email = StringField('Email (Optional)', validators=[
        Optional(), 
        Email(message="Please enter a valid email address.")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6, message="Password must be at least 6 characters long.")
    ])
    password2 = PasswordField('Repeat Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match.')
    ])
    submit = SubmitField('Register')

    def validate_username(self, username):
        if len(username.data) < 2:
            raise ValidationError('Username must be at least 2 characters long.')
        if not username.data.isalnum():
            raise ValidationError('Username can only contain letters and numbers.')
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('This username is already taken.')

    def validate_email(self, email):
        if email.data:  # Only validate if email is provided
            user = User.query.filter_by(email=email.data).first()
            if user is not None:
                raise ValidationError('This email is already registered.')

class ProfileForm(FlaskForm):
    first_name = StringField('First Name', validators=[
        DataRequired(),
        Length(max=50)
    ])
    last_name = StringField('Last Name', validators=[
        DataRequired(),
        Length(max=50)
    ])
    display_name = StringField('What should we call you?', validators=[
        Optional(),
        Length(max=100)
    ])
    submit = SubmitField('Continue')

class GroupForm(FlaskForm):
    name = StringField('Group Name', validators=[DataRequired()])
    members = SelectMultipleField('Initial Members', coerce=int)
    submit = SubmitField('Create Group')

class ExpenseForm(FlaskForm):
    description = StringField('Description', validators=[DataRequired()])
    amount = FloatField('Amount', validators=[DataRequired(), NumberRange(min=0.01)])
    category = SelectField('Category', choices=[
        ('Food', 'Food & Dining'),
        ('Utilities', 'Utilities'),
        ('Rent', 'Rent'),
        ('Transportation', 'Transportation'),
        ('Entertainment', 'Entertainment'),
        ('Shopping', 'Shopping'),
        ('Travel', 'Travel'),
        ('Other', 'Other')
    ], validators=[DataRequired()])
    split_type = SelectField('Split Type', choices=[
        ('equal', 'Split Equally'),
        ('custom', 'Custom Split')
    ], validators=[DataRequired()])
    participants = SelectMultipleField('Participants', coerce=int)
    submit = SubmitField('Add Expense')

class AddFriendForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    submit = SubmitField('Add Friend')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is None:
            raise ValidationError('No user found with this username.')

class GroupInviteForm(FlaskForm):
    friend = SelectField('Friend', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Send Invite')
