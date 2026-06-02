from datetime import datetime, timezone
from app import db


class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default="user")
    create_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # relationships
    projects = db.relationship("Project", backref="owner", lazy="dynamic",
                               cascade="all, delete-orphan")
    api_cases = db.relationship("ApiCase", backref="creator", lazy="dynamic",
                                cascade="all, delete-orphan")
    ai_records = db.relationship("AiGenerateRecord", backref="creator", lazy="dynamic",
                                 cascade="all, delete-orphan")
    web_scripts = db.relationship("WebScript", backref="creator", lazy="dynamic",
                                 cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "create_time": self.create_time.isoformat() if self.create_time else None,
        }


class Project(db.Model):
    __tablename__ = "project"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    create_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # relationships
    environments = db.relationship("Environment", backref="project", lazy="dynamic",
                                   cascade="all, delete-orphan")
    api_cases = db.relationship("ApiCase", backref="project", lazy="dynamic",
                                cascade="all, delete-orphan")
    test_suites = db.relationship("TestSuite", backref="project", lazy="dynamic",
                                  cascade="all, delete-orphan")
    ai_records = db.relationship("AiGenerateRecord", backref="project", lazy="dynamic",
                                 cascade="all, delete-orphan")
    web_scripts = db.relationship("WebScript", backref="project", lazy="dynamic",
                                 cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "owner_id": self.owner_id,
            "create_time": self.create_time.isoformat() if self.create_time else None,
        }


class Environment(db.Model):
    __tablename__ = "environment"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    variables = db.Column(db.JSON, nullable=True)
    create_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "variables": self.variables,
            "create_time": self.create_time.isoformat() if self.create_time else None,
        }


class ApiCase(db.Model):
    __tablename__ = "api_case"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    method = db.Column(db.String(20), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    headers = db.Column(db.JSON, nullable=True)
    params = db.Column(db.JSON, nullable=True)
    body = db.Column(db.JSON, nullable=True)
    body_type = db.Column(db.String(50), nullable=True)
    assertions = db.Column(db.JSON, nullable=True)
    extract = db.Column(db.JSON, nullable=True)
    create_user = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    create_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "method": self.method,
            "url": self.url,
            "headers": self.headers,
            "params": self.params,
            "body": self.body,
            "body_type": self.body_type,
            "assertions": self.assertions,
            "extract": self.extract,
            "create_user": self.create_user,
            "create_time": self.create_time.isoformat() if self.create_time else None,
        }


class TestSuite(db.Model):
    __tablename__ = "test_suite"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(200), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    case_ids = db.Column(db.JSON, nullable=True)
    create_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # relationships
    tasks = db.relationship("TestTask", backref="suite", lazy="dynamic",
                            cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "project_id": self.project_id,
            "case_ids": self.case_ids,
            "create_time": self.create_time.isoformat() if self.create_time else None,
        }


class TestTask(db.Model):
    __tablename__ = "test_task"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    suite_id = db.Column(db.Integer, db.ForeignKey("test_suite.id"), nullable=False)
    status = db.Column(db.String(20), default="pending")  # pending / running / success / failed
    result = db.Column(db.JSON, nullable=True)
    log = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "suite_id": self.suite_id,
            "status": self.status,
            "result": self.result,
            "log": self.log,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


class WebScript(db.Model):
    __tablename__ = "web_script"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    url = db.Column(db.String(500), nullable=False)
    steps = db.Column(db.JSON, nullable=False)
    variables = db.Column(db.JSON, nullable=True)
    create_user = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    create_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    update_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))

    # relationships
    tasks = db.relationship("WebTestTask", backref="script", lazy="dynamic",
                            cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description or "",
            "url": self.url,
            "steps": self.steps or [],
            "variables": self.variables or {},
            "create_user": self.create_user,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time
            else (self.create_time.isoformat() if self.create_time else None),
        }


class WebTestTask(db.Model):
    __tablename__ = "web_test_task"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    script_id = db.Column(db.Integer, db.ForeignKey("web_script.id"), nullable=False)
    task_name = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(20), default="pending")  # pending / running / success / failed
    result = db.Column(db.JSON, nullable=True)
    log = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "script_id": self.script_id,
            "task_name": self.task_name,
            "status": self.status,
            "result": self.result,
            "log": self.log,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


class AiGenerateRecord(db.Model):
    __tablename__ = "ai_generate_record"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    create_user = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    prompt = db.Column(db.Text, nullable=True)
    api_info = db.Column(db.JSON, nullable=True)
    generate_type = db.Column(db.String(50), default="api_case")
    case_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="pending")  # pending / success / failed
    generated_cases = db.Column(db.JSON, nullable=True)
    create_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "create_user": self.create_user,
            "prompt": self.prompt,
            "api_info": self.api_info,
            "generate_type": self.generate_type,
            "case_count": self.case_count,
            "status": self.status,
            "generated_cases": self.generated_cases,
            "create_time": self.create_time.isoformat() if self.create_time else None,
        }
