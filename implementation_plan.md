# PDF Extractor Web App Implementation Plan

## Initial Phase: Business Profile Management & Database Setup

### 1. Project Setup

```bash
# Create Django project
mkdir pdf_extractor_web
cd pdf_extractor_web
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install django django-htmx psycopg2-binary python-dotenv pyyaml

# Initialize Django project
django-admin startproject core .
python manage.py startapp profiles
```

### 2. Database Configuration

1. Edit `core/settings.py`:

```python
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ... existing settings ...

INSTALLED_APPS = [
    # Default Django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Custom apps
    'profiles',
]

# Database Configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'pdf_extractor'),
        'USER': os.getenv('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', ''),
        'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
    }
}
```

### 3. Define Models (profiles/models.py)

```python
from django.db import models
import json

class BusinessProfile(models.Model):
    client_id = models.CharField(max_length=255, primary_key=True)
    business_type = models.TextField(blank=True, null=True)
    business_description = models.TextField(blank=True, null=True)
    custom_categories = models.JSONField(default=dict, blank=True)
    industry_keywords = models.JSONField(default=list, blank=True)
    category_patterns = models.JSONField(default=dict, blank=True)
    industry_insights = models.TextField(blank=True, null=True)
    category_hierarchy = models.JSONField(default=dict, blank=True)
    business_context = models.TextField(blank=True, null=True)
    profile_data = models.JSONField(default=dict, blank=True)
    
    # Method to generate/update client_config.yaml
    def generate_config_file(self, output_path=None):
        """
        Generate client_config.yaml based on profile data.
        If output_path is None, returns the YAML as a string.
        """
        import yaml
        import os
        from datetime import datetime
        
        # Base configuration structure
        config = {
            'name': self.client_id,
            'type': self.business_type or 'business',
            'sheets': {
                'sheetname': f"{self.client_id} Financial Data",
                'sheet_id': "",  # Placeholder for Google Sheets ID
            },
            'parsers': [],  # Will be populated from profile_data if available
            'ai_settings': {
                'assistant': "AmeliaAI",
                'batch_size': 25,
                'expense_threshold': 0.0,
            },
            'categories': [],  # Will be populated from custom_categories
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Add parsers from profile_data or use defaults
        if 'parsers' in self.profile_data:
            config['parsers'] = self.profile_data['parsers']
        else:
            # Default parsers
            config['parsers'] = [
                'amazon', 'bofa_bank', 'bofa_visa', 'chase_visa',
                'wellsfargo_bank', 'wellsfargo_mastercard', 'wellsfargo_visa',
                'wellsfargo_bank_csv', 'first_republic_bank'
            ]
        
        # Add categories from custom_categories
        if self.custom_categories and 'categories' in self.custom_categories:
            config['categories'] = self.custom_categories['categories']
        elif self.custom_categories:
            # Assume custom_categories might be a direct list
            config['categories'] = list(self.custom_categories.keys())
        else:
            # Default categories
            config['categories'] = [
                "Advertising", "Contractors", "Equipment", "Insurance",
                "Office Supplies", "Professional Services", 
                "Software/Subscriptions", "Travel", "Utilities", "Other"
            ]
        
        # If AI settings are specified in profile_data, use those
        if 'ai_settings' in self.profile_data:
            config['ai_settings'].update(self.profile_data['ai_settings'])
        
        # Convert to YAML
        yaml_str = yaml.dump(config, default_flow_style=False, sort_keys=False)
        
        # Write to file if path is provided
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w') as f:
                f.write(yaml_str)
            return output_path
        
        return yaml_str
    
    # Method to import from client_config.yaml
    @classmethod
    def from_config_file(cls, config_path):
        """
        Create or update a BusinessProfile instance from a client_config.yaml file.
        Returns the BusinessProfile instance (not saved to database).
        """
        import yaml
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Extract client_id from config name or filename
        client_id = config.get('name', os.path.basename(os.path.dirname(config_path)))
        
        # Create or get profile instance
        profile, created = cls.objects.get_or_create(client_id=client_id)
        
        # Update fields
        profile.business_type = config.get('type', 'business')
        
        # Handle categories
        if 'categories' in config:
            if isinstance(profile.custom_categories, dict):
                profile.custom_categories['categories'] = config['categories']
            else:
                profile.custom_categories = {'categories': config['categories']}
        
        # Store parsers and AI settings in profile_data
        profile.profile_data = {
            'parsers': config.get('parsers', []),
            'ai_settings': config.get('ai_settings', {}),
            'sheets': config.get('sheets', {})
        }
        
        return profile


class ClientExpenseCategory(models.Model):
    client = models.ForeignKey(BusinessProfile, on_delete=models.CASCADE, related_name='expense_categories')
    category_name = models.CharField(max_length=255)
    category_type = models.CharField(
        max_length=50,
        choices=[('Income', 'Income'), ('Expense', 'Expense')]
    )
    description = models.TextField(blank=True, null=True)
    tax_year = models.IntegerField()
    worksheet = models.CharField(
        max_length=50,
        choices=[
            ('6A', '6A'), 
            ('Auto', 'Auto'), 
            ('HomeOffice', 'HomeOffice'), 
            ('Personal', 'Personal'), 
            ('None', 'None')
        ]
    )
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['client', 'category_name', 'tax_year'], 
                name='unique_client_category_year'
            )
        ]
```

### 4. Admin Interface

Create `profiles/admin.py`:

```python
from django.contrib import admin
from .models import BusinessProfile, ClientExpenseCategory

@admin.register(BusinessProfile)
class BusinessProfileAdmin(admin.ModelAdmin):
    list_display = ('client_id', 'business_type')
    search_fields = ('client_id', 'business_description')

@admin.register(ClientExpenseCategory)
class ClientExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('category_name', 'client', 'category_type', 'tax_year', 'worksheet')
    list_filter = ('category_type', 'tax_year', 'worksheet')
    search_fields = ('category_name', 'description')
```

### 5. Forms for Business Profile

Create `profiles/forms.py`:

```python
from django import forms
from .models import BusinessProfile, ClientExpenseCategory
import json

class BusinessProfileForm(forms.ModelForm):
    # Add a non-model field for handling YAML uploads
    config_file = forms.FileField(required=False, help_text="Upload client_config.yaml")
    
    class Meta:
        model = BusinessProfile
        fields = [
            'client_id', 'business_type', 'business_description',
            'industry_keywords', 'industry_insights', 'business_context'
        ]
        widgets = {
            'industry_keywords': forms.Textarea(attrs={'rows': 4}),
            'business_description': forms.Textarea(attrs={'rows': 4}),
            'industry_insights': forms.Textarea(attrs={'rows': 4}),
            'business_context': forms.Textarea(attrs={'rows': 4}),
        }
    
    def clean_industry_keywords(self):
        """Convert textarea input (one keyword per line) to JSON list"""
        keywords = self.cleaned_data['industry_keywords']
        if isinstance(keywords, str):
            # If keywords is a string, assume it's a newline-separated list
            keywords = [k.strip() for k in keywords.split('\n') if k.strip()]
        return keywords


class CategoryForm(forms.ModelForm):
    class Meta:
        model = ClientExpenseCategory
        fields = ['category_name', 'category_type', 'description', 'tax_year', 'worksheet']
```

### 6. Views for Business Profile

Create `profiles/views.py`:

```python
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
import os
import yaml
import json
from .models import BusinessProfile, ClientExpenseCategory
from .forms import BusinessProfileForm, CategoryForm

class BusinessProfileListView(ListView):
    model = BusinessProfile
    template_name = 'profiles/profile_list.html'
    context_object_name = 'profiles'

class BusinessProfileDetailView(DetailView):
    model = BusinessProfile
    template_name = 'profiles/profile_detail.html'
    context_object_name = 'profile'
    pk_url_kwarg = 'client_id'
    
    def get_object(self):
        return get_object_or_404(BusinessProfile, client_id=self.kwargs['client_id'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = self.object.expense_categories.all()
        return context

class BusinessProfileCreateView(CreateView):
    model = BusinessProfile
    form_class = BusinessProfileForm
    template_name = 'profiles/profile_form.html'
    success_url = reverse_lazy('profile-list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Handle config file upload if provided
        if 'config_file' in self.request.FILES:
            config_file = self.request.FILES['config_file']
            config_data = yaml.safe_load(config_file)
            
            # Update profile with config data
            profile = self.object
            profile.business_type = config_data.get('type', profile.business_type)
            
            # Update profile_data with parsers and AI settings
            profile_data = {}
            if 'parsers' in config_data:
                profile_data['parsers'] = config_data['parsers']
            if 'ai_settings' in config_data:
                profile_data['ai_settings'] = config_data['ai_settings']
            if 'sheets' in config_data:
                profile_data['sheets'] = config_data['sheets']
            
            profile.profile_data = profile_data
            
            # Update custom_categories
            if 'categories' in config_data:
                profile.custom_categories = {'categories': config_data['categories']}
            
            profile.save()
            
            # Create categories based on config
            if 'categories' in config_data:
                for category_name in config_data['categories']:
                    ClientExpenseCategory.objects.get_or_create(
                        client=profile,
                        category_name=category_name,
                        defaults={
                            'category_type': 'Expense',
                            'tax_year': 2023,  # Default to current year
                            'worksheet': 'None'
                        }
                    )
        
        messages.success(self.request, f"Profile '{self.object.client_id}' created successfully.")
        return response

class BusinessProfileUpdateView(UpdateView):
    model = BusinessProfile
    form_class = BusinessProfileForm
    template_name = 'profiles/profile_form.html'
    pk_url_kwarg = 'client_id'
    
    def get_object(self):
        return get_object_or_404(BusinessProfile, client_id=self.kwargs['client_id'])
    
    def get_success_url(self):
        return reverse('profile-detail', kwargs={'client_id': self.object.client_id})
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Profile '{self.object.client_id}' updated successfully.")
        return response

class BusinessProfileDeleteView(DeleteView):
    model = BusinessProfile
    template_name = 'profiles/profile_confirm_delete.html'
    success_url = reverse_lazy('profile-list')
    pk_url_kwarg = 'client_id'
    
    def get_object(self):
        return get_object_or_404(BusinessProfile, client_id=self.kwargs['client_id'])
    
    def delete(self, request, *args, **kwargs):
        profile = self.get_object()
        messages.success(request, f"Profile '{profile.client_id}' deleted successfully.")
        return super().delete(request, *args, **kwargs)

def download_config_yaml(request, client_id):
    profile = get_object_or_404(BusinessProfile, client_id=client_id)
    yaml_content = profile.generate_config_file()
    
    response = HttpResponse(yaml_content, content_type='application/x-yaml')
    response['Content-Disposition'] = f'attachment; filename="{client_id}_config.yaml"'
    return response

def import_config_yaml(request):
    if request.method == 'POST' and 'config_file' in request.FILES:
        config_file = request.FILES['config_file']
        config_data = yaml.safe_load(config_file)
        
        client_id = config_data.get('name')
        if not client_id:
            messages.error(request, "Invalid YAML: missing 'name' field")
            return redirect('profile-list')
        
        try:
            # Create or update profile based on YAML
            profile = BusinessProfile.objects.get(client_id=client_id)
            # Update existing profile
            profile.business_type = config_data.get('type', profile.business_type)
            # Update remaining fields...
        except BusinessProfile.DoesNotExist:
            # Create new profile
            profile = BusinessProfile(
                client_id=client_id,
                business_type=config_data.get('type', 'business')
            )
        
        # Set profile_data for parsers and AI settings
        profile_data = {}
        if 'parsers' in config_data:
            profile_data['parsers'] = config_data['parsers']
        if 'ai_settings' in config_data:
            profile_data['ai_settings'] = config_data['ai_settings']
        if 'sheets' in config_data:
            profile_data['sheets'] = config_data['sheets']
        
        profile.profile_data = profile_data
        
        # Handle categories
        if 'categories' in config_data:
            profile.custom_categories = {'categories': config_data['categories']}
        
        profile.save()
        
        messages.success(request, f"Profile '{client_id}' imported successfully.")
        return redirect('profile-detail', client_id=client_id)
    
    return render(request, 'profiles/import_config.html')
```

### 7. URLs Configuration

Create `profiles/urls.py`:

```python
from django.urls import path
from . import views

urlpatterns = [
    path('', views.BusinessProfileListView.as_view(), name='profile-list'),
    path('create/', views.BusinessProfileCreateView.as_view(), name='profile-create'),
    path('<str:client_id>/', views.BusinessProfileDetailView.as_view(), name='profile-detail'),
    path('<str:client_id>/edit/', views.BusinessProfileUpdateView.as_view(), name='profile-update'),
    path('<str:client_id>/delete/', views.BusinessProfileDeleteView.as_view(), name='profile-delete'),
    path('<str:client_id>/download-config/', views.download_config_yaml, name='download-config'),
    path('import-config/', views.import_config_yaml, name='import-config'),
]
```

Update `core/urls.py`:

```python
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('profiles/', include('profiles.urls')),
    path('', RedirectView.as_view(pattern_name='profile-list'), name='home'),
]
```

### 8. Templates

Create base templates structure:

```
mkdir -p profiles/templates/profiles
```

Create `profiles/templates/base.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}PDF Extractor{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://unpkg.com/htmx.org@1.9.0"></script>
    {% block extra_head %}{% endblock %}
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="{% url 'home' %}">PDF Extractor</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav">
                    <li class="nav-item">
                        <a class="nav-link" href="{% url 'profile-list' %}">Business Profiles</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{% url 'admin:index' %}">Admin</a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>

    <div class="container my-4">
        {% if messages %}
            {% for message in messages %}
                <div class="alert alert-{{ message.tags }}">
                    {{ message }}
                </div>
            {% endfor %}
        {% endif %}

        {% block content %}{% endblock %}
    </div>

    <footer class="bg-light py-3 mt-5">
        <div class="container text-center">
            <p class="text-muted">PDF Extractor Web App</p>
        </div>
    </footer>

    {% block extra_js %}{% endblock %}
</body>
</html>
```

Create basic templates for Business Profile CRUD operations (profiles/templates/profiles/):

1. `profile_list.html` - List of all business profiles
2. `profile_detail.html` - Detail view of a profile with categories
3. `profile_form.html` - Create/edit form
4. `profile_confirm_delete.html` - Confirmation page
5. `import_config.html` - Form to import config

### 9. Run migrations and create superuser

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### 10. Launch development server

```bash
python manage.py runserver
```

## Next Steps (After Basic Profile Management)

1. Implement categories management UI (CRUD operations for `ClientExpenseCategory`)
2. Add client_config.yaml import/export functionality
3. Create UI for viewing SQLite data (to eventually migrate to PostgreSQL)
4. Add authentication layer to restrict access
5. Begin implementing transaction management features
6. Develop the AI integration for profile insights

## Notes on Integration with CLI App

- The web app will operate independently of the CLI app.
- Both apps will have read/write access to the client_config.yaml files.
- The CLI app will continue using SQLite, while the web app will use PostgreSQL.
- Eventually, the parser component of the CLI app will be updated to write to PostgreSQL as well. 