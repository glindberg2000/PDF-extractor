# Background Processing System Design

## Overview
The background processing system will handle long-running transaction processing tasks asynchronously, preventing browser timeouts and providing better user experience. This document outlines the design and implementation strategy.

## Core Components

### 1. Task Model
```python
class ProcessingTask(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ]
    
    TASK_TYPES = [
        ('payee_lookup', 'Payee Lookup'),
        ('classification', 'Classification')
    ]
    
    task_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    task_type = models.CharField(max_length=20, choices=TASK_TYPES)
    client = models.ForeignKey(BusinessProfile, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    transaction_count = models.IntegerField()
    processed_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    error_details = models.JSONField(default=dict)
    task_metadata = models.JSONField(default=dict)  # For storing dynamic configuration
```

### 2. Task Queue Design

#### Option 1: Minimal Queue (Recommended)
Store only essential data in Redis:
```python
{
    "task_id": "uuid",
    "transaction_ids": [1, 2, 3, ...],
    "client_id": "client_id",
    "task_type": "payee_lookup|classification"
}
```

**Pros:**
- Minimal data duplication
- Single source of truth (DB)
- Easier to maintain
- Less memory usage
- Simpler error handling

**Cons:**
- Slightly more DB reads
- Need to fetch configuration on each task

#### Option 2: Complete Queue
Store all execution data in Redis:
```python
{
    "task_id": "uuid",
    "transactions": [
        {
            "id": 1,
            "description": "...",
            "amount": "...",
            "client_context": {...},
            "agent_prompt": "...",
            "tools": [...]
        },
        ...
    ]
}
```

**Pros:**
- Faster processing (no DB reads)
- Complete isolation
- Easier to scale horizontally

**Cons:**
- Data duplication
- More complex error handling
- Harder to maintain consistency
- Higher memory usage
- More complex to update if business logic changes

## Implementation Strategy

### Phase 1: Task Creation
```python
def create_processing_task(transaction_ids, client_id, task_type):
    task = ProcessingTask.objects.create(
        task_type=task_type,
        client_id=client_id,
        transaction_count=len(transaction_ids)
    )
    
    # Store minimal data in Redis
    redis_data = {
        "task_id": str(task.task_id),
        "transaction_ids": transaction_ids,
        "client_id": client_id,
        "task_type": task_type
    }
    
    redis_client.rpush(f'task:{task.task_id}', json.dumps(redis_data))
    return task
```

### Phase 2: Worker Implementation
```python
@celery.task
def process_transaction_batch(task_id):
    task = ProcessingTask.objects.get(task_id=task_id)
    task.status = 'processing'
    task.save()
    
    # Get task data from Redis
    task_data = json.loads(redis_client.lpop(f'task:{task.task_id}'))
    
    # Get client context once
    client = BusinessProfile.objects.get(client_id=task_data['client_id'])
    client_context = {
        'business_type': client.business_type,
        'business_description': client.business_description,
        'common_expenses': client.common_expenses,
        'custom_categories': client.custom_categories
    }
    
    # Process each transaction
    for transaction_id in task_data['transaction_ids']:
        try:
            transaction = Transaction.objects.get(id=transaction_id)
            
            # Get agent configuration
            agent = Agent.objects.get(
                name='payee_lookup_agent' if task_data['task_type'] == 'payee_lookup' 
                else 'classification_agent'
            )
            
            # Process transaction
            result = call_agent(
                agent.name,
                transaction,
                client_context=client_context
            )
            
            # Update transaction
            update_transaction(transaction, result)
            
            task.processed_count += 1
        except Exception as e:
            task.error_count += 1
            task.error_details[str(transaction_id)] = str(e)
        
        task.save()
    
    task.status = 'completed'
    task.save()
```

### Phase 3: Admin Integration
```python
class TransactionAdmin(admin.ModelAdmin):
    actions = ['process_payee_lookup', 'process_classification']
    
    def process_payee_lookup(self, request, queryset):
        task = create_processing_task(
            list(queryset.values_list('id', flat=True)),
            queryset.first().client.client_id,
            'payee_lookup'
        )
        process_transaction_batch.delay(str(task.task_id))
        messages.success(request, f'Started payee lookup for {queryset.count()} transactions')
        
    def process_classification(self, request, queryset):
        task = create_processing_task(
            list(queryset.values_list('id', flat=True)),
            queryset.first().client.client_id,
            'classification'
        )
        process_transaction_batch.delay(str(task.task_id))
        messages.success(request, f'Started classification for {queryset.count()} transactions')
```

## Error Handling

1. **Task Level Errors**
   - Track failed transactions
   - Store error details
   - Allow retry of failed items

2. **System Level Errors**
   - Redis connection issues
   - Celery worker crashes
   - Database connection issues

3. **Recovery Strategy**
   - Automatic retry for transient errors
   - Manual retry for persistent errors
   - Partial completion tracking

## Monitoring

1. **Task Progress**
   - Real-time progress updates
   - Error rate monitoring
   - Processing speed metrics

2. **System Health**
   - Redis queue length
   - Celery worker status
   - Memory usage
   - Error rates

## Testing Strategy

1. **Unit Tests**
   - Task creation
   - Worker processing
   - Error handling
   - Redis operations

2. **Integration Tests**
   - Full processing pipeline
   - Error scenarios
   - Recovery procedures

3. **Performance Tests**
   - Large batch processing
   - Concurrent tasks
   - Resource usage

## Deployment Considerations

1. **Infrastructure**
   - Redis server setup
   - Celery worker configuration
   - Monitoring setup

2. **Scaling**
   - Multiple workers
   - Queue partitioning
   - Load balancing

3. **Maintenance**
   - Queue cleanup
   - Task archival
   - Error reporting

## Next Steps

1. Set up Redis and Celery infrastructure
2. Implement task model and admin interface
3. Create worker implementation
4. Add monitoring and error handling
5. Test with small batches
6. Deploy to staging
7. Monitor and optimize 

## Logging and Debugging

### 1. Real-time Logging System
```python
class TaskLogger:
    def __init__(self, task_id):
        self.task_id = task_id
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0)
        
    def log(self, level, message, transaction_id=None, extra_data=None):
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message,
            'transaction_id': transaction_id,
            'extra_data': extra_data
        }
        self.redis_client.rpush(f'logs:{self.task_id}', json.dumps(log_entry))
        
    def get_logs(self, limit=100):
        logs = self.redis_client.lrange(f'logs:{self.task_id}', 0, limit-1)
        return [json.loads(log) for log in logs]
```

### 2. Worker Logging Integration
```python
@celery.task
def process_transaction_batch(task_id):
    logger = TaskLogger(task_id)
    task = ProcessingTask.objects.get(task_id=task_id)
    
    try:
        logger.log('info', f'Starting task {task_id}')
        task.status = 'processing'
        task.save()
        
        # Get task data from Redis
        task_data = json.loads(redis_client.lpop(f'task:{task.task_id}'))
        logger.log('info', f'Processing {len(task_data["transaction_ids"])} transactions')
        
        # Get client context once
        client = BusinessProfile.objects.get(client_id=task_data['client_id'])
        logger.log('info', f'Loaded client context for {client.client_id}')
        
        # Process each transaction
        for transaction_id in task_data['transaction_ids']:
            try:
                logger.log('info', f'Processing transaction {transaction_id}', transaction_id)
                transaction = Transaction.objects.get(id=transaction_id)
                
                # Get agent configuration
                agent = Agent.objects.get(
                    name='payee_lookup_agent' if task_data['task_type'] == 'payee_lookup' 
                    else 'classification_agent'
                )
                logger.log('debug', f'Using agent {agent.name}', transaction_id)
                
                # Process transaction
                result = call_agent(
                    agent.name,
                    transaction,
                    client_context=client_context
                )
                logger.log('info', f'Agent response: {result}', transaction_id)
                
                # Update transaction
                update_transaction(transaction, result)
                logger.log('info', f'Updated transaction {transaction_id}', transaction_id)
                
                task.processed_count += 1
            except Exception as e:
                error_msg = f'Error processing transaction {transaction_id}: {str(e)}'
                logger.log('error', error_msg, transaction_id, {'traceback': traceback.format_exc()})
                task.error_count += 1
                task.error_details[str(transaction_id)] = str(e)
            
            task.save()
        
        logger.log('info', f'Completed task {task_id}')
        task.status = 'completed'
        task.save()
        
    except Exception as e:
        logger.log('error', f'Task failed: {str(e)}', extra_data={'traceback': traceback.format_exc()})
        task.status = 'failed'
        task.save()
```

### 3. Admin Interface for Logs
```python
class ProcessingTaskAdmin(admin.ModelAdmin):
    # ... existing code ...
    
    def view_logs(self, request, task_id):
        task = self.get_object(request, task_id)
        logger = TaskLogger(task_id)
        logs = logger.get_logs()
        return render(request, 'admin/task_logs.html', {
            'task': task,
            'logs': logs
        })
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<task_id>/logs/',
                self.admin_site.admin_view(self.view_logs),
                name='task-logs'
            ),
        ]
        return custom_urls + urls
```

### 4. Real-time Log Viewing
```html
<!-- templates/admin/task_logs.html -->
{% extends "admin/base_site.html" %}

{% block content %}
<div class="module">
    <h2>Task Logs: {{ task.task_id }}</h2>
    <div id="log-container" style="height: 500px; overflow-y: auto; background: #f5f5f5; padding: 10px;">
        {% for log in logs %}
        <div class="log-entry" style="margin-bottom: 5px; padding: 5px; border-bottom: 1px solid #ddd;">
            <span style="color: #666;">{{ log.timestamp }}</span>
            <span style="color: {% if log.level == 'error' %}#d9534f{% elif log.level == 'warning' %}#f0ad4e{% else %}#5cb85c{% endif %}">
                [{{ log.level|upper }}]
            </span>
            <span>{{ log.message }}</span>
            {% if log.transaction_id %}
            <span style="color: #337ab7;">(Transaction: {{ log.transaction_id }})</span>
            {% endif %}
        </div>
        {% endfor %}
    </div>
</div>

<script>
// Auto-refresh logs every 5 seconds
setInterval(function() {
    fetch(window.location.href)
        .then(response => response.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newLogs = doc.querySelector('#log-container').innerHTML;
            document.querySelector('#log-container').innerHTML = newLogs;
        });
}, 5000);
</script>
{% endblock %}
```

### 5. Log Retention and Cleanup
```python
def cleanup_old_logs():
    """Clean up logs older than 7 days"""
    cutoff = datetime.now() - timedelta(days=7)
    for task_id in redis_client.keys('logs:*'):
        logs = redis_client.lrange(task_id, 0, -1)
        for log in logs:
            log_data = json.loads(log)
            if datetime.fromisoformat(log_data['timestamp']) < cutoff:
                redis_client.lrem(task_id, 1, log)
```

### 6. Debugging Tools

1. **Log Levels**
   - ERROR: Critical issues that prevent processing
   - WARNING: Potential issues that don't stop processing
   - INFO: General processing information
   - DEBUG: Detailed information for debugging

2. **Log Search**
   - Search logs by transaction ID
   - Filter by log level
   - Search by message content
   - Time-based filtering

3. **Performance Metrics**
   - Processing time per transaction
   - API call durations
   - Memory usage
   - Queue lengths

4. **Error Analysis**
   - Error patterns
   - Common failure points
   - Retry statistics
   - Success rates

### 7. Monitoring Dashboard
```python
class TaskMonitorView(LoginRequiredMixin, TemplateView):
    template_name = 'admin/task_monitor.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Active tasks
        active_tasks = ProcessingTask.objects.filter(
            status__in=['pending', 'processing']
        ).order_by('-created_at')
        
        # Task statistics
        stats = {
            'total_tasks': ProcessingTask.objects.count(),
            'active_tasks': active_tasks.count(),
            'completed_tasks': ProcessingTask.objects.filter(status='completed').count(),
            'failed_tasks': ProcessingTask.objects.filter(status='failed').count(),
            'avg_processing_time': ProcessingTask.objects.filter(
                status='completed'
            ).aggregate(Avg('updated_at' - 'created_at'))['updated_at__avg']
        }
        
        context.update({
            'active_tasks': active_tasks,
            'stats': stats
        })
        return context
```

This logging system provides:
1. Real-time visibility into task processing
2. Detailed transaction-level logging
3. Error tracking and debugging
4. Performance monitoring
5. Historical log access
6. Automatic log cleanup

Would you like me to implement any specific part of this logging system first? 