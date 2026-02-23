from __future__ import annotations

from dataclasses import dataclass

from app.db.repositories.chat_repo import ChatRepository
from app.schemas.chat import ProjectPlanOut
from app.services.event_bus import EventBus, get_event_bus
from app.services.plan_file_store import PlanFileStore
from app.utils.ids import generate_id
from app.utils.time import utc_now_iso


@dataclass
class PlanUpdateResult:
    plan: ProjectPlanOut
    conflict: bool = False


class PlanService:
    def __init__(
        self,
        db,
        *,
        event_bus: EventBus | None = None,
        file_store: PlanFileStore | None = None,
    ):
        self.repo = ChatRepository(db)
        self.event_bus = event_bus or get_event_bus()
        self.file_store = file_store or PlanFileStore()

    def _append_revision(
        self,
        row,
        *,
        content: str,
        created_at: str,
        checkpoint_id: str | None,
    ) -> None:
        self.repo.create_project_plan_revision(
            revision_id=generate_id("prv"),
            plan_id=row.id,
            chat_id=row.chat_id,
            project_id=row.project_id,
            checkpoint_id=checkpoint_id,
            revision=row.revision,
            title=row.title,
            status=row.status,
            file_path=row.file_path,
            content_markdown=content,
            content_sha256=row.content_sha256,
            last_editor=row.last_editor,
            approved_action=row.approved_action,
            implementation_chat_id=row.implementation_chat_id,
            created_at=created_at,
        )

    def _to_out(self, plan_row, *, include_content: bool = False) -> ProjectPlanOut:
        content: str | None = None
        if include_content:
            try:
                content, _ = self.file_store.read_plan(
                    project_id=plan_row.project_id, plan_id=plan_row.id
                )
            except ValueError:
                content = None
        return ProjectPlanOut(
            id=plan_row.id,
            chatId=plan_row.chat_id,
            projectId=plan_row.project_id,
            checkpointId=plan_row.checkpoint_id,
            title=plan_row.title,
            status=plan_row.status,
            filePath=plan_row.file_path,
            revision=plan_row.revision,
            contentSha256=plan_row.content_sha256,
            lastEditor=plan_row.last_editor,
            approvedAction=plan_row.approved_action,
            implementationChatId=plan_row.implementation_chat_id,
            createdAt=plan_row.created_at,
            updatedAt=plan_row.updated_at,
            content=content,
        )

    async def list_plans(self, chat_id: str, *, include_content: bool = False) -> list[ProjectPlanOut]:
        return [
            self._to_out(row, include_content=include_content)
            for row in self.repo.list_project_plans(chat_id)
        ]

    async def get_plan(self, chat_id: str, plan_id: str, *, include_content: bool = True) -> ProjectPlanOut:
        row = self.repo.get_project_plan(plan_id)
        if row is None or row.chat_id != chat_id:
            raise ValueError(f"Plan not found: {plan_id}")
        return self._to_out(row, include_content=include_content)

    async def sync_external_if_needed(self, chat_id: str, plan_id: str) -> ProjectPlanOut | None:
        row = self.repo.get_project_plan(plan_id)
        if row is None or row.chat_id != chat_id:
            return None
        try:
            content, _ = self.file_store.read_plan(
                project_id=row.project_id, plan_id=row.id
            )
        except ValueError:
            return None
        file_hash = self.file_store.sha256_text(content)
        if file_hash == row.content_sha256:
            return None
        now = utc_now_iso()
        self.repo.set_project_plan_content(
            row,
            content_sha256=file_hash,
            revision=row.revision + 1,
            last_editor="external",
            updated_at=now,
        )
        self._append_revision(
            row,
            content=content,
            created_at=now,
            checkpoint_id=None,
        )
        self.repo.commit()
        out = self._to_out(row, include_content=True)
        await self.event_bus.publish(
            chat_id,
            {
                "type": "plan_conflict",
                "payload": {"plan": out.model_dump(), "reason": "external_update"},
            },
        )
        return out

    async def create_plan(
        self,
        *,
        chat_id: str,
        checkpoint_id: str | None,
        content: str,
        title: str = "Implementation Plan",
        status: str = "ready",
        last_editor: str = "agent",
    ) -> ProjectPlanOut:
        chat = self.repo.get_chat(chat_id)
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")
        plan_id = generate_id("plan")
        now = utc_now_iso()
        path, content_hash = self.file_store.write_plan(
            project_id=chat.project_id,
            plan_id=plan_id,
            content=content,
        )
        row = self.repo.create_project_plan(
            plan_id=plan_id,
            chat_id=chat_id,
            project_id=chat.project_id,
            checkpoint_id=checkpoint_id,
            title=title,
            status=status,
            file_path=str(path),
            revision=1,
            content_sha256=content_hash,
            last_editor=last_editor,
            approved_action=None,
            implementation_chat_id=None,
            created_at=now,
            updated_at=now,
        )
        self._append_revision(
            row,
            content=content,
            created_at=now,
            checkpoint_id=checkpoint_id,
        )
        self.repo.commit()
        out = self._to_out(row, include_content=True)
        await self.event_bus.publish(
            chat_id,
            {"type": "plan_ready", "payload": {"plan": out.model_dump(), "content": content}},
        )
        return out

    async def update_plan(
        self,
        *,
        chat_id: str,
        plan_id: str,
        content: str,
        title: str | None = None,
        base_revision: int | None = None,
        last_editor: str = "user",
        checkpoint_id: str | None = None,
    ) -> PlanUpdateResult:
        row = self.repo.get_project_plan(plan_id)
        if row is None or row.chat_id != chat_id:
            raise ValueError(f"Plan not found: {plan_id}")
        if base_revision is not None and row.revision != base_revision:
            return PlanUpdateResult(
                plan=self._to_out(row, include_content=True),
                conflict=True,
            )
        _, content_hash = self.file_store.write_plan(
            project_id=row.project_id,
            plan_id=row.id,
            content=content,
        )
        now = utc_now_iso()
        self.repo.set_project_plan_content(
            row,
            title=title,
            checkpoint_id=checkpoint_id,
            status="ready",
            content_sha256=content_hash,
            revision=row.revision + 1,
            last_editor=last_editor,
            updated_at=now,
        )
        self._append_revision(
            row,
            content=content,
            created_at=now,
            checkpoint_id=checkpoint_id,
        )
        self.repo.commit()
        out = self._to_out(row, include_content=True)
        await self.event_bus.publish(
            chat_id,
            {"type": "plan_updated", "payload": {"plan": out.model_dump(), "content": content}},
        )
        return PlanUpdateResult(plan=out, conflict=False)

    async def mark_plan_status(
        self,
        *,
        chat_id: str,
        plan_id: str,
        status: str,
        approved_action: str | None = None,
        implementation_chat_id: str | None = None,
        checkpoint_id: str | None = None,
    ) -> ProjectPlanOut:
        row = self.repo.get_project_plan(plan_id)
        if row is None or row.chat_id != chat_id:
            raise ValueError(f"Plan not found: {plan_id}")
        now = utc_now_iso()
        content = ""
        try:
            content, _ = self.file_store.read_plan(
                project_id=row.project_id, plan_id=row.id
            )
        except ValueError:
            content = ""
        self.repo.set_project_plan_content(
            row,
            checkpoint_id=checkpoint_id,
            status=status,
            revision=row.revision + 1,
            approved_action=approved_action,
            implementation_chat_id=implementation_chat_id,
            updated_at=now,
        )
        self._append_revision(
            row,
            content=content,
            created_at=now,
            checkpoint_id=checkpoint_id,
        )
        self.repo.commit()
        out = self._to_out(row, include_content=True)
        await self.event_bus.publish(
            chat_id,
            {"type": "plan_approved", "payload": {"plan": out.model_dump()}},
        )
        return out
