# schedule/apps.py
"""
Shifta Django Application Configuration
スマートフォン対応シフト管理システム
Djangoアプリケーション設定
"""

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class ScheduleConfig(AppConfig):
    """シフト管理アプリケーションの設定クラス"""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'schedule'
    verbose_name = 'シフト管理システム'
    
    def ready(self):
        """アプリケーション準備完了時の処理"""
        # シグナルハンドラーの登録
        from . import signals
        
        # 初期データセットアップのシグナル
        post_migrate.connect(self.create_initial_data, sender=self)
        
        # Celeryタスクの登録（非同期処理用）
        try:
            from .tasks import setup_periodic_tasks
            setup_periodic_tasks()
        except ImportError:
            # Celeryが利用できない場合はスキップ
            pass
    
    def create_initial_data(self, sender, **kwargs):
        """初期データの作成"""
        from django.contrib.auth.models import Group, Permission
        from django.contrib.contenttypes.models import ContentType
        from .models import JobType, HolidayType, WorkStyle
        
        # グループの作成
        admin_group, created = Group.objects.get_or_create(name='管理者')
        staff_group, created = Group.objects.get_or_create(name='スタッフ')
        
        # 権限の設定
        content_types = ContentType.objects.filter(app_label='schedule')
        
        # 管理者権限
        admin_permissions = Permission.objects.filter(
            content_type__in=content_types
        )
        admin_group.permissions.set(admin_permissions)
        
        # スタッフ権限（制限付き）
        staff_permissions = Permission.objects.filter(
            content_type__in=content_types,
            codename__in=[
                'view_shiftrequest',
                'add_shiftrequest',
                'change_shiftrequest',
                'view_shiftassignment',
                'view_staffprofile',
                'change_staffprofile',
            ]
        )
        staff_group.permissions.set(staff_permissions)
        
        # 基本的な勤務タイプの作成
        default_job_types = [
            {
                'name': '通常勤務',
                'description': '通常の勤務時間',
                'start_time': '09:00',
                'end_time': '18:00',
                'break_duration': 60,
                'is_active': True,
                'color': '#007bff',
                'required_staff': 1,
            },
            {
                'name': '早番',
                'description': '早朝勤務',
                'start_time': '06:00',
                'end_time': '15:00',
                'break_duration': 60,
                'is_active': True,
                'color': '#28a745',
                'required_staff': 1,
            },
            {
                'name': '遅番',
                'description': '夜間勤務',
                'start_time': '13:00',
                'end_time': '22:00',
                'break_duration': 60,
                'is_active': True,
                'color': '#ffc107',
                'required_staff': 1,
            },
            {
                'name': '夜勤',
                'description': '深夜勤務',
                'start_time': '22:00',
                'end_time': '06:00',
                'break_duration': 120,
                'is_active': True,
                'color': '#dc3545',
                'required_staff': 1,
            },
        ]
        
        for job_data in default_job_types:
            JobType.objects.get_or_create(
                name=job_data['name'],
                defaults=job_data
            )
        
        # 休日タイプの作成
        default_holiday_types = [
            {
                'name': '有給休暇',
                'description': '年次有給休暇',
                'annual_days': 20,
                'carry_over_limit': 20,
                'is_paid': True,
                'color': '#17a2b8',
                'requires_approval': True,
            },
            {
                'name': '特別休暇',
                'description': '特別な事由による休暇',
                'annual_days': 5,
                'carry_over_limit': 0,
                'is_paid': True,
                'color': '#6f42c1',
                'requires_approval': True,
            },
            {
                'name': '欠勤',
                'description': '無給の欠勤',
                'annual_days': 0,
                'carry_over_limit': 0,
                'is_paid': False,
                'color': '#dc3545',
                'requires_approval': False,
            },
        ]
        
        for holiday_data in default_holiday_types:
            HolidayType.objects.get_or_create(
                name=holiday_data['name'],
                defaults=holiday_data
            )
        
        # 勤務スタイルの作成
        default_work_styles = [
            {
                'name': 'フルタイム',
                'description': '週5日、1日8時間の勤務',
                'weekly_hours': 40,
                'max_consecutive_days': 5,
                'min_rest_hours': 12,
                'is_active': True,
            },
            {
                'name': 'パートタイム',
                'description': '短時間勤務',
                'weekly_hours': 20,
                'max_consecutive_days': 3,
                'min_rest_hours': 12,
                'is_active': True,
            },
            {
                'name': 'シフト制',
                'description': '交代制勤務',
                'weekly_hours': 40,
                'max_consecutive_days': 4,
                'min_rest_hours': 16,
                'is_active': True,
            },
        ]
        
        for style_data in default_work_styles:
            WorkStyle.objects.get_or_create(
                name=style_data['name'],
                defaults=style_data
            )


class ShiftaConfig(ScheduleConfig):
    """
    後方互換性のための別名
    """
    pass
