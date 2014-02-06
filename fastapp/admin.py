from django.contrib import admin
from fastapp.models import Base, Exec

class BaseAdmin(admin.ModelAdmin):
    pass
admin.site.register(Base, BaseAdmin)

class ExecAdmin(admin.ModelAdmin):
    pass
admin.site.register(Exec, ExecAdmin)