from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Regexp


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Stay signed in")


class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[
        DataRequired(), Length(3, 64),
        Regexp(r"^[A-Za-z0-9_.-]+$", message="Letters, numbers, . _ - only")])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    display_name = StringField("Display name", validators=[Length(max=120)])
    timezone = SelectField("Timezone", default="America/New_York", choices=[
        ("America/New_York", "Eastern"), ("America/Chicago", "Central"),
        ("America/Denver", "Mountain"), ("America/Los_Angeles", "Pacific"),
        ("UTC", "UTC")])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=10)])
    confirm = PasswordField("Confirm password", validators=[
        DataRequired(), EqualTo("password", message="Passwords must match")])