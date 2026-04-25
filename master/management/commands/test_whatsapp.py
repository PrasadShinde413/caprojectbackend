from django.core.management.base import BaseCommand
from master.sms.service import SMSService
from django.conf import settings

class Command(BaseCommand):
    help = 'Test BhashSMS WhatsApp integration'

    def add_arguments(self, parser):
        parser.add_argument('--phone', type=str, default='9172847206', help='Phone number with country code')
        parser.add_argument('--template', type=str, help='Template name')
        parser.add_argument('--params', type=str, help='Template parameters (comma separated)')

    def handle(self, *args, **options):
        phone = options['phone']
        template = options['template'] or getattr(settings, 'BHASHSMS_DEFAULT_TEMPLATE', 'pdr_uti')
        params = options['params'] or getattr(settings, 'BHASHSMS_DEFAULT_PARAMS', '1,2')

        self.stdout.write(self.style.SUCCESS(f"Testing WhatsApp integration for {phone}..."))
        self.stdout.write(f"Using template: {template}")
        self.stdout.write(f"Using params: {params}")

        service = SMSService()
        # Direct call to provider for testing
        result = service.provider.send_sms(
            phone_number=phone,
            message="Test Message", # This might not be used if template is active
            template_name=template,
            params=params
        )

        if result['success']:
            self.stdout.write(self.style.SUCCESS(f"Successfully sent! Message ID: {result['message_id']}"))
        else:
            self.stdout.write(self.style.ERROR(f"Failed to send: {result['error']}"))
