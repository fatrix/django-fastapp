from django.db import models
from django.contrib.auth.models import User


class AuthProfile(models.Model):
    user = models.ForeignKey(User)
    access_token = models.CharField(max_length=72)
