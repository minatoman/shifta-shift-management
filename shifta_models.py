# schedule/models.py
"""
Shifta - スマートフォン対応シフト管理システム
データベースモデル定義

このファイルは、Shiftaシステムの全てのデータ構造を定義します。
- ユーザーとスタッフ情報
- 休日管理
- シフト期間と希望提出
- AIによる最終的な割り当て結果
"""

import datetime
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError

# --- 1. ユーザーとスタッフ情報 ---

class User(AbstractUser):
    """
    Django標準のユーザーモデルを拡張。
    管理権限とスタッフ情報を保持。
    """
    class Meta:
        db_table = 'auth_user'
        verbose_name = 'ユーザー'
        verbose_name_plural = 'ユーザー'

    def __str__(self):
        return self.username


class JobType(models.Model):
    """職種 (例: 看護師, 介護士, 事務)"""
    name = models.CharField("職種名", max_length=100, unique=True)
    description = models.TextField("説明", blank=True, null=True)
    color_code = models.CharField(
        "カレンダー色", 
        max_length=7, 
        default="#3788D8",
        help_text="カレンダー表示時の色（#RRGGBB形式）"
    )
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        db_table = 'schedule_job_type'
        verbose_name = '職種'
        verbose_name_plural = '職種'
        ordering = ['name']

    def __str__(self):
        return self.name


class WorkStyle(models.Model):
    """勤務形態 (例: 常勤, 非常勤, 夜勤専従)"""
    name = models.CharField("勤務形態名", max_length=100, unique=True)
    max_shifts_per_month = models.PositiveIntegerField(
        "月間最大勤務日数", 
        default=22,
        validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    min_shifts_per_month = models.PositiveIntegerField(
        "月間最低勤務日数", 
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(31)]
    )
    allow_consecutive_days = models.PositiveIntegerField(
        "最大連続勤務日数", 
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(14)]
    )
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        db_table = 'schedule_work_style'
        verbose_name = '勤務形態'
        verbose_name_plural = '勤務形態'
        ordering = ['name']

    def clean(self):
        if self.min_shifts_per_month > self.max_shifts_per_month:
            raise ValidationError('最低勤務日数は最大勤務日数以下である必要があります。')

    def __str__(self):
        return self.name


class StaffProfile(models.Model):
    """スタッフ個人に紐づく詳細情報"""
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name="profile",
        verbose_name="ユーザー"
    )
    job_type = models.ForeignKey(
        JobType, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name="職種"
    )
    work_style = models.ForeignKey(
        WorkStyle, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name="勤務形態"
    )
    employee_id = models.CharField(
        "社員番号", 
        max_length=50, 
        unique=True, 
        blank=True, 
        null=True
    )
    phone_number = models.CharField(
        "電話番号", 
        max_length=20, 
        blank=True, 
        null=True
    )
    hire_date = models.DateField("入社日", blank=True, null=True)
    is_active = models.BooleanField("有効", default=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        db_table = 'schedule_staff_profile'
        verbose_name = 'スタッフプロフィール'
        verbose_name_plural = 'スタッフプロフィール'
        ordering = ['user__last_name', 'user__first_name']

    def __str__(self):
        name = self.user.get_full_name() or self.user.username
        return f"{name} ({self.job_type.name if self.job_type else '未設定'})"

    @property
    def display_name(self):
        """表示用の名前を返す"""
        return self.user.get_full_name() or self.user.username


# --- 2. 休日と残数管理 ---

class HolidayType(models.Model):
    """休日の種類 (例: 週休, 代休, 有給休暇)"""
    name = models.CharField("休日名", max_length=100, unique=True)
    is_paid_leave = models.BooleanField(
        "有給休暇扱い", 
        default=False,
        help_text="有給休暇として残日数をカウントするか"
    )
    color_code = models.CharField(
        "表示色", 
        max_length=7, 
        default="#FF6B6B",
        help_text="カレンダー表示時の色（#RRGGBB形式）"
    )
    sort_order = models.PositiveIntegerField("表示順", default=0)
    is_active = models.BooleanField("有効", default=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        db_table = 'schedule_holiday_type'
        verbose_name = '休日種別'
        verbose_name_plural = '休日種別'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class HolidayBalance(models.Model):
    """スタッフ個人の休日残数"""
    staff = models.ForeignKey(
        StaffProfile, 
        on_delete=models.CASCADE, 
        related_name="holiday_balances",
        verbose_name="スタッフ"
    )
    holiday_type = models.ForeignKey(
        HolidayType, 
        on_delete=models.CASCADE,
        verbose_name="休日種別"
    )
    balance = models.FloatField(
        "残日数", 
        default=0.0,
        validators=[MinValueValidator(0.0)]
    )
    year = models.PositiveIntegerField(
        "対象年度", 
        default=timezone.now().year
    )
    last_updated = models.DateTimeField("最終更新", auto_now=True)

    class Meta:
        db_table = 'schedule_holiday_balance'
        verbose_name = '休日残数'
        verbose_name_plural = '休日残数'
        unique_together = ('staff', 'holiday_type', 'year')
        ordering = ['staff', 'holiday_type']

    def __str__(self):
        return f"{self.staff.display_name} - {self.holiday_type.name}: {self.balance}日 ({self.year}年度)"


# --- 3. シフト期間と希望提出 ---

class SchedulePeriod(models.Model):
    """シフト作成の対象期間 (例: 2025年8月度)"""
    name = models.CharField("期間名", max_length=100)
    start_date = models.DateField("開始日")
    end_date = models.DateField("終了日")
    request_deadline = models.DateTimeField("希望提出締切日時")
    is_active = models.BooleanField("アクティブ", default=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        db_table = 'schedule_period'
        verbose_name = 'スケジュール期間'
        verbose_name_plural = 'スケジュール期間'
        ordering = ['-start_date']

    def clean(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError('開始日は終了日より前である必要があります。')
        if self.request_deadline and self.start_date and self.request_deadline.date() > self.start_date:
            raise ValidationError('締切日時は開始日より前である必要があります。')

    def __str__(self):
        return self.name

    @property
    def is_request_open(self):
        """希望提出期間中かどうか"""
        return timezone.now() <= self.request_deadline

    @property
    def days_count(self):
        """期間の日数"""
        return (self.end_date - self.start_date).days + 1


class ShiftRequest(models.Model):
    """スタッフからの勤務希望"""
    
    PRIORITY_CHOICES = [
        (1, '休み希望'),
        (2, '勤務可'),
        (3, '勤務最優先'),
    ]
    
    staff = models.ForeignKey(
        StaffProfile, 
        on_delete=models.CASCADE, 
        related_name="requests",
        verbose_name="スタッフ"
    )
    period = models.ForeignKey(
        SchedulePeriod, 
        on_delete=models.CASCADE,
        verbose_name="対象期間"
    )
    date = models.DateField("希望日")
    priority = models.IntegerField(
        "優先度",
        choices=PRIORITY_CHOICES,
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(3)]
    )
    notes = models.CharField("備考", max_length=255, blank=True, null=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        db_table = 'schedule_shift_request'
        verbose_name = 'シフト希望'
        verbose_name_plural = 'シフト希望'
        unique_together = ('staff', 'date')
        ordering = ['date', 'staff']

    def clean(self):
        if self.period and self.date:
            if not (self.period.start_date <= self.date <= self.period.end_date):
                raise ValidationError('希望日は対象期間内である必要があります。')

    def __str__(self):
        priority_label = dict(self.PRIORITY_CHOICES)[self.priority]
        return f"{self.staff.display_name} on {self.date} ({priority_label})"

    @property
    def priority_display(self):
        """優先度の表示名"""
        return dict(self.PRIORITY_CHOICES)[self.priority]


# --- 4. 管理者設定とAIによる割り当て結果 ---

class DailyRequirement(models.Model):
    """日別・職種別の必要人数"""
    period = models.ForeignKey(
        SchedulePeriod, 
        on_delete=models.CASCADE,
        verbose_name="対象期間"
    )
    date = models.DateField("日付")
    job_type = models.ForeignKey(
        JobType, 
        on_delete=models.CASCADE,
        verbose_name="職種"
    )
    required_staff_count = models.PositiveIntegerField(
        "必要人数",
        validators=[MinValueValidator(0)]
    )
    min_staff_count = models.PositiveIntegerField(
        "最低人数",
        validators=[MinValueValidator(0)]
    )
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        db_table = 'schedule_daily_requirement'
        verbose_name = '日別必要人数'
        verbose_name_plural = '日別必要人数'
        unique_together = ('date', 'job_type')
        ordering = ['date', 'job_type']

    def clean(self):
        if self.min_staff_count > self.required_staff_count:
            raise ValidationError('最低人数は必要人数以下である必要があります。')

    def __str__(self):
        return f"{self.date} ({self.job_type.name}): {self.min_staff_count} - {self.required_staff_count}人"


class ShiftAssignment(models.Model):
    """AIによって生成・確定された最終勤務表"""
    staff = models.ForeignKey(
        StaffProfile, 
        on_delete=models.CASCADE, 
        related_name="assignments",
        verbose_name="スタッフ"
    )
    date = models.DateField("勤務日")
    is_workday = models.BooleanField("勤務日か", default=True)
    holiday_type = models.ForeignKey(
        HolidayType, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="休日種別"
    )
    notes = models.CharField("備考", max_length=255, blank=True, null=True)
    created_by_ai = models.BooleanField("AI作成", default=True)
    manually_adjusted = models.BooleanField("手動調整済み", default=False)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        db_table = 'schedule_shift_assignment'
        verbose_name = 'シフト割り当て'
        verbose_name_plural = 'シフト割り当て'
        unique_together = ('staff', 'date')
        ordering = ['date', 'staff']

    def clean(self):
        if not self.is_workday and not self.holiday_type:
            raise ValidationError('休日の場合は休日種別を指定してください。')
        if self.is_workday and self.holiday_type:
            raise ValidationError('勤務日の場合は休日種別を指定できません。')

    def __str__(self):
        if self.is_workday:
            status = "勤務"
        else:
            status = f"休み ({self.holiday_type.name if self.holiday_type else ''})"
        return f"{self.date} - {self.staff.display_name}: {status}"

    @property
    def status_display(self):
        """ステータスの表示名"""
        if self.is_workday:
            return "勤務"
        else:
            return f"休み ({self.holiday_type.name if self.holiday_type else ''})"


# --- 5. システム管理用モデル ---

class ScheduleLog(models.Model):
    """シフト作成ログ"""
    
    ACTION_CHOICES = [
        ('ai_create', 'AI自動作成'),
        ('manual_adjust', '手動調整'),
        ('finalize', '確定'),
        ('notification', '通知送信'),
    ]
    
    period = models.ForeignKey(
        SchedulePeriod, 
        on_delete=models.CASCADE,
        verbose_name="対象期間"
    )
    action = models.CharField("アクション", max_length=20, choices=ACTION_CHOICES)
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name="実行ユーザー"
    )
    description = models.TextField("詳細", blank=True, null=True)
    success = models.BooleanField("成功", default=True)
    execution_time = models.FloatField("実行時間(秒)", null=True, blank=True)
    created_at = models.DateTimeField("実行日時", auto_now_add=True)

    class Meta:
        db_table = 'schedule_log'
        verbose_name = 'スケジュールログ'
        verbose_name_plural = 'スケジュールログ'
        ordering = ['-created_at']

    def __str__(self):
        action_label = dict(self.ACTION_CHOICES)[self.action]
        status = "成功" if self.success else "失敗"
        return f"{self.period.name} - {action_label} ({status})"
