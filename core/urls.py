# core/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from strawberry.django.views import GraphQLView
from health.schema import schema as health_schema
@login_required
def dashboard_redirect(request):
    if request.user.role == 'student':
        return HttpResponseRedirect(reverse('dashboard:student'))
    elif request.user.role == 'teacher':
        return HttpResponseRedirect(reverse('dashboard:teacher'))
    elif request.user.role == 'counselor':
        return HttpResponseRedirect(reverse('dashboard:counselor'))
    elif request.user.role == 'parent':
        return HttpResponseRedirect(reverse('dashboard:parent'))
    else:
        return HttpResponseRedirect('/admin/')

@login_required
def iphone_home(request):
    return render(request, 'iphone/home.html', {'user': request.user})

@login_required
def profile_view(request):
    return render(request, 'accounts/profile.html', {'user': request.user})


# core/urls.py

from django.views.decorators.csrf import csrf_exempt
from strawberry.django.views import GraphQLView
from health.schema import schema as health_schema   # ← ajouter

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('dashboard/redirect/', dashboard_redirect, name='dashboard_redirect'),
    path('dashboard/', include('dashboard.urls')),
    path('iphone/', iphone_home, name='iphone_home'),
    path('profile/', profile_view, name='profile'),
    path('warning/', include('early_warning.urls')),
    path('health/', include('health.urls')),
    path('health/graphql/', csrf_exempt(GraphQLView.as_view(schema=health_schema)), name='health_graphql'),  
    path('education/', include('education.urls')),
    path('study/', include('study.urls')),
    path('audit/', include('audit.urls')),
    path('', include('education.urls_social')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)