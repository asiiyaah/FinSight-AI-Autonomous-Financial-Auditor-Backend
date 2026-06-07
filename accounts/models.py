from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
# allows us to add custom fields (like profile pics or phone numbers)
# in the future without wiping or breaking the database.
class CustomUser(AbstractUser):
    pass