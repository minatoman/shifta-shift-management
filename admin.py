# schedule/admin.py
"""
Shifta Admin
スマートフォン対応シフト管理システム
Django管理画面カスタマイズ
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Avg
from .models import (
    StaffProfile, JobType, WorkStyle, HolidayType, SchedulePeriod,
    ShiftRequest, ShiftAssignment, HolidayBalance, NotificationLog
)


class StaffProfileInline(admin.StackedInline):
    """ユーザーモデルにスタッフプロフィールを統合"""
    model = StaffProfile
    can_delete = False
    verbose_name_plural = 'スタッフプロフィール'
    
    fieldsets = (
        ('基本情報', {
            'fields': ('phone_number', 'emergency_contact', 'hire_date')
        }),
        ('勤務設定', {
            'fields': (
                'work_style', 'max_hours_per_week', 'max_consecutive_days',
                'min_rest_hours', 'hourly_rate'
            )
        }),
        ('希望条件', {
            'fields': (
                'preferred_job_types', 'available_days',
                'preferred_start_time', 'preferred_end_time'
            )
        }),
        ('その他', {
            'fields': ('notes', 'is_active'),
            'classes': ('collapse',)
        })
    )


class CustomUserAdmin(UserAdmin):
    """カスタムユーザー管理"""
    inlines = (StaffProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 
                    'is_staff', 'is_active', 'get_profile_status')
    list_filter = ('is_staff', 'is_active', 'date_joined', 
                   'staffprofile__work_style', 'staffprofile__is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    
    def get_profile_status(self, obj):
        try:
            profile = obj.staffprofile
            if profile.is_active:
                return format_html('<span style="color: green;">✓ 有効</span>')
            else:
                return format_html('<span style="color: red;">✗ 無効</span>')
        except StaffProfile.DoesNotExist:
            return format_html('<span style="color: orange;">⚠ 未設定</span>')
    
    get_profile_status.short_description = 'プロフィール状態'


@admin.register(JobType)
class JobTypeAdmin(admin.ModelAdmin):
    """勤務タイプ管理"""
    list_display = ('name', 'start_time', 'end_time', 'required_staff',
                    'get_colored_badge', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    ordering = ('start_time',)
    
    fieldsets = (
        ('基本情報', {
            'fields': ('name', 'description', 'color', 'is_active')
        }),
        ('時間設定', {
            'fields': ('start_time', 'end_time', 'break_duration')
        }),
        ('人員設定', {
            'fields': ('required_staff', 'max_staff')
        }),
        ('給与設定', {
            'fields': ('base_hourly_rate', 'overtime_multiplier'),
            'classes': ('collapse',)
        })
    )
    
    def get_colored_badge(self, obj):
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 12px;">{}</span>',
            obj.color, obj.name
        )
    get_colored_badge.short_description = '表示'


@admin.register(WorkStyle)
class WorkStyleAdmin(admin.ModelAdmin):
    """勤務スタイル管理"""
    list_display = ('name', 'weekly_hours', 'max_consecutive_days',
                    'min_rest_hours', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')


@admin.register(HolidayType)
class HolidayTypeAdmin(admin.ModelAdmin):
    """休日タイプ管理"""
    list_display = ('name', 'annual_days', 'carry_over_limit',
                    'is_paid', 'requires_approval', 'get_colored_badge')
    list_filter = ('is_paid', 'requires_approval', 'is_active')
    search_fields = ('name', 'description')
    
    def get_colored_badge(self, obj):
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 12px;">{}</span>',
            obj.color, obj.name
        )
    get_colored_badge.short_description = '表示'


@admin.register(SchedulePeriod)
class SchedulePeriodAdmin(admin.ModelAdmin):
    """スケジュール期間管理"""
    list_display = ('name', 'start_date', 'end_date', 'request_deadline',
                    'get_status_badge', 'get_optimization_status', 'created_at')
    list_filter = ('is_active', 'optimization_status', 'created_at')
    search_fields = ('name', 'description')
    date_hierarchy = 'start_date'
    ordering = ('-start_date',)
    
    fieldsets = (
        ('基本情報', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('期間設定', {
            'fields': ('start_date', 'end_date', 'request_deadline')
        }),
        ('最適化', {
            'fields': ('optimization_status', 'optimization_score',
                      'optimization_completed_at', 'optimization_error'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('optimization_completed_at', 'optimization_error', 'created_at')
    
    def get_status_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">✓ 有効</span>')
        else:
            return format_html('<span style="color: red;">✗ 無効</span>')
    get_status_badge.short_description = '状態'
    
    def get_optimization_status(self, obj):
        status_colors = {
            'pending': 'orange',
            'running': 'blue',
            'completed': 'green',
            'failed': 'red',
        }
        color = status_colors.get(obj.optimization_status, 'gray')
        return format_html(
            '<span style="color: {};">● {}</span>',
            color, obj.get_optimization_status_display()
        )
    get_optimization_status.short_description = '最適化状態'


@admin.register(ShiftRequest)
class ShiftRequestAdmin(admin.ModelAdmin):
    """シフト希望管理"""
    list_display = ('get_user_name', 'date', 'job_type', 'get_preference_badge',
                    'period', 'created_at')
    list_filter = ('preference_level', 'job_type', 'period', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    date_hierarchy = 'date'
    ordering = ('-created_at',)
    
    def get_user_name(self, obj):
        return f"{obj.user.last_name} {obj.user.first_name}"
    get_user_name.short_description = 'スタッフ'
    
    def get_preference_badge(self, obj):
        preference_colors = {
            5: '#dc3545',  # 赤
            4: '#fd7e14',  # オレンジ
            3: '#ffc107',  # 黄色
            2: '#6c757d',  # グレー
            1: '#343a40',  # 黒
        }
        preference_texts = {
            5: '絶対',
            4: '希望',
            3: '普通',
            2: '微妙',
            1: '不可',
        }
        color = preference_colors.get(obj.preference_level, '#6c757d')
        text = preference_texts.get(obj.preference_level, '不明')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 12px;">{}</span>',
            color, text
        )
    get_preference_badge.short_description = '希望度'


@admin.register(ShiftAssignment)
class ShiftAssignmentAdmin(admin.ModelAdmin):
    """シフト割り当て管理"""
    list_display = ('get_user_name', 'date', 'job_type', 'start_time',
                    'end_time', 'get_duration', 'created_at')
    list_filter = ('job_type', 'date', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    date_hierarchy = 'date'
    ordering = ('-date', 'start_time')
    
    def get_user_name(self, obj):
        return f"{obj.user.last_name} {obj.user.first_name}"
    get_user_name.short_description = 'スタッフ'
    
    def get_duration(self, obj):
        if obj.start_time and obj.end_time:
            # 勤務時間を計算
            from datetime import datetime, timedelta
            start = datetime.combine(obj.date, obj.start_time)
            end = datetime.combine(obj.date, obj.end_time)
            
            # 終了時刻が開始時刻より早い場合（日をまたぐ場合）
            if end < start:
                end += timedelta(days=1)
            
            duration = end - start
            hours = duration.total_seconds() / 3600
            return f"{hours:.1f}時間"
        return "-"
    get_duration.short_description = '勤務時間'


@admin.register(HolidayBalance)
class HolidayBalanceAdmin(admin.ModelAdmin):
    """休暇残数管理"""
    list_display = ('get_user_name', 'holiday_type', 'total_days',
                    'used_days', 'get_remaining_days', 'year')
    list_filter = ('holiday_type', 'year')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    ordering = ('year', 'user__username')
    
    def get_user_name(self, obj):
        return f"{obj.user.last_name} {obj.user.first_name}"
    get_user_name.short_description = 'スタッフ'
    
    def get_remaining_days(self, obj):
        remaining = obj.total_days - obj.used_days
        if remaining > 0:
            return format_html('<span style="color: green;">{} 日</span>', remaining)
        elif remaining == 0:
            return format_html('<span style="color: orange;">0 日</span>')
        else:
            return format_html('<span style="color: red;">{} 日</span>', remaining)
    get_remaining_days.short_description = '残日数'


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    """通知ログ管理"""
    list_display = ('get_user_name', 'notification_type', 'title',
                    'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('user__username', 'title', 'content')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)
    
    def get_user_name(self, obj):
        if obj.user:
            return f"{obj.user.last_name} {obj.user.first_name}"
        return "全体通知"
    get_user_name.short_description = '宛先'


# ユーザーモデルを再登録
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# 管理画面のタイトルカスタマイズ
admin.site.site_header = 'Shifta 管理画面'
admin.site.site_title = 'Shifta Admin'
admin.site.index_title = 'シフト管理システム ダッシュボード'
