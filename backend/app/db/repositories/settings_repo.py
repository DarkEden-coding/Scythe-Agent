from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models.auto_approve_rule import AutoApproveRule
from app.db.models.provider_model_cache import ProviderModelCache
from app.db.models.settings import Settings


class SettingsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_settings(self) -> Settings | None:
        return self.db.get(Settings, 1)

    def list_models(self) -> list[ProviderModelCache]:
        return list(self.db.scalars(select(ProviderModelCache).order_by(ProviderModelCache.label.asc())).all())

    def replace_models(self, models: list[ProviderModelCache]) -> list[ProviderModelCache]:
        self.db.execute(delete(ProviderModelCache).where(ProviderModelCache.provider == "openrouter"))
        for model in models:
            self.db.add(model)
        return models

    def set_active_model(self, model: str, updated_at: str) -> Settings:
        settings = self.get_settings()
        if settings is None:
            raise ValueError("Settings record missing")
        settings.active_model = model
        settings.updated_at = updated_at
        return settings

    def list_auto_approve_rules(self) -> list[AutoApproveRule]:
        return list(self.db.scalars(select(AutoApproveRule).order_by(AutoApproveRule.created_at.asc())).all())

    def replace_auto_approve_rules(self, rules: list[AutoApproveRule]) -> list[AutoApproveRule]:
        for row in self.list_auto_approve_rules():
            self.db.delete(row)
        for rule in rules:
            self.db.add(rule)
        return rules

    def commit(self) -> None:
        self.db.commit()
