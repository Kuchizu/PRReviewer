from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Table, Integer
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

team_members = Table(
    'team_members',
    Base.metadata,
    Column('team_id', String, ForeignKey('teams.id'), primary_key=True),
    Column('user_id', String, ForeignKey('users.id'), primary_key=True)
)

pr_reviewers = Table(
    'pr_reviewers',
    Base.metadata,
    Column('pr_id', String, ForeignKey('pull_requests.id'), primary_key=True),
    Column('user_id', String, ForeignKey('users.id'), primary_key=True)
)


class User(Base):
    __tablename__ = 'users'

    id = Column(String, primary_key=True)
    username = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    team_id = Column(String, ForeignKey('teams.id'))

    team = relationship('Team', back_populates='members')
    assigned_prs = relationship('PullRequest', secondary=pr_reviewers, back_populates='assigned_reviewers')


class Team(Base):
    __tablename__ = 'teams'

    id = Column(String, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    members = relationship('User', back_populates='team', cascade='all, delete-orphan')


class PullRequest(Base):
    __tablename__ = 'pull_requests'

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    author_id = Column(String, ForeignKey('users.id'), nullable=False)
    status = Column(String, default='OPEN')
    created_at = Column(DateTime, default=datetime.utcnow)
    merged_at = Column(DateTime, nullable=True)

    author = relationship('User')
    assigned_reviewers = relationship('User', secondary=pr_reviewers, back_populates='assigned_prs')
