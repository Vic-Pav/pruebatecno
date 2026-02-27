"""
Personalización del Django Admin para Celery.
"""
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule
from django_celery_results.models import TaskResult
from django.contrib import messages
from django.shortcuts import redirect

# ==================== PERIODIC TASKS ====================
class CustomPeriodicTaskAdmin(admin.ModelAdmin):
    """Admin personalizado para tareas periódicas."""
    
    list_display = [
        'name',
        'task',
        'enabled',
        'schedule_display',
        'last_run_display',
        'total_run_count',
        'actions_column',
    ]
    
    list_filter = ['enabled', 'task', 'queue']
    search_fields = ['name', 'task']
    
    fieldsets = (
        ('Task Information', {
            'fields': ('name', 'task', 'enabled', 'description')
        }),
        ('Schedule', {
            'fields': ('interval', 'crontab', 'solar', 'clocked', 'start_time', 'expires')
        }),
        ('Execution Options', {
            'fields': ('queue', 'exchange', 'routing_key', 'priority', 'one_off')
        }),
        ('Arguments', {
            'fields': ('args', 'kwargs'),
            'classes': ('collapse',)
        }),
    )
    
    def schedule_display(self, obj):
        """Muestra el schedule de forma legible."""
        if obj.interval:
            return f"Every {obj.interval}"
        elif obj.crontab:
            return f"Cron: {obj.crontab}"
        elif obj.solar:
            return f"Solar: {obj.solar}"
        elif obj.clocked:
            return f"Once at: {obj.clocked.clocked_time}"
        return "No schedule"
    schedule_display.short_description = 'Schedule'
    
    def last_run_display(self, obj):
        """Muestra la última ejecución."""
        if obj.last_run_at:
            from django.utils.timesince import timesince
            return f"{timesince(obj.last_run_at)} ago"
        return "Never"
    last_run_display.short_description = 'Last Run'
    
    def actions_column(self, obj):
        """Botones de acciones rápidas."""
        return format_html(
            '<a class="button" href="{}">Run Now</a>',
            reverse('admin:run_periodic_task', args=[obj.pk])
        )
    actions_column.short_description = 'Actions'
    
    def get_urls(self):
        """Añadir URL personalizada para ejecutar tareas."""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:task_id>/run/',
                self.admin_site.admin_view(self.run_task_view),
                name='run_periodic_task',
            ),
        ]
        return custom_urls + urls
    
    def run_task_view(self, request, task_id):
        """Ejecuta una tarea manualmente."""
        task = PeriodicTask.objects.get(pk=task_id)
        
        # Importar la tarea de Celery
        from pruebatecno.celery import celery_app
        
        # Ejecutar de forma asíncrona
        celery_app.send_task(
            task.task,
            args=eval(task.args) if task.args else [],
            kwargs=eval(task.kwargs) if task.kwargs else {},
            queue=task.queue or 'default',
        )
        
        messages.success(request, f'Task "{task.name}" has been queued for execution.')
        return redirect('admin:django_celery_beat_periodictask_changelist')

# Reemplazar el admin por defecto
admin.site.unregister(PeriodicTask)
admin.site.register(PeriodicTask, CustomPeriodicTaskAdmin)

# ==================== TASK RESULTS ====================
class CustomTaskResultAdmin(admin.ModelAdmin):
    """Admin personalizado para resultados de tareas."""
    
    list_display = [
        'task_name',
        'status_colored',
        'date_done_display',
        'result_preview',
        'view_details',
    ]
    
    list_filter = ['status', 'task_name', 'date_done']
    search_fields = ['task_name', 'task_id']
    readonly_fields = ['task_id', 'task_name', 'task_args', 'task_kwargs', 'result', 'traceback']
    
    def status_colored(self, obj):
        """Status con colores."""
        colors = {
            'SUCCESS': 'green',
            'FAILURE': 'red',
            'PENDING': 'orange',
            'RETRY': 'blue',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.status
        )
    status_colored.short_description = 'Status'
    
    def date_done_display(self, obj):
        """Muestra cuándo se completó."""
        if obj.date_done:
            from django.utils.timesince import timesince
            return f"{timesince(obj.date_done)} ago"
        return "N/A"
    date_done_display.short_description = 'Completed'
    
    def result_preview(self, obj):
        """Preview del resultado."""
        if obj.result:
            result_str = str(obj.result)[:50]
            if len(str(obj.result)) > 50:
                result_str += "..."
            return result_str
        return "No result"
    result_preview.short_description = 'Result'
    
    def view_details(self, obj):
        """Link para ver detalles completos."""
        return format_html(
            '<a href="{}">View Full</a>',
            reverse('admin:django_celery_results_taskresult_change', args=[obj.pk])
        )
    view_details.short_description = 'Details'

# Reemplazar el admin por defecto
admin.site.unregister(TaskResult)
admin.site.register(TaskResult, CustomTaskResultAdmin)

# ==================== PANEL DE CONTROL PERSONALIZADO ====================
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

@staff_member_required
def celery_monitor_view(request):
    """Panel de monitoreo personalizado."""
    from pruebatecno.celery import celery_app
    
    # Inspeccionar workers activos
    inspect = celery_app.control.inspect()
    
    active_workers = inspect.active() or {}
    scheduled_tasks = inspect.scheduled() or {}
    registered_tasks = inspect.registered() or {}
    
    # Estadísticas de tareas
    total_success = TaskResult.objects.filter(status='SUCCESS').count()
    total_failure = TaskResult.objects.filter(status='FAILURE').count()
    total_pending = TaskResult.objects.filter(status='PENDING').count()
    
    context = {
        'active_workers': active_workers,
        'scheduled_tasks': scheduled_tasks,
        'registered_tasks': registered_tasks,
        'total_success': total_success,
        'total_failure': total_failure,
        'total_pending': total_pending,
    }
    
    return render(request, 'admin/celery_monitor.html', context)