from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.audit import AppSetting
from app.models.user import User
from app.services.audit_service import AuditService
from app.utils.money import money, money_float


class SettingsServiceError(ValueError):
    pass


class SettingsService:
    FEE_KEY = "transfer_fee_percent"
    MAX_KEY = "transfer_max_percent"
    DEFAULTS = {
        FEE_KEY: "1.00",
        MAX_KEY: "70.00",
    }

    def __init__(self, db: Session):
        self.db = db

    def _setting(self, key: str) -> AppSetting:
        setting = self.db.query(AppSetting).filter_by(key=key).one_or_none()
        if setting is None:
            setting = AppSetting(key=key, value=self.DEFAULTS[key])
            self.db.add(setting)
            self.db.commit()
            self.db.refresh(setting)
        return setting

    def decimal_value(self, key: str) -> Decimal:
        return money(self._setting(key).value)

    def transfer_fee_percent(self) -> Decimal:
        return self.decimal_value(self.FEE_KEY)

    def transfer_max_percent(self) -> Decimal:
        return self.decimal_value(self.MAX_KEY)

    def transfer_policy(self) -> dict[str, float]:
        return {
            "fee_percent": money_float(self.transfer_fee_percent()),
            "max_percent": money_float(self.transfer_max_percent()),
        }

    def fee_for(self, amount: float | int | str | Decimal) -> float:
        amount_value = money(amount)
        fee_percent = self.transfer_fee_percent()
        if fee_percent <= 0:
            return 0.0
        fee = money(amount_value * fee_percent / Decimal("100"))
        if amount_value > 0 and fee == 0:
            fee = Decimal("0.01")
        return money_float(fee)

    def max_transfer_amount(self, balance: float | int | str | Decimal) -> float:
        balance_value = money(balance)
        max_debit = money(balance_value * self.transfer_max_percent() / Decimal("100"))
        if max_debit <= 0:
            return 0.0
        return money_float(max_debit)

    def update_transfer_policy(self, admin: User, fee_percent: float, max_percent: float) -> None:
        fee = money(fee_percent)
        maximum = money(max_percent)
        if fee < 0 or fee > 100:
            raise SettingsServiceError("Комиссия должна быть от 0 до 100%")
        if maximum <= 0 or maximum > 100:
            raise SettingsServiceError("Максимум перевода должен быть от 0.01 до 100%")
        for key, value in ((self.FEE_KEY, fee), (self.MAX_KEY, maximum)):
            setting = self._setting(key)
            setting.value = f"{value:.2f}"
        AuditService(self.db).log(
            admin,
            "settings.transfer_policy",
            "app_settings",
            None,
            {"fee_percent": f"{fee:.2f}", "max_percent": f"{maximum:.2f}"},
        )
        self.db.commit()

    def ensure_defaults(self) -> None:
        for key in self.DEFAULTS:
            self._setting(key)
