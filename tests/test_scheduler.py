import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

from flask import Flask

from models import Account, Post, db
from scheduler import process_scheduled_posts


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        with self.app.app_context():
            db.create_all()
            self.account = Account(username="test", display_name="Test")
            db.session.add(self.account)
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def add_post(self, status, scheduled_at=None):
        with self.app.app_context():
            post = Post(
                account_id=self.account.id,
                title=f"{status} post",
                status=status,
                scheduled_at=scheduled_at,
            )
            db.session.add(post)
            db.session.commit()
            return post.id

    def get_post(self, post_id):
        with self.app.app_context():
            return db.session.get(Post, post_id)

    def test_future_scheduled_post_remains_scheduled(self):
        post_id = self.add_post(
            "scheduled",
            datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        process_scheduled_posts(self.app)
        self.assertEqual(self.get_post(post_id).status, "scheduled")

    def test_due_post_is_published_with_timestamp(self):
        post_id = self.add_post(
            "scheduled",
            datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        process_scheduled_posts(self.app)
        post = self.get_post(post_id)
        self.assertEqual(post.status, "published")
        self.assertIsNotNone(post.published_at)

    def test_draft_and_published_posts_are_ignored(self):
        draft_id = self.add_post("draft", datetime.now(timezone.utc) - timedelta(minutes=1))
        published_id = self.add_post(
            "published", datetime.now(timezone.utc) - timedelta(minutes=1)
        )
        process_scheduled_posts(self.app)
        self.assertEqual(self.get_post(draft_id).status, "draft")
        self.assertEqual(self.get_post(published_id).status, "published")

    def test_failed_post_does_not_stop_other_posts(self):
        ids = [
            self.add_post(
                "scheduled",
                datetime.now(timezone.utc) - timedelta(minutes=1),
            )
            for _ in range(2)
        ]

        real_commit = db.session.commit
        calls = 0

        def commit_with_one_failure():
            nonlocal calls
            calls += 1
            if calls == 1:
                db.session.rollback()
                raise RuntimeError("simulated database failure")
            real_commit()

        with patch.object(db.session, "commit", side_effect=commit_with_one_failure):
            process_scheduled_posts(self.app)

        statuses = [self.get_post(post_id).status for post_id in ids]
        self.assertEqual(statuses.count("published"), 1)
        self.assertEqual(statuses.count("scheduled"), 1)

    def test_multiple_due_posts_are_processed(self):
        ids = [
            self.add_post(
                "scheduled",
                datetime.now(timezone.utc) - timedelta(minutes=1),
            )
            for _ in range(3)
        ]
        process_scheduled_posts(self.app)
        self.assertTrue(all(self.get_post(post_id).status == "published" for post_id in ids))


if __name__ == "__main__":
    unittest.main()
