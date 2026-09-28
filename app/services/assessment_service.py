from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.models.assessment import Assessment, AssessmentPayment
from app.models.membership import Membership
from app.models.user import User
from app.utils.money import money_float


class AssessmentServiceError(ValueError):
    pass


class AssessmentService:
    def __init__(self, db: Session):
        self.db = db

    def create_assessment(
        self,
        admin: User,
        title: str,
        topic: str,
        description: str | None,
        cost: float,
        scope: str,
        group_id: int,
        student_membership_id: int | None,
        due_at: datetime | None,
    ) -> Assessment:
        title = title.strip()
        topic = topic.strip()
        description = description.strip() if description else None
        if not title:
            raise AssessmentServiceError("Укажите название зачета")
        if not topic:
            raise AssessmentServiceError("Укажите тему зачета")
        cost = money_float(cost)
        if cost <= 0:
            raise AssessmentServiceError("Стоимость должна быть больше нуля")
        if scope not in {"group", "student"}:
            raise AssessmentServiceError("Выберите назначение зачета")
        if scope == "student":
            if not student_membership_id:
                raise AssessmentServiceError("Выберите студента")
            membership = self.db.get(Membership, student_membership_id)
            if membership is None:
                raise AssessmentServiceError("Студент не найден")
            group_id = membership.group_id
        else:
            student_membership_id = None

        assessment = Assessment(
            title=title,
            topic=topic,
            description=description,
            cost=cost,
            scope=scope,
            group_id=group_id,
            student_membership_id=student_membership_id,
            due_at=due_at,
            status="active",
            created_by_user_id=admin.id,
        )
        self.db.add(assessment)
        self.db.commit()
        self.db.refresh(assessment)
        return assessment

    def list_assessments(self) -> list[Assessment]:
        return (
            self.db.query(Assessment)
            .options(
                selectinload(Assessment.group),
                selectinload(Assessment.student_membership).selectinload(Membership.user),
                selectinload(Assessment.payments),
            )
            .order_by(Assessment.status, Assessment.created_at.desc())
            .all()
        )

    def assigned_to(self, membership: Membership) -> list[Assessment]:
        return (
            self.db.query(Assessment)
            .options(selectinload(Assessment.payments), selectinload(Assessment.group))
            .filter(
                or_(
                    (Assessment.scope == "group") & (Assessment.group_id == membership.group_id),
                    (Assessment.scope == "student") & (Assessment.student_membership_id == membership.id),
                )
            )
            .order_by(Assessment.status, Assessment.due_at.is_(None), Assessment.due_at, Assessment.created_at.desc())
            .all()
        )

    def payment_map_for(self, membership: Membership) -> dict[int, AssessmentPayment]:
        payments = (
            self.db.query(AssessmentPayment)
            .filter_by(membership_id=membership.id, status="paid")
            .order_by(AssessmentPayment.created_at.desc())
            .all()
        )
        return {payment.assessment_id: payment for payment in payments}
