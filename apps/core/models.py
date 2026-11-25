from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    SALESMAN = 'SALESMAN', 'Salesman'
    FACTORY_ADMIN = 'FACTORY_ADMIN', 'Factory Admin'
    PRODUCTION_SUPERVISOR = 'PRODUCTION_SUPERVISOR', 'Production Supervisor'
    ACCOUNTANT_AUDITOR = 'ACCOUNTANT_AUDITOR', 'Accountant / Auditor'
    OWNER = 'OWNER', 'Owner / Management'


class User(AbstractUser):
    role = models.CharField(
        max_length=30,
        choices=UserRole.choices,
        default=UserRole.SALESMAN,
        help_text='Designated system role determining business access permissions.'
    )
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    @property
    def is_salesman(self):
        return self.role == UserRole.SALESMAN

    @property
    def is_admin(self):
        return self.role == UserRole.FACTORY_ADMIN or self.is_superuser

    @property
    def is_production_supervisor(self):
        return self.role == UserRole.PRODUCTION_SUPERVISOR

    @property
    def is_auditor(self):
        return self.role == UserRole.ACCOUNTANT_AUDITOR

    @property
    def is_owner(self):
        return self.role == UserRole.OWNER

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class AuditLog(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=60)
    entity = models.CharField(max_length=60)
    entity_id = models.CharField(max_length=60)
    previous_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    reason = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.user} {self.action} {self.entity}#{self.entity_id}"
