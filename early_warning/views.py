# early_warning/views.py

import csv
import logging
import json
from datetime import datetime
import pandas as pd
import numpy as np
from django.db.models import Count, Q
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from .models import RiskScore, Alert, Intervention, ThresholdConfig
from .forms import ImportCSVForm, InterventionForm, ThresholdConfigForm
from .services import RiskScoringService, TransformersAIService

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    """Dashboard avec graphiques générés par pandas et Chart.js"""
    
    # ========== DONNÉES DE BASE ==========
    total_students = RiskScore.objects.count()
    high_risk_count = RiskScore.objects.filter(risk_level='high').count()
    medium_risk_count = RiskScore.objects.filter(risk_level='medium').count()
    low_risk_count = RiskScore.objects.filter(risk_level='low').count()
    active_alerts = Alert.objects.filter(status='pending').count()
    
    # Interventions
    interventions = Intervention.objects.select_related('alert__risk_score').order_by('-created_at')
    interventions_stats = {
        'total': interventions.count(),
        'completed': interventions.filter(status='completed').count(),
        'in_progress': interventions.filter(status='in_progress').count(),
        'planned': interventions.filter(status='planned').count(),
    }
    if interventions_stats['total'] > 0:
        interventions_stats['completion_rate'] = int(
            (interventions_stats['completed'] / interventions_stats['total']) * 100
        )
    else:
        interventions_stats['completion_rate'] = 0
    
    recent_interventions = interventions[:5]
    alerts = Alert.objects.select_related('risk_score', 'ai_suggestion').exclude(
        status='resolved'
    ).order_by('-created_at')[:10]
    
    has_data = total_students > 0
    
    # ========== ANALYSES AVEC PANDAS POUR LES GRAPHIQUES ==========
    # Initialisation par défaut
    risk_distribution_labels = ['Risque Élevé', 'Risque Moyen', 'Risque Faible']
    risk_distribution_data = [0, 0, 0]
    class_avg_labels = []
    class_avg_data = []
    histogram_labels = ['0-20', '20-40', '40-60', '60-80', '80-100']
    histogram_data = [0, 0, 0, 0, 0]
    daily_labels = []
    daily_data = []
    correlation_labels = ['Absences', 'Notes', 'Comportement']
    correlation_data = [0, 0, 0]
    top10_labels = []
    top10_data = []
    top10_classes = []
    scatter_absences = []
    scatter_grades = []
    class_count_labels = []
    class_count_data = []
    class_grades_labels = []
    class_grades_data = []
    
    if has_data:
        try:
            # Récupérer toutes les données
            risk_data = list(RiskScore.objects.all().values(
                'student_name', 'class_name', 'risk_level', 'risk_score',
                'absences', 'avg_grade', 'behavior_score', 'created_at'
            ))
            
            # Convertir en DataFrame pandas
            df = pd.DataFrame(risk_data)
            
            # Graphique 1: Distribution des niveaux de risque
            risk_distribution = df['risk_level'].value_counts().to_dict()
            risk_distribution_data = [
                int(risk_distribution.get('high', 0)),
                int(risk_distribution.get('medium', 0)),
                int(risk_distribution.get('low', 0))
            ]
            
            # Graphique 2: Score moyen par classe
            if len(df) > 0:
                class_avg = df.groupby('class_name')['risk_score'].mean().sort_values(ascending=False).head(10)
                class_avg_labels = [str(x) for x in class_avg.index.tolist()]
                class_avg_data = [float(round(x, 1)) for x in class_avg.values.tolist()]
            
            # Graphique 3: Distribution des scores
            if len(df) > 0:
                df['risk_bin'] = pd.cut(df['risk_score'], bins=[0, 20, 40, 60, 80, 100], 
                                        labels=histogram_labels, right=False)
                hist_counts = df['risk_bin'].value_counts().sort_index()
                histogram_data = [int(hist_counts.get(label, 0)) for label in histogram_labels]
            
            # Graphique 4: Évolution temporelle
            if len(df) > 0:
                df['date'] = pd.to_datetime(df['created_at']).dt.date
                daily_avg = df.groupby('date')['risk_score'].mean().tail(30)
                daily_labels = [d.strftime('%d/%m') for d in daily_avg.index]
                daily_data = [float(round(x, 1)) for x in daily_avg.values.tolist()]
            
            # Graphique 5: Corrélations
            if len(df) > 1:
                correlation_data = [
                    float(round(df['absences'].corr(df['risk_score']), 2)),
                    float(round(df['avg_grade'].corr(df['risk_score']), 2)),
                    float(round(df['behavior_score'].corr(df['risk_score']), 2))
                ]
            
            # Graphique 6: Top 10 risques
            if len(df) > 0:
                top10 = df.nlargest(10, 'risk_score')[['student_name', 'risk_score', 'class_name']]
                top10_labels = [str(row['student_name']) for _, row in top10.iterrows()]
                top10_data = [float(round(row['risk_score'], 1)) for _, row in top10.iterrows()]
                top10_classes = [str(row['class_name']) for _, row in top10.iterrows()]
            
            # Graphique 7 & 8: Scatter plots
            if len(df) > 0:
                scatter_absences = [{'x': float(row['absences']), 'y': float(row['risk_score'])} for _, row in df.iterrows()]
                scatter_grades = [{'x': float(row['avg_grade']), 'y': float(row['risk_score'])} for _, row in df.iterrows()]
            
            # Graphique 9: Nombre d'étudiants par classe
            if len(df) > 0:
                class_count = df['class_name'].value_counts().head(10)
                class_count_labels = [str(x) for x in class_count.index.tolist()]
                class_count_data = [int(x) for x in class_count.values.tolist()]
            
            # Graphique 10: Moyenne des notes par classe
            if len(df) > 0:
                class_grades = df.groupby('class_name')['avg_grade'].mean().sort_values(ascending=False).head(10)
                class_grades_labels = [str(x) for x in class_grades.index.tolist()]
                class_grades_data = [float(round(x, 1)) for x in class_grades.values.tolist()]
                
        except Exception as e:
            logger.error(f"Erreur pandas: {e}")
    
    context = {
        'total_students': total_students,
        'high_risk_count': high_risk_count,
        'medium_risk_count': medium_risk_count,
        'low_risk_count': low_risk_count,
        'active_alerts': active_alerts,
        'has_data': has_data,
        'user': request.user,
        'interventions_stats': interventions_stats,
        'recent_interventions': recent_interventions,
        'total_interventions': interventions_stats['total'],
        'alerts': alerts,
        # Données pour les graphiques
        'risk_distribution_labels': risk_distribution_labels,
        'risk_distribution_data': risk_distribution_data,
        'class_avg_labels': class_avg_labels,
        'class_avg_data': class_avg_data,
        'histogram_labels': histogram_labels,
        'histogram_data': histogram_data,
        'daily_labels': daily_labels,
        'daily_data': daily_data,
        'correlation_labels': correlation_labels,
        'correlation_data': correlation_data,
        'top10_labels': top10_labels,
        'top10_data': top10_data,
        'top10_classes': top10_classes,
        'scatter_absences': scatter_absences,
        'scatter_grades': scatter_grades,
        'class_count_labels': class_count_labels,
        'class_count_data': class_count_data,
        'class_grades_labels': class_grades_labels,
        'class_grades_data': class_grades_data,
    }
    
    return render(request, 'dashboard/teacher.html', context)


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
        'overdue': sum(1 for i in interventions if i.is_overdue()),
    }
    
    context = {
        'interventions': interventions_page,
        'stats': stats,
        'status_filter': status_filter,
    }
    return render(request, 'early_warning/mes_interventions.html', context)
# ══════════════════════════════════════════════════════════════════════════════
#  VUE 1 — IMPORT CSV
# ══════════════════════════════════════════════════════════════════════════════
@login_required
def import_csv(request):
    """
    Import des données étudiants depuis un fichier CSV.
    """
    if request.method == 'POST':
        form = ImportCSVForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']

            try:
                df = pd.read_csv(csv_file)

                # Vérification des colonnes requises
                required = [
                    'student_name', 'student_id', 'class_name',
                    'absences', 'avg_grade', 'behavior_score',
                ]
                missing = [col for col in required if col not in df.columns]
                if missing:
                    error_msg = (
                        f"CSV malformé — colonnes manquantes: "
                        f"{', '.join(missing)}. "
                        f"Colonnes trouvées: {', '.join(df.columns.tolist())}"
                    )
                    messages.error(request, error_msg)
                    return render(
                        request,
                        'early_warning/import_csv.html',
                        {'form': form, 'error': error_msg}
                    )

                # Validation des données
                errors = []
                for idx, row in df.iterrows():
                    try:
                        absences = float(row['absences'])
                        avg = float(row['avg_grade'])
                        behavior = float(row['behavior_score'])

                        if not (0 <= absences <= 100):
                            errors.append(
                                f"Ligne {idx+2}: absences={absences} hors intervalle [0-100]"
                            )
                        if not (0 <= avg <= 20):
                            errors.append(
                                f"Ligne {idx+2}: avg_grade={avg} hors intervalle [0-20]"
                            )
                        if not (0 <= behavior <= 10):
                            errors.append(
                                f"Ligne {idx+2}: behavior_score={behavior} hors [0-10]"
                            )
                    except (ValueError, TypeError) as e:
                        errors.append(
                            f"Ligne {idx+2}: valeur numérique invalide — {e}"
                        )

                if errors:
                    error_msg = f"Données invalides ({len(errors)} erreur(s)): " + \
                                " | ".join(errors[:5])
                    messages.error(request, error_msg)
                    return render(
                        request,
                        'early_warning/import_csv.html',
                        {'form': form, 'errors': errors}
                    )

                # Traitement nominal
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
                                message=(
                                    f"Alerte auto — {risk_obj.student_name} — "
                                    f"Score: {risk_obj.risk_score:.1f}/100"
                                ),
                                status='pending',
                            )
                            ai_sugg = ai_service.get_ai_suggestion(risk_obj)
                            alert.ai_suggestion = ai_sugg
                            alert.save()
                            alerts_created += 1

                    except Exception as e:
                        errors_rows.append(f"Ligne {idx+2}: {e}")
                        logger.error(f"[ImportCSV] Erreur ligne {idx+2}: {e}")

                msg = (
                    f"Import terminé ! {students_processed} étudiants traités, "
                    f"{alerts_created} alertes générées."
                )
                if errors_rows:
                    msg += f" ({len(errors_rows)} ligne(s) ignorée(s))"

                messages.success(request, msg)
                return redirect('early_warning:dashboard')

            except Exception as e:
                error_msg = f"Erreur lors de la lecture du CSV: {e}"
                messages.error(request, error_msg)
                return render(
                    request,
                    'early_warning/import_csv.html',
                    {'form': form}
                )
    else:
        form = ImportCSVForm()

    return render(request, 'early_warning/import_csv.html', {'form': form})


# ══════════════════════════════════════════════════════════════════════════════
#  VUE 3 — LISTE DES ALERTES
# ══════════════════════════════════════════════════════════════════════════════
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


# ══════════════════════════════════════════════════════════════════════════════
#  VUE 4 — DÉTAIL D'UNE ALERTE
# ══════════════════════════════════════════════════════════════════════════════
@login_required
def alert_detail(request, alert_id):
    """Détail d'une alerte avec suggestion IA"""
    alert = get_object_or_404(
        Alert.objects.select_related('risk_score', 'ai_suggestion'),
        id=alert_id,
    )

    interventions = alert.interventions.order_by('-created_at')

    context = {
        'alert': alert,
        'alert_id': alert_id,
        'interventions': interventions,
    }
    return render(request, 'early_warning/alert_detail.html', context)


# ══════════════════════════════════════════════════════════════════════════════
#  VUE 5 — CRÉER UNE INTERVENTION
# ══════════════════════════════════════════════════════════════════════════════
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


# ══════════════════════════════════════════════════════════════════════════════
#  VUE 6 — DÉTAIL D'UNE INTERVENTION
# ══════════════════════════════════════════════════════════════════════════════
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


# ══════════════════════════════════════════════════════════════════════════════
#  VUE 7 — CONFIGURATION DES SEUILS
# ══════════════════════════════════════════════════════════════════════════════
@login_required
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


# ══════════════════════════════════════════════════════════════════════════════
#  VUE 8 — EXPORT CSV
# ══════════════════════════════════════════════════════════════════════════════
@login_required
def export_risk_report_csv(request):
    """Export CSV des scores de risque"""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        'attachment; filename="rapport_risques_{}.csv"'.format(
            datetime.now().strftime('%Y%m%d_%H%M%S')
        )
    )
    response.write('\ufeff')  # BOM pour Excel

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


# ══════════════════════════════════════════════════════════════════════════════
#  VUE 9 — EXPORT PDF
# ══════════════════════════════════════════════════════════════════════════════
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
        messages.error(request, "ReportLab n'est pas installé. Veuillez l'installer avec 'pip install reportlab'")
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

    # Tableau stats
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

    # Tableau étudiants
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
    else:
        elements.append(Paragraph("Aucune donnée d'étudiant disponible.", styles['Normal']))

    doc.build(elements)
    return response


# ══════════════════════════════════════════════════════════════════════════════
#  VUE 10 — API JSON (pour les graphiques Chart.js)
# ══════════════════════════════════════════════════════════════════════════════
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
