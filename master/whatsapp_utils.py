import logging
import threading
import time
from django.conf import settings
from .sms.service import SMSService
from .models import AssignmentDocumentSubmission, Work

logger = logging.getLogger(__name__)

# 🔒 Thread-local storage for deduplication
_sent_cache = threading.local()

def send_work_whatsapp_notification(work, notification_type):
    """
    Send WhatsApp notification to client based on work status change.
    Types: 'acceptance', 'pending', 'completed'
    """
    # 🛡️ Deduplication: Prevent sending the same notification type for the same work twice in one thread
    if not hasattr(_sent_cache, 'sent_items'):
        _sent_cache.sent_items = {}
    
    cache_key = f"{work.id}_{notification_type}"
    current_time = time.time()
    
    # If sent in last 2 seconds, skip
    if cache_key in _sent_cache.sent_items:
        last_sent = _sent_cache.sent_items[cache_key]
        if current_time - last_sent < 2:
            logger.info(f"Skipping duplicate WhatsApp for {cache_key}")
            return
            
    _sent_cache.sent_items[cache_key] = current_time

    if not getattr(settings, 'SMS_ENABLED', False):
        logger.info("SMS is disabled in settings.")
        return

    client = work.assignment.client
    phone = client.mobile_number or client.phone
    if not phone:
        logger.warning(f"No phone number found for client {client.client_name}")
        return

    service = SMSService()
    
    template_name = getattr(settings, 'BHASHSMS_DEFAULT_TEMPLATE', 'pdr_uti')
    
    # Common variables
    client_name = client.client_name
    safe_client_name = client_name.replace(',', '')
    work_name = work.work_service.service_name
    assignment_name = work.assignment.assignment_name

    message = ""
    params = ""

    if notification_type == 'acceptance':
        # 🔔 Use specific template for acceptance
        template_name = getattr(settings, 'BHASHSMS_ACCEPTANCE_TEMPLATE', 'wa_uti')

        message = (
            f"Dear {client_name}\n"
            f"We have received your work related to {work_name}. In case anything required our team will connect you.\n\n"
            "Regards,\nIbrahim Shaikh & Co"
        )
        
        # Parameter 1: Name, Parameter 2: Work Name
        safe_work = work_name.replace(',', ' ')
        params = f"{safe_client_name},{safe_work}"
        
    elif notification_type == 'pending':
        # Get pending documents
        all_docs = work.work_service.documents.all()
        submitted_doc_ids = AssignmentDocumentSubmission.objects.filter(
            assignment=work.assignment,
            work_service=work.work_service,
            status='Submitted'
        ).values_list('document_id', flat=True)
        
        pending_docs = all_docs.exclude(id__in=submitted_doc_ids)
        doc_list = ", ".join([doc.document_name for doc in pending_docs])
        
        message = (
            "Pending Doc reminder\n"
            f"Dear {client_name}\n"
            "You work is on hold due to following documents requirement - \n"
            f"{doc_list}\n\n"
            "Regards,\nIbrahim Shaikh & Co"
        )
        # Ensure no commas in parameters to prevent gateway errors
        safe_docs = doc_list.replace(',', ' ')
        params = f"{safe_client_name},{safe_docs[:50]}"

    elif notification_type == 'completed':
        # 🔔 Use specific template for completed
        template_name = getattr(settings, 'BHASHSMS_COMPLETED_TEMPLATE', 'wcm_ibsc')

        message = (
            f"Dear {client_name}\n"
            f"We are happy to inform you that your work related to {work_name} is completed.\n"
            "Happy to serve you.\n\n"
            "Regards,\nIbrahim Shaikh & Co"
        )
        safe_work = work_name.replace(',', ' ')
        params = f"{safe_client_name},{safe_work}"

    if message:
        try:
            # We use send_bulk_message with a single recipient list
            service.send_bulk_message(
                recipients=[client],
                message=message,
                message_type=f'work_{notification_type}',
                template_name=template_name,
                template_params=params
            )
            logger.info(f"WhatsApp {notification_type} notification sent to {client_name}")
        except Exception as e:
            logger.error(f"Error sending WhatsApp notification: {str(e)}")

def send_bulk_work_whatsapp_notification(client, works, notification_type):
    """
    Send a single WhatsApp notification for multiple works of the same client.
    """
    if not getattr(settings, 'SMS_ENABLED', False):
        return

    phone = client.mobile_number or client.phone
    if not phone:
        return

    service = SMSService()
    template_name = getattr(settings, 'BHASHSMS_DEFAULT_TEMPLATE', 'pdr_uti')
    
    client_name = client.client_name
    safe_client_name = client_name.replace(',', '')
    work_names = ", ".join([w.work_service.service_name for w in works])
    
    message = ""
    params = ""

    if notification_type == 'acceptance':
        # 🔔 Use specific template for acceptance
        template_name = getattr(settings, 'BHASHSMS_ACCEPTANCE_TEMPLATE', 'wa_uti')

        message = (
            f"Dear {client_name}\n"
            f"We have received your works related to {work_names}. In case anything required our team will connect you.\n\n"
            "Regards,\nIbrahim Shaikh & Co"
        )
        safe_works = work_names.replace(',', ' ')
        params = f"{safe_client_name},{safe_works}"
        
    elif notification_type == 'pending':
        # Collect all pending documents across these works
        all_pending_docs = []
        for work in works:
            all_docs = work.work_service.documents.all()
            submitted_doc_ids = AssignmentDocumentSubmission.objects.filter(
                assignment=work.assignment,
                work_service=work.work_service,
                status='Submitted'
            ).values_list('document_id', flat=True)
            pending_docs = all_docs.exclude(id__in=submitted_doc_ids)
            for d in pending_docs:
                all_pending_docs.append(f"{d.document_name} ({work.work_service.service_name})")
        
        doc_list = " ".join(all_pending_docs)
        
        message = (
            f"Dear {client_name}\n"
            f"We have received your works related to {work_names}. In case anything required our team will connect you.\n\n"
            
            "Regards,\nIbrahim Shaikh & Co"
        )
        # Ensure no commas in parameters
        safe_docs = doc_list.replace(',', ' ')
        params = f"{safe_client_name},{safe_docs[:50]}"

    elif notification_type == 'completed':
        message = (
            f"Dear {client_name}\n"
            f"We are happy to inform you that your works related to {work_names} are completed.\n"
            "Happy to serve you.\n\n"
            "Regards,\nIbrahim Shaikh & Co"
        )
        safe_works = work_names.replace(',', ' ')
        params = f"{safe_client_name},{safe_works}"

    if message:
        service.send_bulk_message(
            recipients=[client],
            message=message,
            message_type=f'work_{notification_type}_bulk',
            template_name=template_name,
            template_params=params
        )

def check_and_send_all_birthdays():
    """
    Check if any client or employee has birthday today and send WhatsApp wishes.
    """
    from datetime import datetime
    from userauth.models import User
    from .models import Client
    
    today = datetime.now().date()
    service = SMSService()
    
    # Custom birthday message
    birthday_message_template = (
        "Dear {name}\n"
        "Wishing you a very Happy Birthday! May this year bring you continued success, "
        "good health, and prosperity. It is always a pleasure working with you, and we truly "
        "value your trust. Have a wonderful year ahead!\n\n"
        "Regards,\nIbrahim Shaikh & Co"
    )
    
    # 1. Check Clients
    birthday_clients = Client.objects.filter(
        birthdate__month=today.month,
        birthdate__day=today.day,
        is_active=True
    )
    for client in birthday_clients:
        client_name = client.client_name
        safe_name = client_name.replace(',', '')
        
        message = birthday_message_template.replace('{name}', client_name)
        
        service.send_bulk_message(
            recipients=[client],
            message=message,
            message_type='birthday_wish',
            template_name='wish_bdy',
            template_params=safe_name
        )
        logger.info(f"Birthday wish sent to client: {client_name}")
        
    # 2. Check Employees (Users)
    birthday_users = User.objects.filter(
        birthdate__month=today.month,
        birthdate__day=today.day,
        is_active=True
    )
    for user in birthday_users:
        user_name = user.full_name
        safe_name = user_name.replace(',', '')
        
        message = birthday_message_template.replace('{name}', user_name)
        
        service.send_bulk_message(
            recipients=[user],
            message=message,
            message_type='birthday_wish',
            template_name='wish_bdy',
            template_params=safe_name
        )
        logger.info(f"Birthday wish sent to employee: {user_name}")





