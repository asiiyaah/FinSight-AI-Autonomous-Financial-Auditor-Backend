from django.db import models
from django.conf import settings
# Create your models here.

class Statement(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    file=models.FileField(upload_to='statements/')
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=10)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_parsed = models.BooleanField(default=False)
    audit_status = models.BooleanField(default=False)
    summary = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.file_name}"
    
class Transaction(models.Model):
    statement = models.ForeignKey(Statement, on_delete=models.CASCADE, related_name='transactions')
    date = models.DateField()
    vendor = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=100, blank=True)
    raw_description = models.TextField(null=True, blank=True)
    transaction_type = models.CharField(
    max_length=10,
    default="debit"
    )

    def __str__(self):
        return f"{self.date} - {self.vendor} - {self.amount}"
    
