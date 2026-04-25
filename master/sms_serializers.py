from rest_framework import serializers
from master.models import SMSMessage, SMSLog, Client
from userauth.models import User


class SMSLogSerializer(serializers.ModelSerializer):
    recipient_name = serializers.CharField(source='recipient.full_name', read_only=True)
    
    class Meta:
        model = SMSLog
        fields = ['id', 'recipient_name', 'recipient_phone', 'status', 
                  'error_message', 'sent_at', 'created_at']


class SendBulkSMSSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=160, required=False, allow_blank=True)
    recipient_type = serializers.ChoiceField(choices=['employees', 'clients', 'all'])
    recipients = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )
    template_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    template_params = serializers.CharField(max_length=255, required=False, allow_blank=True)
    
    def validate(self, data):
        recipient_type = data.get('recipient_type')
        recipients_ids = data.get('recipients', [])
        
        if recipients_ids:
            for rid in recipients_ids:
                if recipient_type == 'employees':
                    if not User.objects.filter(id=rid).exists():
                        raise serializers.ValidationError(f"Employee with ID {rid} does not exist.")
                elif recipient_type == 'clients':
                    if not Client.objects.filter(id=rid).exists():
                        raise serializers.ValidationError(f"Client with ID {rid} does not exist.")
                else: # 'all'
                    exists = User.objects.filter(id=rid).exists() or Client.objects.filter(id=rid).exists()
                    if not exists:
                        raise serializers.ValidationError(f"Recipient with ID {rid} not found in Employees or Clients.")
                        
        return data


class SMSMessageListSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, allow_null=True)
    recipient_count = serializers.SerializerMethodField()
    
    class Meta:
        model = SMSMessage
        fields = ['id', 'message_type', 'message_content', 'status', 
                  'sent_count', 'failed_count', 'recipient_count', 
                  'created_at', 'sent_at', 'created_by_name']
    
    def get_recipient_count(self, obj):
        return obj.recipients.count()


class SMSMessageDetailSerializer(serializers.ModelSerializer):
    logs = SMSLogSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, allow_null=True)
    recipient_list = serializers.SerializerMethodField()
    
    class Meta:
        model = SMSMessage
        fields = ['id', 'message_type', 'message_content', 'status', 
                  'sent_count', 'failed_count', 'created_at', 'sent_at', 
                  'created_by_name', 'recipient_list', 'logs']
    
    def get_recipient_list(self, obj):
        return list(obj.recipients.values_list('id', 'full_name', 'phone_no'))
