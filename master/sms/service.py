import logging
from django.conf import settings
from .providers.bhashsms import BhashSMSProvider
from master.models import SMSMessage, SMSLog, Client
from userauth.models import User

logger = logging.getLogger(__name__)

class SMSService:
    """Service to handle SMS/WhatsApp operations"""
    
    def __init__(self):
        self.provider = BhashSMSProvider()

    def send_bulk_message(self, recipients, message, message_type='bulk', created_by=None, template_name=None, template_params=None):
        """
        Send personalized WhatsApp messages to a list of recipients.
        """
        sms_msg = SMSMessage.objects.create(
            message_type=message_type,
            message_content=message or template_name or "WhatsApp Message",
            created_by=created_by if isinstance(created_by, User) else None
        )
        
        user_recipients = [r for r in recipients if isinstance(r, User)]
        if user_recipients:
            sms_msg.recipients.set(user_recipients)
        
        sent = 0
        failed = 0
        
        for recipient in recipients:
            # 1. Get Phone Number
            phone = None
            name = "Client"
            if hasattr(recipient, 'phone_no') and recipient.phone_no: # User model
                phone = recipient.phone_no
                name = getattr(recipient, 'full_name', 'User')
            elif hasattr(recipient, 'mobile_number') and recipient.mobile_number: # Client model priority
                phone = recipient.mobile_number
                name = getattr(recipient, 'client_name', 'Client')
            elif hasattr(recipient, 'phone') and recipient.phone: # Client model fallback
                phone = recipient.phone
                name = getattr(recipient, 'client_name', 'Client')
            
            if not phone:
                continue

            # 2. Personalize Template Parameters
            # Default to specific templates based on type
            t_name = template_name
            if not t_name:
                if message_type == 'bulk':
                    t_name = getattr(settings, 'BHASHSMS_BULK_TEMPLATE', 'wa_bulk')
                elif message_type == 'birthday':
                    t_name = getattr(settings, 'BHASHSMS_BIRTHDAY_TEMPLATE', 'wa_brt')
            
            # Default params mapping: {{name}},{{message}}
            current_params = template_params
            if not current_params:
                current_params = "{{name}},{{message}}"
            
            # Replace placeholders
            safe_name = name.replace(',', '')
            safe_message = (message or "").replace(',', ' ')
            
            final_params = current_params.replace("{{name}}", safe_name).replace("{{message}}", safe_message)

            # 3. Send Individual Message for personalization
            result = self.provider.send_sms(
                phone_number=phone,
                message=message,
                template_name=t_name,
                params=final_params
            )
            
            # 4. Create Log
            SMSLog.objects.create(
                sms_message=sms_msg,
                recipient=recipient if isinstance(recipient, User) else None,
                recipient_phone=phone,
                status='sent' if result['success'] else 'failed',
                external_id=result.get('message_id'),
                error_message=result.get('error')
            )
            
            if result['success']:
                sent += 1
            else:
                failed += 1
        
        # Update main message status
        sms_msg.status = 'sent' if sent > 0 else 'failed'
        sms_msg.sent_count = sent
        sms_msg.failed_count = failed
        sms_msg.save()
        
        return sms_msg

    def send_birthday_wish(self, recipient):
        """Send personalized birthday wish to User or Client"""
        name = "Valued Client"
        if hasattr(recipient, 'full_name'): # User
            name = recipient.full_name
        elif hasattr(recipient, 'client_name'): # Client
            name = recipient.client_name
            
        # Use custom birthday template
        template_name = 'wish_bdy'
        
        message = (
            f"Dear {name}\n"
            f"Wishing you a very Happy Birthday! May this year bring you continued success, "
            f"good health, and prosperity. It is always a pleasure working with you, and we truly "
            f"value your trust. Have a wonderful year ahead!\n\n"
            f"Regards,\nIbrahim Shaikh & Co"
        )
        
        # Template params - ensure no commas
        safe_name = name.replace(',', '')
        template_params = safe_name
        
        sms_msg = self.send_bulk_message(
            recipients=[recipient],
            message=message,
            message_type='birthday',
            template_name=template_name,
            template_params=template_params
        )
        
        return sms_msg.status == 'sent'
