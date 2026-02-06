from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models.auto_approve_rule import AutoApproveRule
from app.config.settings import get_settings
from app.db.repositories.settings_repo import SettingsRepository
from app.schemas.settings import (
    AutoApproveRuleIn,
    AutoApproveRuleOut,
    GetAutoApproveResponse,
    GetSettingsResponse,
    SetModelResponse,
    SetAutoApproveResponse,
)


class SettingsService:
    def __init__(self, db: Session):
        self.repo = SettingsRepository(db)
        self.app_settings = get_settings()

    def get_settings(self) -> GetSettingsResponse:
        settings_row = self.repo.get_settings()
        if settings_row is None:
            raise ValueError("Settings record missing")

        available_models = self._available_models()
        if settings_row.active_model not in set(available_models):
            self.ensure_active_model_valid()
            settings_row = self.repo.get_settings()
            if settings_row is None:
                raise ValueError("Settings record missing")

        rules = self.repo.list_auto_approve_rules()

        return GetSettingsResponse(
            model=settings_row.active_model,
            availableModels=available_models,
            contextLimit=settings_row.context_limit,
            autoApproveRules=[
                AutoApproveRuleOut(
                    id=r.id,
                    field=r.field,
                    value=r.value,
                    enabled=bool(r.enabled),
                    createdAt=r.created_at,
                )
                for r in rules
            ],
        )

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _available_models(self) -> list[str]:
        models = self.repo.list_models()
        labels = [m.label for m in models if m.provider == "openrouter"]
        return labels or list(self.app_settings.fallback_models)

    def ensure_active_model_valid(self) -> str:
        settings_row = self.repo.get_settings()
        if settings_row is None:
            raise ValueError("Settings record missing")

        available = self._available_models()
        available_set = set(available)
        target = settings_row.active_model
        if target not in available_set:
            if self.app_settings.default_active_model in available_set:
                target = self.app_settings.default_active_model
            elif available:
                target = available[0]
            else:
                target = self.app_settings.default_active_model

        if target != settings_row.active_model:
            self.repo.set_active_model(target, updated_at=self._now())
            self.repo.commit()
        return target

    def set_model(self, model: str) -> SetModelResponse:
        settings_row = self.repo.get_settings()
        if settings_row is None:
            raise ValueError("Settings record missing")

        available = self._available_models()
        if model not in set(available):
            raise ValueError(f"Model is not available: {model}")

        previous_model = settings_row.active_model
        context_limit = settings_row.context_limit
        self.repo.set_active_model(model, updated_at=self._now())
        self.repo.commit()
        return SetModelResponse(model=model, previousModel=previous_model, contextLimit=context_limit)

    def get_auto_approve_rules(self) -> GetAutoApproveResponse:
        rules = self.repo.list_auto_approve_rules()
        return GetAutoApproveResponse(
            rules=[
                AutoApproveRuleOut(
                    id=r.id,
                    field=r.field,
                    value=r.value,
                    enabled=bool(r.enabled),
                    createdAt=r.created_at,
                )
                for r in rules
            ]
        )

    def set_auto_approve_rules(self, rules: list[AutoApproveRuleIn]) -> SetAutoApproveResponse:
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            AutoApproveRule(
                id=f"aar-{uuid4().hex[:12]}",
                field=r.field,
                value=r.value,
                enabled=1 if r.enabled else 0,
                created_at=now,
            )
            for r in rules
        ]
        self.repo.replace_auto_approve_rules(rows)
        self.repo.commit()
        return SetAutoApproveResponse(
            rules=[
                AutoApproveRuleOut(
                    id=r.id,
                    field=r.field,
                    value=r.value,
                    enabled=bool(r.enabled),
                    createdAt=r.created_at,
                )
                for r in rows
            ]
        )
