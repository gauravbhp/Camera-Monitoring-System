from django import forms

class EmailConfigForm(forms.Form):
    """Email configuration form"""
    email_host = forms.CharField(
        label='SMTP Host',
        max_length=100,
        initial='smtp.gmail.com'
    )
    email_port = forms.IntegerField(
        label='SMTP Port',
        initial=587,
        min_value=1,
        max_value=65535
    )
    email_use_tls = forms.BooleanField(
        label='Use TLS',
        initial=True,
        required=False
    )
    email_host_user = forms.EmailField(
        label='Email Address',
        required=True
    )
    email_host_password = forms.CharField(
        label='App Password',
        widget=forms.PasswordInput,
        required=True
    )
    alert_recipients = forms.CharField(
        label='Alert Recipients (comma separated)',
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text='Enter email addresses separated by commas'
    )
    send_daily_report = forms.BooleanField(
        label='Send Daily Report',
        initial=True,
        required=False
    )
    send_alerts_for_critical = forms.BooleanField(
        label='Send Urgent Alerts for Critical Cameras',
        initial=True,
        required=False
    )
    alert_threshold = forms.IntegerField(
        label='Alert Threshold',
        initial=5,
        min_value=1,
        help_text='Send urgent alert if this many critical cameras are down'
    )
    daily_check_time = forms.CharField(
        label='Daily Check Time',
        max_length=5,
        initial='15:29',
        help_text='Format: HH:MM (24-hour)'
    )