from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .sms_serializers import (
    SendBulkSMSSerializer, 
    SMSMessageListSerializer, 
    SMSMessageDetailSerializer
)
from .sms.service import SMSService
from userauth.models import User
from .models import Client, SMSMessage, SMSLog
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

class SendBulkSMSAPIView(APIView):
    """Send bulk SMS/WhatsApp to employees/clients"""
    
    def post(self, request):
        serializer = SendBulkSMSSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        message = serializer.validated_data.get('message', '')
        recipient_type = serializer.validated_data['recipient_type']
        recipients_ids = serializer.validated_data.get('recipients', [])
        template_name = serializer.validated_data.get('template_name')
        template_params = serializer.validated_data.get('template_params')
        
        recipients = []
        
        # 1. Handle Specific IDs if provided
        if recipients_ids:
            if recipient_type == 'employees':
                recipients = list(User.objects.filter(id__in=recipients_ids, is_active=True))
            elif recipient_type == 'clients':
                recipients = list(Client.objects.filter(id__in=recipients_ids, is_active=True))
            else: # 'all'
                recipients = list(User.objects.filter(id__in=recipients_ids, is_active=True))
                recipients += list(Client.objects.filter(id__in=recipients_ids, is_active=True))
        
        # 2. Handle Bulk selection if no specific IDs provided
        else:
            if recipient_type == 'employees':
                recipients = list(User.objects.filter(is_active=True))
            elif recipient_type == 'clients':
                recipients = list(Client.objects.filter(is_active=True))
            else: # 'all'
                recipients = list(User.objects.filter(is_active=True))
                recipients += list(Client.objects.filter(is_active=True))
        
        if not recipients:
            return Response(
                {'error': 'No recipients found matching criteria'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            sms_service = SMSService()
            sms_msg = sms_service.send_bulk_message(
                recipients=recipients,
                message=message,
                created_by=request.user,
                template_name=template_name,
                template_params=template_params
            )
            
            return Response({
                'message': 'WhatsApp message sent successfully' if sms_msg.status == 'sent' else 'Failed to send WhatsApp message',
                'sms_id': sms_msg.id,
                'total_recipients': len(recipients),
                'sent_count': sms_msg.sent_count,
                'failed_count': sms_msg.failed_count,
                'status': sms_msg.status
            }, status=status.HTTP_200_OK if sms_msg.status == 'sent' else status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            logger.error(f"Error in SendBulkSMSAPIView: {str(e)}")
            return Response(
                {'error': f"Failed to send message: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SendBirthdaySMSAPIView(APIView):
    """Send birthday wishes to all employees/clients having birthday today"""
    
    def post(self, request):
        today = timezone.now().date()
        
        # Find users with birthday today
        users = User.objects.filter(
            birthdate__month=today.month, 
            birthdate__day=today.day, 
            is_active=True
        )
        
        # Find clients with birthday today
        clients = Client.objects.filter(
            birthdate__month=today.month, 
            birthdate__day=today.day, 
            is_active=True
        )
        
        recipients = list(users) + list(clients)
        
        if not recipients:
            return Response({'message': 'No birthdays found today'}, status=status.HTTP_200_OK)
            
        try:
            sms_service = SMSService()
            sent_count = 0
            for recipient in recipients:
                success = sms_service.send_birthday_wish(recipient)
                if success:
                    sent_count += 1
            
            return Response({
                'message': f'Birthday wishes processed',
                'total_found': len(recipients),
                'successfully_sent': sent_count
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in SendBirthdaySMSAPIView: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SMSHistoryAPIView(APIView):
    """Get history of all bulk/birthday SMS messages"""
    
    def get(self, request):
        messages = SMSMessage.objects.all().order_by('-created_at')
        serializer = SMSMessageListSerializer(messages, many=True)
        return Response(serializer.data)


class SMSDetailAPIView(APIView):
    """Get detailed logs for a specific SMS message"""
    
    def get(self, request, sms_id):
        try:
            message = SMSMessage.objects.get(id=sms_id)
            serializer = SMSMessageDetailSerializer(message)
            return Response(serializer.data)
        except SMSMessage.DoesNotExist:
            return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)


class SMSStatsAPIView(APIView):
    """Get simple statistics about SMS delivery"""
    
    def get(self, request):
        total_messages = SMSMessage.objects.count()
        total_logs = SMSLog.objects.count()
        sent_logs = SMSLog.objects.filter(status='sent').count()
        failed_logs = SMSLog.objects.filter(status='failed').count()
        
        return Response({
            'total_bulk_messages': total_messages,
            'total_individual_logs': total_logs,
            'total_sent': sent_logs,
            'total_failed': failed_logs,
            'success_rate': (sent_logs / total_logs * 100) if total_logs > 0 else 0
        })
