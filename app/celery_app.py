from celery import Celery
from config import Config


def make_celery(app=None):
    celery = Celery(
        "netcatch",
        broker=Config.CELERY_BROKER_URL,
        backend=Config.CELERY_RESULT_BACKEND,
        include=["app.tasks.test_runner"],
    )
    celery.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Shanghai",
        enable_utc=True,
    )

    if app:

        class FlaskTask(celery.Task):
            abstract = True

            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        celery.Task = FlaskTask

    return celery


# Create global celery instance (configured later in create_app)
celery = make_celery()
