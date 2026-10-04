from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc)


class Account(db.Model):
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    display_name = db.Column(db.String(150), nullable=False)
    avatar = db.Column(db.String(255))
    bio = db.Column(db.Text)
    followers = db.Column(db.Integer, nullable=False, default=0)
    following = db.Column(db.Integer, nullable=False, default=0)
    posts_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    posts = db.relationship(
        "Post", back_populates="account", cascade="all, delete-orphan"
    )


class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(
        db.Integer, db.ForeignKey("accounts.id"), nullable=False, index=True
    )
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    media_path = db.Column(db.String(500))
    cover_path = db.Column(db.String(500))
    status = db.Column(db.String(20), nullable=False, default="draft")
    published_at = db.Column(db.DateTime(timezone=True))
    scheduled_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    account = db.relationship("Account", back_populates="posts")
    statistics = db.relationship(
        "PostStatistics",
        back_populates="post",
        uselist=False,
        cascade="all, delete-orphan",
    )


class PostStatistics(db.Model):
    __tablename__ = "post_statistics"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(
        db.Integer,
        db.ForeignKey("posts.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    views = db.Column(db.Integer, nullable=False, default=0)
    likes = db.Column(db.Integer, nullable=False, default=0)
    comments = db.Column(db.Integer, nullable=False, default=0)
    shares = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    post = db.relationship("Post", back_populates="statistics")


class Automation(db.Model):
    __tablename__ = "automations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="inactive")
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    logs = db.relationship(
        "AutomationLog",
        back_populates="automation",
        cascade="all, delete-orphan",
    )


class AutomationLog(db.Model):
    __tablename__ = "automation_logs"

    id = db.Column(db.Integer, primary_key=True)
    automation_id = db.Column(
        db.Integer, db.ForeignKey("automations.id"), nullable=False, index=True
    )
    action = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    automation = db.relationship("Automation", back_populates="logs")


class Settings(db.Model):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), nullable=False, unique=True)
    value = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
