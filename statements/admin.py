from django.contrib import admin
from .models import Statement,Transaction
# Register your models here.
admin.site.register(Statement)
admin.site.register(Transaction)