import requests
import logging
import urllib.parse
from django.conf import settings
from .base import SMSProvider

logger = logging.getLogger(__name__)

class BhashSMSProvider(SMSProvider):
    """BhashSMS Implementation for WhatsApp Integration"""
    
    BASE_URL = "https://bhashsms.com/api/sendmsgutil.php"
    
    def __init__(self):
        self.user = getattr(settings, 'BHASHSMS_USER', 'ISC_BWAI')
        self.password = getattr(settings, 'BHASHSMS_PASS', '123456')
        self.sender = getattr(settings, 'BHASHSMS_SENDER', 'BUZWAP')
        self.priority = getattr(settings, 'BHASHSMS_PRIORITY', 'wa')
        self.stype = getattr(settings, 'BHASHSMS_STYPE', 'normal')
        self.mock_mode = getattr(settings, 'SMS_MOCK_MODE', False)

    def _format_phone(self, phone_number):
        """Format to 12 digits (including 91) for India."""
        phone = str(phone_number).replace(' ', '').replace('-', '').replace('+', '')
        
        # If it's a 10-digit number, prepend 91
        if len(phone) == 10:
            phone = "91" + phone
        # If it's already 12 digits (like 91XXXXXXXXXX), keep it
        elif len(phone) > 12:
            phone = phone[-12:]
            
        return phone

    def send_sms(self, phone_number, message, template_name=None, params=None):
        """
        Send WhatsApp message via BhashSMS with URL Encoding.
        """
        try:
            phone = self._format_phone(phone_number)
            t_name = template_name or getattr(settings, 'BHASHSMS_DEFAULT_TEMPLATE', 'pdr_uti')
            t_params = params or getattr(settings, 'BHASHSMS_DEFAULT_PARAMS', '1,2')
            
            if self.mock_mode:
                return {'success': True, 'message_id': f'MOCK-WA-{phone}', 'error': None}

            # We must URL-encode the parameters (especially Params) because they contain spaces.
            # However, we keep the commas literal as BhashSMS requires them.
            encoded_params = urllib.parse.quote(t_params).replace('%2C', ',')
            
            # Construct the URL
            raw_url = (
                f"{self.BASE_URL}?"
                f"user={self.user}&"
                f"pass={self.password}&"
                f"sender={self.sender}&"
                f"phone={phone}&"
                f"text={t_name}&"
                f"priority={self.priority}&"
                f"stype={self.stype}&"
                f"Params={encoded_params}"
            )

            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            logger.info(f"[BHASHSMS] Sending WhatsApp to {phone} using template {t_name}")
            logger.info(f"[BHASHSMS] URL: {raw_url.replace(self.password, '******')}")
            
            response = requests.get(raw_url, timeout=15, verify=False)
            response_text = response.text
            
            if response.status_code == 200 and ("S." in response_text or "Sent" in response_text or "OK" in response_text.upper()):
                return {'success': True, 'message_id': response_text.strip(), 'error': None}
            else:
                return {'success': False, 'message_id': None, 'error': response_text}

        except Exception as e:
            logger.error(f"[BHASHSMS ERROR] {str(e)}")
            return {'success': False, 'message_id': None, 'error': str(e)}

    def send_bulk_sms(self, phone_numbers, message, template_name=None, params=None):
        """Send bulk WhatsApp messages"""
        details = []
        sent = 0
        failed = 0
        for phone in phone_numbers:
            result = self.send_sms(phone, message, template_name, params)
            details.append({'phone': phone, 'success': result['success'], 'error': result['error']})
            if result['success']: sent += 1
            else: failed += 1
        return {'sent': sent, 'failed': failed, 'details': details}
