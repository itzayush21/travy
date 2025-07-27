from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import Enum, DateTime, Date

db = SQLAlchemy()

# User table
class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True)  # UUID from Supabase
    email = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    profile = db.relationship('UserProfile', backref='user', uselist=False, cascade="all, delete-orphan")
    emergency_contacts = db.relationship('EmergencyContact', backref='user', cascade="all, delete-orphan")
    language_preference = db.relationship('LanguagePreference', backref='user', uselist=False, cascade="all, delete-orphan")


class UserProfile(db.Model):
    __tablename__ = 'user_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    blood_group = db.Column(db.String(5))
    health_conditions = db.Column(db.Text)
    allergies = db.Column(db.Text)
    food_preferences = db.Column(db.Text)
    travel_preferences = db.Column(db.Text)


class EmergencyContact(db.Model):
    __tablename__ = 'emergency_contacts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(100))
    relation = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))


class LanguagePreference(db.Model):
    __tablename__ = 'language_preferences'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    preferred_language = db.Column(db.String(30))


class Pod(db.Model):
    __tablename__ = 'pods'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    invite_code = db.Column(db.String(10), unique=True)  # Can be generated randomly
    created_by = db.Column(db.String(36), nullable=False)  # Supabase UUID
    created_at = db.Column(DateTime, default=datetime.utcnow)

    destination = db.Column(db.String(100))
    start_date = db.Column(Date)
    end_date = db.Column(Date)
    status = db.Column(Enum('planned', 'active', 'completed', name='pod_status'), default='planned')
    estimated_budget = db.Column(db.Integer)
    preferred_transport = db.Column(db.String(50))
    tags = db.Column(db.String(100))  # comma-separated

    members = db.relationship('PodMember', backref='pod', cascade="all, delete-orphan")


class PodMember(db.Model):
    __tablename__ = 'pod_members'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), nullable=False)  # Supabase UUID (not FK if user table is external)
    pod_id = db.Column(db.Integer, db.ForeignKey('pods.id', ondelete="CASCADE"), nullable=False)
    role = db.Column(Enum('admin', 'member', name='pod_roles'), default='member')
    joined_at = db.Column(DateTime, default=datetime.utcnow)

# models.py

class PodItinerary(db.Model):
    __tablename__ = 'itinerary_items'

    id = db.Column(db.Integer, primary_key=True)
    pod_id = db.Column(db.Integer, db.ForeignKey('pods.id', ondelete="CASCADE"))
    description = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.String(36))  # user_id who added it
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    pod = db.relationship("Pod", backref="itinerary_items")

class PodPacking(db.Model):
    __tablename__ = 'pod_packing'

    id = db.Column(db.Integer, primary_key=True)
    pod_id = db.Column(db.Integer, db.ForeignKey('pods.id', ondelete="CASCADE"))
    description = db.Column(db.Text)
    created_by = db.Column(db.String(36))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PodBudget(db.Model):
    __tablename__ = 'pod_budgets'

    id = db.Column(db.Integer, primary_key=True)
    pod_id = db.Column(db.Integer, db.ForeignKey('pods.id', ondelete='CASCADE'))
    description = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(36))  # UUID of user
    created_at = db.Column(db.DateTime, default=datetime.utcnow)



