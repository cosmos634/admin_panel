from flask import Flask, render_template
import os

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from models import Account, Post, PostStatistics, db


def create_app():
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///admin_panel.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

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

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "1") == "1")
