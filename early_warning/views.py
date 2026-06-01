# early_warning/views.py - VERSION CORRIGÉE ET FONCTIONNELLE

import csv
import logging
from datetime import datetime

import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ImportCSVForm, InterventionForm, ThresholdConfigForm
from .models import AISuggestion, Alert, Intervention, RiskScore, ThresholdConfig
from .services import NotificationService, RiskScoringService, TransformersAIService

# Import des services d'audit
from audit.services import log_action, log_error, log_success, log_blocked

logger = logging.getLogger(__name__)


# ========== DÉCORATEUR DE RÔLE ==========

def role_required(*allowed_roles):
    """Décorateur pour vérifier les rôles avec log d'audit"""
    def decorator(view_func):
        def wrapped_view(request, *args, **kwargs):
            if not hasattr(request.user, 'role') or request.user.role not in allowed_roles:
                log_blocked(
                    user=request.user,
                    action='unauthorized_access',
                    reason=f"Rôle '{getattr(request.user, 'role', 'unknown')}' non autorisé pour {request.path}",
                    case_id=request.path,
                    request=request
                )
                raise PermissionDenied("Vous n'avez pas les permissions nécessaires.")
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator


# ========== VUE 1 — IMPORT CSV ==========

@login_required
@role_required('teacher', 'admin')
def import_csv(request):
    """Import des données étudiants depuis un fichier CSV."""
    if request.method == 'POST':
        form = ImportCSVForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']

            try:
                df = pd.read_csv(csv_file)

                required = [
                    'student_name', 'student_id', 'class_name',
                    'absences', 'avg_grade', 'behavior_score',
                ]
                missing = [col for col in required if col not in df.columns]
                if missing:
                    error_msg = f"CSV malformé — colonnes manquantes: {', '.join(missing)}"
                    messages.error(request, error_msg)
                    return render(request, 'early_warning/import_csv.html', {'form': form, 'error': error_msg})

                # Validation des données
                errors = []
                for idx, row in df.iterrows():
                    try:
                        absences = float(row['absences'])
                        avg = float(row['avg_grade'])
                        behavior = float(row['behavior_score'])

                        if not (0 <= absences <= 100):
                            errors.append(f"Ligne {idx+2}: absences={absences} hors intervalle [0-100]")
                        if not (0 <= avg <= 20):
                            errors.append(f"Ligne {idx+2}: avg_grade={avg} hors intervalle [0-20]")
                        if not (0 <= behavior <= 10):
                            errors.append(f"Ligne {idx+2}: behavior_score={behavior} hors [0-10]")
                    except (ValueError, TypeError) as e:
                        errors.append(f"Ligne {idx+2}: valeur numérique invalide — {e}")

                if errors:
                    error_msg = f"Données invalides ({len(errors)} erreur(s)): " + " | ".join(errors[:5])
                    messages.error(request, error_msg)
                    return render(request, 'early_warning/import_csv.html', {'form': form, 'errors': errors})

                scoring_service = RiskScoringService()
                ai_service = TransformersAIService()
                config = ThresholdConfig.get_config()

                students_processed = 0
                alerts_created = 0
                errors_rows = []

                for idx, row in df.iterrows():
                    try:
                        risk_obj = scoring_service.calculate_risk_score(
                            student_name=str(row['student_name']).strip(),
                            student_id=str(row['student_id']).strip(),
                            class_name=str(row['class_name']).strip(),
                            absences=int(float(row['absences'])),
                            avg_grade=float(row['avg_grade']),
                            behavior_score=int(float(row['behavior_score'])),
                        )
                        students_processed += 1

                        if risk_obj.risk_score >= config.alert_threshold:
                            alert = Alert.objects.create(
                                risk_score=risk_obj,
                                message=f"Alerte auto — {risk_obj.student_name} — Score: {risk_obj.risk_score:.1f}/100",
                                status='pending',
                            )
                            ai_sugg = ai_service.get_ai_suggestion(risk_obj)
                            alert.ai_suggestion = ai_sugg
                            alert.save()
                            alerts_created += 1

                    except Exception as e:
                        errors_rows.append(f"Ligne {idx+2}: {e}")
                        logger.error(f"[ImportCSV] Erreur ligne {idx+2}: {e}")

                msg = f"Import terminé ! {students_processed} étudiants traités, {alerts_created} alertes générées."
                if errors_rows:
                    msg += f" ({len(errors_rows)} ligne(s) ignorée(s))"

                messages.success(request, msg)
                return redirect('early_warning:dashboard')

            except Exception as e:
                error_msg = f"Erreur lors de la lecture du CSV: {e}"
                messages.error(request, error_msg)
                return render(request, 'early_warning/import_csv.html', {'form': form})
    else:
        form = ImportCSVForm()

    return render(request, 'early_warning/import_csv.html', {'form': form})


# ========== VUE 2 — DASHBOARD (VERSION CORRIGÉE SANS FILTRE) ==========

# ========== VUE 2 — DASHBOARD (VERSION CORRIGÉE AVEC TOUS LES GRAPHIQUES) ==========

@login_required
def dashboard(request):
    """Dashboard principal avec statistiques dynamiques - Version complète"""
    
    # Récupérer TOUTES les données
    risks = RiskScore.objects.all()
    
    total_students = risks.count()
    high_risk_count = risks.filter(risk_level='high').count()
    medium_risk_count = risks.filter(risk_level='medium').count()
    low_risk_count = risks.filter(risk_level='low').count()
    
    top_risks = risks.order_by('-risk_score')[:10]
    
    alerts = (
        Alert.objects
        .select_related('risk_score', 'ai_suggestion')
        .exclude(status='resolved')
        .order_by('-created_at')[:10]
    )
    
    class_stats = (
        risks
        .values('class_name')
        .annotate(
            total=Count('id'),
            high=Count('id', filter=Q(risk_level='high')),
            avg_score=Avg('risk_score'),
        )
        .order_by('-high')[:8]
    )
    
    has_data = total_students > 0
    
    # ========== DONNÉES POUR LES GRAPHIQUES ==========
    
    # 1. Distribution des risques (camembert)
    risk_distribution_labels = ['Élevé', 'Moyen', 'Faible']
    risk_distribution_data = [high_risk_count, medium_risk_count, low_risk_count]
    
    # 2. Score moyen par classe
    class_avg = risks.values('class_name').annotate(avg_risk=Avg('risk_score'))
    class_avg_labels = [c['class_name'] for c in class_avg if c['class_name']]
    class_avg_data = [round(c['avg_risk'], 1) for c in class_avg if c['class_name']]
    
    # 3. Histogramme des scores
    risk_scores_list = list(risks.values_list('risk_score', flat=True))
    bins = [0, 20, 40, 60, 80, 100]
    histogram_data = [0] * (len(bins) - 1)
    for score in risk_scores_list:
        for i in range(len(bins) - 1):
            if bins[i] <= score < bins[i+1] or (i == len(bins)-2 and score == bins[i+1]):
                histogram_data[i] += 1
                break
    histogram_labels = ['0-20', '20-40', '40-60', '60-80', '80-100']
    
    # 4. Top 10 étudiants à risque
    top10_labels = [s.student_name for s in top_risks if s.student_name]
    top10_data = [s.risk_score for s in top_risks if s.student_name]
    
    # 5. Scatter plot Absences vs Risque
    scatter_absences = [
        {'x': r.absences, 'y': r.risk_score} 
        for r in risks.filter(absences__isnull=False) 
        if r.absences is not None
    ]
    
    # 6. Scatter plot Notes vs Risque
    scatter_grades = [
        {'x': r.avg_grade, 'y': r.risk_score} 
        for r in risks.filter(avg_grade__isnull=False) 
        if r.avg_grade is not None
    ]
    
    # 7. Nombre d'étudiants par classe
    class_count = risks.values('class_name').annotate(count=Count('id'))
    class_count_labels = [c['class_name'] for c in class_count if c['class_name']]
    class_count_data = [c['count'] for c in class_count if c['class_name']]
    
    # 8. Moyenne des notes par classe
    class_grades = risks.filter(avg_grade__isnull=False).values('class_name').annotate(avg_grade=Avg('avg_grade'))
    class_grades_labels = [c['class_name'] for c in class_grades if c['class_name']]
    class_grades_data = [round(c['avg_grade'], 1) for c in class_grades if c['class_name']]
    
    # 9. Évolution du score de risque moyen (par date de création)
    from django.db.models.functions import TruncDate
    daily_trend = (
        risks
        .annotate(date=TruncDate('created_at'))
        .values('date')
        .annotate(avg_score=Avg('risk_score'))
        .order_by('date')
    )
    
    daily_labels = [d['date'].strftime('%d/%m') if d['date'] else '' for d in daily_trend]
    daily_data = [round(d['avg_score'], 1) for d in daily_trend]
    
    # 10. Interventions récentes
    recent_interventions = (
        Intervention.objects
        .select_related('alert__risk_score', 'ai_suggestion')
        .order_by('-created_at')[:5]
    )
    
    context = {
        # Variables pour le template
        'total_students': total_students,
        'high_risk_count': high_risk_count,
        'medium_risk_count': medium_risk_count,
        'low_risk_count': low_risk_count,
        'top_risks': top_risks,
        'alerts': alerts,
        'class_stats': list(class_stats),
        'has_data': has_data,
        # Variables pour les graphiques
        'risk_distribution_labels': risk_distribution_labels,
        'risk_distribution_data': risk_distribution_data,
        'class_avg_labels': class_avg_labels,
        'class_avg_data': class_avg_data,
        'histogram_labels': histogram_labels,
        'histogram_data': histogram_data,
        'top10_labels': top10_labels,
        'top10_data': top10_data,
        'scatter_absences': scatter_absences,
        'scatter_grades': scatter_grades,
        'class_count_labels': class_count_labels,
        'class_count_data': class_count_data,
        'class_grades_labels': class_grades_labels,
        'class_grades_data': class_grades_data,
        'correlation_labels': ['Absences', 'Notes', 'Comportement'],
        'correlation_data': [0.6, -0.7, 0.4],
        # NOUVELLES VARIABLES
        'daily_labels': daily_labels,
        'daily_data': daily_data,
        'recent_interventions': recent_interventions,
    }
    
    return render(request, 'dashboard/teacher.html', context)
# ========== VUE 3 — LISTE DES ALERTES ==========

@login_required
def alerts_list(request):
    """Liste paginée des alertes avec filtres"""
    qs = (
        Alert.objects
        .select_related('risk_score', 'ai_suggestion')
        .order_by('-created_at')
    )

    status_filter = request.GET.get('status', '')
    risk_level_filter = request.GET.get('risk_level', '')
    class_filter = request.GET.get('class_name', '')

    if status_filter:
        qs = qs.filter(status=status_filter)
    if risk_level_filter:
        qs = qs.filter(risk_score__risk_level=risk_level_filter)
    if class_filter:
        qs = qs.filter(risk_score__class_name__icontains=class_filter)

    paginator = Paginator(qs, 20)
    page = request.GET.get('page')
    alerts = paginator.get_page(page)

    classes = (
        RiskScore.objects
        .values_list('class_name', flat=True)
        .distinct()
        .order_by('class_name')
    )

    context = {
        'alerts': alerts,
        'status_filter': status_filter,
        'risk_level_filter': risk_level_filter,
        'class_filter': class_filter,
        'classes': classes,
    }
    return render(request, 'early_warning/alerts_list.html', context)


# ========== VUE 4 — DÉTAIL D'UNE ALERTE ==========

@login_required
def alert_detail(request, alert_id):
    """Détail d'une alerte avec suggestion IA"""
    alert = get_object_or_404(
        Alert.objects.select_related('risk_score', 'ai_suggestion'),
        id=alert_id,
    )
    
    interventions = alert.interventions.select_related('ai_suggestion').order_by('-created_at')

    context = {
        'alert': alert,
        'alert_id': alert_id,
        'interventions': interventions,
    }
    return render(request, 'early_warning/alert_detail.html', context)


# ========== VUE 5 — CRÉER UNE INTERVENTION ==========

@login_required
def intervention_create(request, alert_id):
    """Créer une intervention pour une alerte donnée"""
    alert = get_object_or_404(Alert, id=alert_id)

    if request.method == 'POST':
        form = InterventionForm(request.POST)
        if form.is_valid():
            intervention = form.save(commit=False)
            intervention.alert = alert
            intervention.ai_suggestion = alert.ai_suggestion
            intervention.save()

            alert.status = 'in_progress'
            alert.save()
            
            messages.success(request, "Intervention créée avec succès !")
            return redirect('early_warning:intervention_detail', pk=intervention.pk)
    else:
        initial = {}
        if alert.ai_suggestion:
            initial = {
                'action_type': alert.ai_suggestion.suggested_action,
                'description': alert.ai_suggestion.description,
            }
        form = InterventionForm(initial=initial, ai_suggestion=alert.ai_suggestion)

    return render(
        request,
        'early_warning/intervention_form.html',
        {'form': form, 'alert': alert}
    )


# ========== VUE 6 — DÉTAIL D'UNE INTERVENTION ==========

@login_required
def intervention_detail(request, pk):
    """Détail et mise à jour du statut d'une intervention"""
    intervention = get_object_or_404(
        Intervention.objects.select_related(
            'alert__risk_score', 'ai_suggestion'
        ),
        pk=pk,
    )

    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = dict(Intervention.STATUS_CHOICES).keys()

        if new_status in valid_statuses:
            intervention.status = new_status
            if request.POST.get('notes'):
                intervention.notes = request.POST.get('notes')
            intervention.save()

            if new_status == 'completed':
                intervention.alert.status = 'resolved'
                intervention.alert.save()
            
            messages.success(request, f"Statut mis à jour : {intervention.get_status_display()}")
            return redirect('early_warning:intervention_detail', pk=pk)

    return render(
        request,
        'early_warning/intervention_detail.html',
        {'intervention': intervention}
    )


# ========== VUE 7 — CONFIGURATION DES SEUILS ==========

@login_required
@role_required('teacher', 'admin')
def threshold_config(request):
    """Configuration des seuils d'alerte."""
    config = ThresholdConfig.get_config()

    if request.method == 'POST':
        form = ThresholdConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "Configuration mise à jour avec succès !")
            return redirect('early_warning:threshold_config')
    else:
        form = ThresholdConfigForm(instance=config)

    return render(
        request,
        'early_warning/threshold_config.html',
        {'form': form, 'config': config}
    )


# ========== VUE 8 — EXPORT CSV ==========

@login_required
def export_risk_report_csv(request):
    """Export CSV des scores de risque"""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        'attachment; filename="rapport_risques_{}.csv"'.format(
            datetime.now().strftime('%Y%m%d_%H%M%S')
        )
    )
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Nom Eleve', 'ID Eleve', 'Classe',
        'Absences (%)', 'Moyenne (/20)', 'Comportement (/10)',
        'Score Risque (/100)', 'Niveau', 'Date Creation',
    ])

    for s in RiskScore.objects.order_by('-risk_score'):
        writer.writerow([
            s.id,
            s.student_name,
            s.student_id,
            s.class_name,
            s.absences,
            f"{s.avg_grade:.1f}",
            s.behavior_score,
            f"{s.risk_score:.1f}",
            s.get_risk_level_display(),
            s.created_at.strftime('%Y-%m-%d %H:%M'),
        ])
    
    return response


# ========== VUE 9 — EXPORT PDF ==========

@login_required
def export_risk_report_pdf(request):
    """Export PDF avec ReportLab"""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer,
                                        Table, TableStyle)
    except ImportError:
        messages.error(request, "ReportLab n'est pas installé.")
        return redirect('early_warning:dashboard')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        'attachment; filename="rapport_risques_{}.pdf"'.format(
            datetime.now().strftime('%Y%m%d_%H%M%S')
        )
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        rightMargin=30, leftMargin=30,
        topMargin=50, bottomMargin=30,
    )

    styles = getSampleStyleSheet()
    title_sty = ParagraphStyle(
        'Title3alemni',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#8B0000'),
        spaceAfter=20,
        alignment=1,
    )

    elements = []
    risk_scores = RiskScore.objects.order_by('-risk_score')

    elements.append(Paragraph("Rapport d'Evaluation des Risques — 3alemni", title_sty))
    elements.append(Spacer(1, 0.15 * inch))
    elements.append(
        Paragraph(
            f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
            styles['Normal']
        )
    )
    elements.append(Spacer(1, 0.25 * inch))

    stats = risk_scores.aggregate(
        total=Count('id'),
        high=Count('id', filter=Q(risk_level='high')),
        medium=Count('id', filter=Q(risk_level='medium')),
        low=Count('id', filter=Q(risk_level='low')),
    )
    stats_data = [
        ['Statistique', 'Valeur'],
        ['Total étudiants', str(stats['total'])],
        ['Risque élevé', str(stats['high'])],
        ['Risque moyen', str(stats['medium'])],
        ['Risque faible', str(stats['low'])],
    ]
    st = Table(stats_data, colWidths=[2.5 * inch, 2.5 * inch])
    st.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8B0000')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(st)
    elements.append(Spacer(1, 0.25 * inch))

    if stats['total'] > 0:
        elements.append(Paragraph("Détail des Etudiants", styles['Heading2']))
        student_data = [['Nom', 'Classe', 'Absences', 'Moyenne', 'Score', 'Niveau']]
        for s in risk_scores[:30]:
            level_map = {'high': 'Elevé', 'medium': 'Moyen', 'low': 'Faible'}
            student_data.append([
                s.student_name[:25],
                s.class_name[:15],
                f"{s.absences}%",
                f"{s.avg_grade:.1f}",
                f"{s.risk_score:.1f}",
                level_map.get(s.risk_level, s.risk_level),
            ])

        tbl = Table(
            student_data,
            colWidths=[1.8*inch, 1.1*inch, 0.8*inch, 0.8*inch, 0.8*inch, 1.0*inch]
        )
        level_colors = {'Elevé': '#8B0000', 'Moyen': '#EF9F27', 'Faible': '#639922'}
        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        for i, row in enumerate(student_data[1:], start=1):
            lvl = row[-1]
            color = level_colors.get(lvl, '#888')
            style_cmds.append(
                ('TEXTCOLOR', (5, i), (5, i), colors.HexColor(color))
            )
            if i % 2 == 0:
                style_cmds.append(
                    ('BACKGROUND', (0, i), (-1, i), colors.HexColor('#FFF5F5'))
                )
        tbl.setStyle(TableStyle(style_cmds))
        elements.append(tbl)

    doc.build(elements)
    
    return response


# ========== VUE 10 — MES INTERVENTIONS ==========

@login_required
def mes_interventions_list(request):
    """Liste de toutes les interventions du professeur"""
    interventions = Intervention.objects.select_related(
        'alert__risk_score', 'ai_suggestion'
    ).order_by('-created_at')
    
    status_filter = request.GET.get('status', '')
    if status_filter:
        interventions = interventions.filter(status=status_filter)
    
    paginator = Paginator(interventions, 10)
    page = request.GET.get('page')
    interventions_page = paginator.get_page(page)
    
    stats = {
        'total': interventions.count(),
        'completed': interventions.filter(status='completed').count(),
        'in_progress': interventions.filter(status='in_progress').count(),
        'planned': interventions.filter(status='planned').count(),
        'overdue': 0,
    }
    
    context = {
        'interventions': interventions_page,
        'stats': stats,
        'status_filter': status_filter,
    }
    return render(request, 'early_warning/mes_interventions.html', context)


# ========== VUE 11 — API JSON ==========

@login_required
def api_risk_data(request):
    """API JSON pour alimenter les graphiques du dashboard"""
    data = {
        'distribution': {
            'high': RiskScore.objects.filter(risk_level='high').count(),
            'medium': RiskScore.objects.filter(risk_level='medium').count(),
            'low': RiskScore.objects.filter(risk_level='low').count(),
        },
        'top_risks': [
            {
                'name': r.student_name,
                'score': round(r.risk_score, 1),
                'level': r.risk_level,
                'class': r.class_name,
            }
            for r in RiskScore.objects.order_by('-risk_score')[:10]
        ],
        'by_class': list(
            RiskScore.objects
            .values('class_name')
            .annotate(
                total=Count('id'),
                high=Count('id', filter=Q(risk_level='high')),
            )
            .order_by('class_name')
        ),
    }
    return JsonResponse(data)