from django.db import models
# tasks/models.py
class Task(models.Model):
    title = models.CharField(max_length=200)
    completed = models.BooleanField(default=False)

