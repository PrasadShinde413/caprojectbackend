from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Work, Assignment
from .whatsapp_utils import send_work_whatsapp_notification
import logging
import threading

logger = logging.getLogger(__name__)

# 🔒 Thread-local storage for signal suppression
_thread_locals = threading.local()

def suppress_whatsapp_signals():
    """Context manager/decorator to suppress WhatsApp signals"""
    class Suppressor:
        def __enter__(self):
            _thread_locals.suppress_whatsapp = True
        def __exit__(self, exc_type, exc_val, exc_tb):
            _thread_locals.suppress_whatsapp = False
    return Suppressor()

def is_whatsapp_suppressed():
    return getattr(_thread_locals, 'suppress_whatsapp', False)

@receiver(pre_save, sender=Work)
def track_work_status_change(sender, instance, **kwargs):
    """
    Store the old status to compare in post_save
    """
    if instance.id:
        try:
            old_instance = Work.objects.get(id=instance.id)
            instance._old_status = old_instance.status
        except Work.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None

@receiver(post_save, sender=Work)
def send_whatsapp_on_status_change(sender, instance, created, **kwargs):
    """
    Trigger WhatsApp messages when status changes
    """
    # Skip if specifically requested (e.g. for bulk updates)
    if getattr(instance, '_skip_whatsapp', False) or is_whatsapp_suppressed():
        return

    old_status = getattr(instance, '_old_status', None)
    new_status = instance.status

    # 1. Work Acceptance: Status changes from Pending to In Progress
    # DISABLED: Messages only sent from API endpoints
    # if old_status == 'Pending' and new_status == 'In Progress':
    #     logger.info(f"Work {instance.id} accepted. Sending WhatsApp.")
    #     send_work_whatsapp_notification(instance, 'acceptance')

    # 2. Work Pending: Status changes to Pending (either from other status or created as Pending)
    # DISABLED: Messages only sent from API endpoints
    # elif new_status == 'Pending' and (created or old_status != 'Pending'):
    #     logger.info(f"Work {instance.id} is Pending. Sending acceptance WhatsApp.")
    #     send_work_whatsapp_notification(instance, 'acceptance')

    # 3. Work Completed: Status changes to Completed
    if new_status == 'Completed' and old_status != 'Completed':
        logger.info(f"Work {instance.id} completed. Sending WhatsApp.")
        send_work_whatsapp_notification(instance, 'completed')

@receiver(pre_save, sender=Assignment)
def track_assignment_status_change(sender, instance, **kwargs):
    if instance.id:
        try:
            old_instance = Assignment.objects.get(id=instance.id)
            instance._old_status = old_instance.status
        except Assignment.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None

@receiver(post_save, sender=Assignment)
def send_assignment_whatsapp_notification(sender, instance, created, **kwargs):
    # Skip if specifically requested
    if getattr(instance, '_skip_whatsapp', False) or is_whatsapp_suppressed():
        return

    old_status = getattr(instance, '_old_status', None)
    new_status = instance.status

    if old_status != new_status or (created and new_status == 'Pending'):
        # For assignment level, we can send a summary
        # But for now let's reuse the logic if it makes sense
        # Or just send a simple assignment-level message
        client = instance.client
        from .sms.service import SMSService
        from django.conf import settings
        
        if not getattr(settings, 'SMS_ENABLED', False):
            return
            
        phone = client.mobile_number or client.phone
        if not phone:
            return

        service = SMSService()
        template_name = getattr(settings, 'BHASHSMS_DEFAULT_TEMPLATE', 'pdr_uti')
        
        msg = ""
        params = f"{client.client_name},"
        
        if new_status == 'In Progress' and old_status == 'Pending':
            msg = f"Hello {client.client_name}, your assignment '{instance.assignment_name}' has been accepted."
            params += f"{instance.assignment_name} Accepted"
        elif new_status == 'Completed' and old_status != 'Completed':
            msg = f"Hello {client.client_name}, your assignment '{instance.assignment_name}' is completed."
            params += f"{instance.assignment_name} Completed"
        elif new_status == 'Pending' and (created or old_status != 'Pending'):
            msg = f"Hello {client.client_name}, your assignment '{instance.assignment_name}' is pending."
            params += f"{instance.assignment_name} Pending"

        if msg:
            service.send_bulk_message(
                recipients=[client],
                message=msg,
                message_type=f'assignment_{new_status.lower()}',
                template_name=template_name,
                template_params=params
            )
