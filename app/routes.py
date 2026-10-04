import os

from flask import Blueprint, abort, jsonify, request, send_from_directory
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import Task, TaskStatus, Team, TeamMember, User

bp = Blueprint("api", __name__)


def get_json():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, "Тело запроса должно быть JSON-объектом")
    return data


def require_str(data, field):
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        abort(400, f"Поле '{field}' обязательно и должно быть непустой строкой")
    return value.strip()


def require_int(data, field):
    value = data.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        abort(400, f"Поле '{field}' обязательно и должно быть целым числом")
    return value


def get_or_404(model, obj_id, name):
    obj = db.session.get(model, obj_id)
    if obj is None:
        abort(404, f"Не найдено: {name} с id {obj_id}")
    return obj


def check_assignee(team, assignee_id):
    get_or_404(User, assignee_id, "Пользователь")
    if not team.has_member(assignee_id):
        abort(400, "Исполнитель должен быть участником команды")


DOCS_DIR = os.path.join(os.path.dirname(__file__), "docs")


@bp.get("/openapi.yaml")
def openapi_spec():
    return send_from_directory(DOCS_DIR, "openapi.yaml", mimetype="application/yaml")


@bp.get("/docs")
def swagger_ui():
    return send_from_directory(DOCS_DIR, "swagger.html")


@bp.get("/health")
def health():
    db.session.execute(text("SELECT 1"))
    return jsonify(status="ok", db="ok")


@bp.post("/users")
def create_user():
    username = require_str(get_json(), "username")
    user = User(username=username)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(400, "Пользователь с таким именем уже существует")
    return jsonify(user.to_dict()), 201


@bp.get("/users")
def list_users():
    users = db.session.scalars(select(User).order_by(User.id)).all()
    return jsonify([u.to_dict() for u in users])


@bp.post("/teams")
def create_team():
    data = get_json()
    name = require_str(data, "name")
    admin_id = require_int(data, "admin_id")
    get_or_404(User, admin_id, "Пользователь")

    team = Team(name=name, admin_id=admin_id)
    team.members.append(TeamMember(user_id=admin_id))
    db.session.add(team)
    db.session.commit()
    return jsonify(team.to_dict()), 201


@bp.get("/teams/<int:team_id>")
def get_team(team_id):
    return jsonify(get_or_404(Team, team_id, "Команда").to_dict())


@bp.post("/teams/<int:team_id>/members")
def add_member(team_id):
    team = get_or_404(Team, team_id, "Команда")
    user_id = require_int(get_json(), "user_id")
    get_or_404(User, user_id, "Пользователь")
    if team.has_member(user_id):
        abort(400, "Пользователь уже состоит в команде")

    team.members.append(TeamMember(user_id=user_id))
    db.session.commit()
    return jsonify(team.to_dict()), 201


@bp.post("/teams/<int:team_id>/tasks")
def create_task(team_id):
    team = get_or_404(Team, team_id, "Команда")
    data = get_json()
    title = require_str(data, "title")
    author_id = require_int(data, "author_id")
    description = data.get("description", "")
    if not isinstance(description, str):
        abort(400, "Поле 'description' должно быть строкой")
    get_or_404(User, author_id, "Пользователь")

    assignee_id = data.get("assignee_id")
    if assignee_id is not None:
        assignee_id = require_int(data, "assignee_id")
        check_assignee(team, assignee_id)

    task = Task(
        team_id=team.id,
        author_id=author_id,
        assignee_id=assignee_id,
        title=title,
        description=description,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201


@bp.get("/teams/<int:team_id>/tasks")
def list_team_tasks(team_id):
    get_or_404(Team, team_id, "Команда")
    tasks = db.session.scalars(select(Task).where(Task.team_id == team_id).order_by(Task.id)).all()
    return jsonify([t.to_dict() for t in tasks])


@bp.get("/tasks/<int:task_id>")
def get_task(task_id):
    return jsonify(get_or_404(Task, task_id, "Задача").to_dict())


@bp.patch("/tasks/<int:task_id>/assignee")
def set_assignee(task_id):
    task = get_or_404(Task, task_id, "Задача")
    assignee_id = require_int(get_json(), "assignee_id")
    check_assignee(task.team, assignee_id)

    task.assignee_id = assignee_id
    db.session.commit()
    return jsonify(task.to_dict())


@bp.patch("/tasks/<int:task_id>/status")
def set_status(task_id):
    task = get_or_404(Task, task_id, "Задача")
    data = get_json()
    user_id = require_int(data, "user_id")
    status = require_str(data, "status")

    try:
        new_status = TaskStatus(status)
    except ValueError:
        allowed = ", ".join(s.value for s in TaskStatus)
        abort(400, f"Неизвестный статус. Допустимые: {allowed}")
    if task.assignee_id is None or task.assignee_id != user_id:
        abort(400, "Статус может менять только исполнитель задачи")

    task.status = new_status
    db.session.commit()
    return jsonify(task.to_dict())
