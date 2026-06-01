# health/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import HealthRequest, HealthTimelineEvent


@receiver(post_save, sender=HealthRequest)
def log_status_change(sender, instance, created, **kwargs):
    """Log automatique des changements de statut"""
    if not created:
        try:
            old = HealthRequest.objects.get(id=instance.id)
            if old.status != instance.status:
                HealthTimelineEvent.objects.create(
                    health_request=instance,
                    event_type='assigned' if instance.status == 'in_progress' else 'closed',
                    actor='Système',
                    action=f"Statut changé: {old.get_status_display()} → {instance.get_status_display()}"
                )
        except HealthRequest.DoesNotExist:
            pass