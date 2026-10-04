import os
import threading
from datetime import datetime, timezone

from sqlalchemy import select

from models import Post, db


DEFAULT_INTERVAL = 30


def utcnow():
    return datetime.now(timezone.utc)


def _as_utc_naive(value):
    """Normalize SQLite/SQLAlchemy datetime values to naive UTC for comparison."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def process_scheduled_posts(app):
    """Publish all scheduled posts whose UTC schedule time has passed."""
    now = utcnow()
    now_naive = now.replace(tzinfo=None)

    with app.app_context():
        due_posts = db.session.scalars(
            select(Post)
            .where(
                Post.status == "scheduled",
                Post.scheduled_at.is_not(None),
                Post.scheduled_at <= now_naive,
            )
            .order_by(Post.scheduled_at.asc(), Post.id.asc())
        ).all()

        for post in due_posts:
            try:
                # SQLite may return naive datetimes even when timezone=True was used.
                # Normalize before the due check so the comparison stays UTC-based.
                scheduled_at = _as_utc_naive(post.scheduled_at)
                if scheduled_at is None or scheduled_at > now_naive:
                    continue

                # Keep the state check immediately before mutation so repeated
                # scheduler ticks cannot republish an already published post.
                if post.status != "scheduled":
                    continue

                post.status = "published"
                post.published_at = now
                db.session.commit()
                app.logger.info(
                    "Scheduled post %s successfully published.", post.id
                )
            except Exception:
                db.session.rollback()
                app.logger.exception(
                    "Failed to process scheduled post %s.", post.id
                )

        return len(due_posts)


def _scheduler_loop(app, stop_event, interval):
    app.logger.info("Post scheduler started (interval=%ss).", interval)
    try:
        process_scheduled_posts(app)
    except Exception:
        app.logger.exception("Initial scheduler run failed; worker remains active.")

    while not stop_event.wait(interval):
        try:
            process_scheduled_posts(app)
        except Exception:
            app.logger.exception("Post scheduler error; worker remains active.")


def start_scheduler(app):
    """Start one lightweight scheduler thread for this Flask app."""
    if app.extensions.get("post_scheduler_thread") is not None:
        return app.extensions["post_scheduler_thread"]

    interval = int(os.getenv("SCHEDULER_INTERVAL", str(DEFAULT_INTERVAL)))
    if interval < 5:
        interval = 5

    stop_event = threading.Event()
    thread = threading.Thread(
        target=_scheduler_loop,
        args=(app, stop_event, interval),
        name="post-scheduler",
        daemon=True,
    )

    app.extensions["post_scheduler_stop_event"] = stop_event
    app.extensions["post_scheduler_thread"] = thread
    thread.start()
    return thread
