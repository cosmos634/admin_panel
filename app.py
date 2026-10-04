from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import mimetypes
import os

from flask import Flask, flash, redirect, render_template, request, url_for
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from models import Account, Post, PostStatistics, db
from scheduler import start_scheduler


ALLOWED_MEDIA_EXTENSIONS = {"mp4", "webm", "mov", "m4v", "jpg", "jpeg", "png", "webp", "gif"}
ALLOWED_COVER_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_MEDIA_MIMETYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-m4v",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}
ALLOWED_COVER_MIMETYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_SIZE = 200 * 1024 * 1024
MAX_TITLE_LENGTH = 255


def utcnow():
    return datetime.now(timezone.utc)


def allowed_file(file_storage, allowed_extensions, allowed_mimetypes):
    if not file_storage or not file_storage.filename:
        return False

    filename = secure_filename(file_storage.filename)
    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    if extension not in allowed_extensions:
        return False

    content_type = (file_storage.mimetype or "").lower()
    return not content_type or content_type == "application/octet-stream" or content_type in allowed_mimetypes


def save_upload(file_storage, upload_dir):
    original_name = secure_filename(file_storage.filename or "")
    extension = original_name.rsplit(".", 1)[1].lower()
    filename = f"{uuid4().hex}.{extension}"
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / filename
    file_storage.save(destination)
    return destination, filename


def create_app(test_config=None):
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///admin_panel.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE
    app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    with app.app_context():
        db.create_all()

        # Phase 4 needs a local account to own newly created posts.
        # Create one default account only when the database has no accounts yet.
        if Account.query.count() == 0:
            db.session.add(
                Account(
                    username="cosm_0s",
                    display_name="CosmOS",
                    followers=0,
                    following=0,
                    posts_count=0,
                )
            )
            db.session.commit()

    @app.errorhandler(413)
    def request_entity_too_large(_error):
        flash("Uploaded file is too large. Maximum size is 200 MB.", "error")
        return redirect(url_for("add_post"))

    @app.template_filter("compact_number")
    def compact_number(value):
        if value is None:
            return "0"
        value = int(value)
        if value >= 1_000_000:
            number = value / 1_000_000
            return f"{number:.1f}".rstrip("0").rstrip(".") + "M"
        if value >= 1_000:
            number = value / 1_000
            return f"{number:.1f}".rstrip("0").rstrip(".") + "K"
        return f"{value:,}"

    @app.route("/")
    @app.route("/dashboard")
    def dashboard():
        account = Account.query.order_by(Account.id.asc()).first()

        posts = []
        total_views = total_likes = total_comments = total_shares = 0

        if account:
            posts = (
                Post.query.options(joinedload(Post.statistics))
                .filter_by(account_id=account.id)
                .order_by(Post.updated_at.desc(), Post.created_at.desc())
                .all()
            )

            totals = (
                db.session.query(
                    func.coalesce(func.sum(PostStatistics.views), 0),
                    func.coalesce(func.sum(PostStatistics.likes), 0),
                    func.coalesce(func.sum(PostStatistics.comments), 0),
                    func.coalesce(func.sum(PostStatistics.shares), 0),
                )
                .outerjoin(Post, PostStatistics.post_id == Post.id)
                .filter(Post.account_id == account.id)
                .one()
            )
            total_views, total_likes, total_comments, total_shares = totals

        return render_template(
            "dashboard.html",
            account=account,
            posts=posts,
            total_views=total_views,
            total_likes=total_likes,
            total_comments=total_comments,
            total_shares=total_shares,
        )

    @app.route("/posts/add", methods=["GET", "POST"])
    def add_post():
        if request.method == "GET":
            return render_template("add_post.html", form_data={}, selected_status="draft")

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        status = request.form.get("status", "draft").strip().lower()
        scheduled_at_raw = request.form.get("scheduled_at", "").strip()
        media = request.files.get("media")
        cover = request.files.get("cover")

        form_data = {
            "title": title,
            "description": description,
            "scheduled_at": scheduled_at_raw,
        }

        errors = []

        if not title:
            errors.append("Title is required.")
        elif len(title) > MAX_TITLE_LENGTH:
            errors.append(f"Title must be {MAX_TITLE_LENGTH} characters or fewer.")

        if status not in {"draft", "published", "scheduled"}:
            errors.append("Invalid post action.")

        publishable = status in {"published", "scheduled"}
        if publishable and (not media or not media.filename):
            errors.append("Media is required when publishing or scheduling a post.")

        if media and media.filename:
            if not allowed_file(media, ALLOWED_MEDIA_EXTENSIONS, ALLOWED_MEDIA_MIMETYPES):
                errors.append("Unsupported media file type.")

        if cover and cover.filename:
            if not allowed_file(cover, ALLOWED_COVER_EXTENSIONS, ALLOWED_COVER_MIMETYPES):
                errors.append("Unsupported cover image type.")

        scheduled_at = None
        if status == "scheduled":
            if not scheduled_at_raw:
                errors.append("Scheduled date and time are required.")
            else:
                try:
                    scheduled_at = datetime.fromisoformat(scheduled_at_raw)
                except ValueError:
                    errors.append("Scheduled date and time are invalid.")

        account = Account.query.order_by(Account.id.asc()).first()
        if not account:
            errors.append("No account is configured. Create an account before adding posts.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template(
                "add_post.html",
                form_data=form_data,
                selected_status=status,
            ), 400

        upload_root = Path(app.static_folder) / "uploads"
        media_dir = upload_root / "media"
        cover_dir = upload_root / "covers"
        saved_paths = []

        try:
            media_path = None
            cover_path = None

            if media and media.filename:
                saved_media, media_filename = save_upload(media, media_dir)
                saved_paths.append(saved_media)
                media_path = f"uploads/media/{media_filename}"

            if cover and cover.filename:
                saved_cover, cover_filename = save_upload(cover, cover_dir)
                saved_paths.append(saved_cover)
                cover_path = f"uploads/covers/{cover_filename}"

            now = utcnow()

            if status == "draft":
                post_status = "draft"
                published_at = None
                scheduled_at = None
            elif status == "published":
                post_status = "published"
                published_at = now
                scheduled_at = None
            else:
                post_status = "scheduled"
                published_at = None

            post = Post(
                account_id=account.id,
                title=title,
                description=description or None,
                media_path=media_path,
                cover_path=cover_path,
                status=post_status,
                published_at=published_at,
                scheduled_at=scheduled_at,
            )
            db.session.add(post)
            db.session.flush()

            db.session.add(
                PostStatistics(
                    post_id=post.id,
                    views=0,
                    likes=0,
                    comments=0,
                    shares=0,
                )
            )

            account.posts_count = (account.posts_count or 0) + 1
            db.session.commit()

        except Exception:
            db.session.rollback()
            for path in saved_paths:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            app.logger.exception("Failed to create post")
            flash("The post could not be created. Please try again.", "error")
            return render_template(
                "add_post.html",
                form_data=form_data,
                selected_status=status,
            ), 500

        flash("Post created successfully.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/automation")
    def automation():
        return render_template("automation.html")

    @app.route("/settings")
    def settings():
        return render_template("settings.html")

    @app.route("/view-post")
    @app.route("/view-post/<int:post_id>")
    def view_post(post_id=None):
        return render_template("view_post.html")

    # The scheduler is skipped for tests. In debug mode, Flask's reloader starts
    # the worker only in the reloader child process.
    if not app.testing and os.getenv("DISABLE_POST_SCHEDULER") != "1":
        debug_enabled = os.getenv("FLASK_DEBUG", "1") == "1"
        reloader_process = os.getenv("WERKZEUG_RUN_MAIN") == "true"
        if not debug_enabled or reloader_process:
            start_scheduler(app)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "1") == "1")
