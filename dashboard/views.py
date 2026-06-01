from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from early_warning.models import Alert, RiskScore
from accounts.models import StudentProfile

# ⚠️ AJOUTE CETTE FONCTION MANQUANTE
@login_required
def iphone_home(request):
    return render(request, 'iphone/home.html')

@login_required
def dashboard_redirect(request):
    role = request.user.role
    if role == 'student':
        return redirect('dashboard_student')
    elif role == 'teacher':
        return redirect('dashboard_teacher')
    elif role == 'counselor':
        return redirect('dashboard_counselor')
    elif role == 'parent':
        return redirect('dashboard_parent')
    else:
        return redirect('iphone_home')

@login_required
def dashboard_student(request):
    return render(request, 'dashboard/student.html')

@login_required
def dashboard_teacher(request):
    if request.user.role != 'teacher':
        return redirect('iphone_home')
    
    alerts = Alert.objects.filter(
        student__teacher=request.user,
        status='pending'
    ).select_related('student__user', 'risk_score')
    
    high_risk_count = RiskScore.objects.filter(
        student__teacher=request.user,
        level='high'
    ).count()
    
    low_risk = RiskScore.objects.filter(student__teacher=request.user, level='low').count()
    medium_risk = RiskScore.objects.filter(student__teacher=request.user, level='medium').count()
    
    students_count = StudentProfile.objects.filter(teacher=request.user).count()
    intervention_count = Alert.objects.filter(student__teacher=request.user).count()
    
    context = {
        'alerts': alerts,
        'high_risk_count': high_risk_count,
        'low_risk': low_risk,
        'medium_risk': medium_risk,
        'students_count': students_count,
        'intervention_count': intervention_count,
    }
    return render(request, 'dashboard/teacher.html', context)

@login_required
def dashboard_counselor(request):
    return render(request, 'dashboard/counselor.html')

@login_required
def dashboard_parent(request):
    return render(request, 'dashboard/parent.html')