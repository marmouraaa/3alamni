from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, StudentProfile, TeacherProfile, CounselorProfile, ParentProfile

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    
    fieldsets = UserAdmin.fieldsets + (
        ('Informations 3alemni', {'fields': ('role', 'date_of_birth', 'phone', 'profile_picture', 'bio', 'linked_student')}),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Informations 3alemni', {'fields': ('role', 'date_of_birth', 'phone')}),
    )

class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'school_name', 'anonymous_id')
    list_filter = ('level',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'anonymous_id')
    readonly_fields = ('anonymous_id', 'total_study_hours', 'current_streak')

class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'school', 'years_of_experience')
    list_filter = ('subject',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name')

class CounselorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'speciality', 'license_number', 'available_for_chat')
    list_filter = ('speciality', 'available_for_chat')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')

class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_children')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    
    def get_children(self, obj):
        return ", ".join([str(child) for child in obj.children.all()])
    get_children.short_description = "Enfants"

admin.site.register(User, CustomUserAdmin)
admin.site.register(StudentProfile, StudentProfileAdmin)
admin.site.register(TeacherProfile, TeacherProfileAdmin)
admin.site.register(CounselorProfile, CounselorProfileAdmin)
admin.site.register(ParentProfile, ParentProfileAdmin)