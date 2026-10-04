from flask import Flask, render_template
import os

from models import db


def create_app():
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///admin_panel.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.route("/")
    @app.route("/dashboard")
    def dashboard():
        account = {
            "username": "cosm_0s",
            "name": "CosmOS",
            "followers": 9000000,
            "following": 0,
            "posts_count": 48,
        }

        posts = [
            {"title": "Post #1", "views": "100000", "likes": "99977", "comments": "9276", "shares": "9275"},
            {"title": "Post #2", "views": "100000", "likes": "97007", "comments": "976", "shares": "975"},
        ]

        return render_template("dashboard.html", account=account, posts=posts)

    @app.route("/automation")
    def automation():
        return render_template("automation.html")

    @app.route("/settings")
    def settings():
        return render_template("settings.html")

    @app.route("/view-post")
    def view_post():
        return render_template("view_post.html")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "1") == "1")
