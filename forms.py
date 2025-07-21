# schedule/forms.py
"""
Shifta Forms
スマートフォン対応シフト管理システム
フォーム定義
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Submit, Row, Column, HTML
from crispy_forms.bootstrap import FormActions
from .models import (
    StaffProfile, ShiftRequest, SchedulePeriod, 
    JobType, HolidayType, WorkStyle
)


class CustomLoginForm(AuthenticationForm):
    """カスタムログインフォーム（スマートフォン最適化）"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'mobile-optimized'
        self.helper.layout = Layout(
            Field('username', placeholder='ユーザー名またはメールアドレス',
                  css_class='form-control-lg mobile-input'),
            Field('password', placeholder='パスワード',
                  css_class='form-control-lg mobile-input'),
            HTML('<div class="form-check mb-3">'
                 '<input class="form-check-input" type="checkbox" id="remember_me">'
                 '<label class="form-check-label" for="remember_me">ログイン状態を保持する</label>'
                 '</div>'),
            Submit('submit', 'ログイン', css_class='btn btn-primary btn-lg w-100 mobile-btn')
        )
        
        # フィールドのカスタマイズ
        self.fields['username'].widget.attrs.update({
            'autocomplete': 'username',
            'inputmode': 'text',
        })
        self.fields['password'].widget.attrs.update({
            'autocomplete': 'current-password',
        })


class StaffProfileForm(forms.ModelForm):
    """スタッフプロフィール設定フォーム"""
    
    class Meta:
        model = StaffProfile
        fields = [
            'phone_number', 'emergency_contact', 'preferred_job_types',
            'work_style', 'max_hours_per_week', 'max_consecutive_days',
            'min_rest_hours', 'available_days', 'preferred_start_time',
            'preferred_end_time', 'notes'
        ]
        widgets = {
            'phone_number': forms.TextInput(attrs={'inputmode': 'tel'}),
            'emergency_contact': forms.TextInput(attrs={'inputmode': 'tel'}),
            'preferred_job_types': forms.CheckboxSelectMultiple(),
            'available_days': forms.CheckboxSelectMultiple(),
            'preferred_start_time': forms.TimeInput(attrs={'type': 'time'}),
            'preferred_end_time': forms.TimeInput(attrs={'type': 'time'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            HTML('<h4 class="mb-3">📱 基本情報</h4>'),
            Row(
                Column('phone_number', css_class='col-md-6'),
                Column('emergency_contact', css_class='col-md-6'),
            ),
            HTML('<h4 class="mb-3 mt-4">⚙️ 勤務設定</h4>'),
            'work_style',
            Row(
                Column('max_hours_per_week', css_class='col-md-4'),
                Column('max_consecutive_days', css_class='col-md-4'),
                Column('min_rest_hours', css_class='col-md-4'),
            ),
            HTML('<h4 class="mb-3 mt-4">🎯 希望条件</h4>'),
            'preferred_job_types',
            'available_days',
            Row(
                Column('preferred_start_time', css_class='col-md-6'),
                Column('preferred_end_time', css_class='col-md-6'),
            ),
            'notes',
            FormActions(
                Submit('submit', '💾 保存', css_class='btn btn-primary btn-lg mobile-btn')
            )
        )


class ShiftRequestForm(forms.ModelForm):
    """シフト希望提出フォーム（スマートフォン最適化）"""
    
    class Meta:
        model = ShiftRequest
        fields = ['date', 'job_type', 'preference_level', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'preference_level': forms.RadioSelect(),
            'notes': forms.TextInput(attrs={'placeholder': '特記事項があれば入力'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.period = kwargs.pop('period', None)
        super().__init__(*args, **kwargs)
        
        if self.period:
            # 対象期間の日付のみ選択可能にする
            self.fields['date'].widget.attrs.update({
                'min': self.period.start_date.strftime('%Y-%m-%d'),
                'max': self.period.end_date.strftime('%Y-%m-%d'),
            })
        
        # 希望度の選択肢をカスタマイズ
        self.fields['preference_level'].choices = [
            (5, '🔥 絶対に働きたい'),
            (4, '😊 できれば働きたい'),
            (3, '😐 どちらでも良い'),
            (2, '😔 あまり働きたくない'),
            (1, '❌ 働けない'),
        ]
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'mobile-shift-form'
        self.helper.layout = Layout(
            Field('date', css_class='form-control-lg mobile-input'),
            Field('job_type', css_class='form-select-lg'),
            HTML('<div class="preference-selector mb-3">'),
            Field('preference_level', css_class='preference-radio'),
            HTML('</div>'),
            Field('notes', css_class='form-control mobile-input'),
            Submit('submit', '📝 希望を提出', css_class='btn btn-primary btn-lg w-100 mobile-btn')
        )


class BulkShiftRequestForm(forms.Form):
    """一括シフト希望提出フォーム"""
    
    period = forms.ModelChoiceField(
        queryset=SchedulePeriod.objects.filter(is_active=True),
        label='対象期間',
        widget=forms.Select(attrs={'class': 'form-select-lg'})
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # 未来の期間のみ選択可能
        self.fields['period'].queryset = SchedulePeriod.objects.filter(
            is_active=True,
            request_deadline__gte=timezone.now().date()
        )
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_id = 'bulk-request-form'
        self.helper.layout = Layout(
            Field('period', css_class='form-select-lg'),
            HTML('<div id="bulk-request-grid" class="mt-4"></div>'),
            Submit('submit', '💾 一括保存', css_class='btn btn-success btn-lg w-100 mobile-btn mt-4')
        )


class AdminScheduleForm(forms.Form):
    """管理者用スケジュール作成フォーム"""
    
    period = forms.ModelChoiceField(
        queryset=SchedulePeriod.objects.filter(is_active=True),
        label='対象期間'
    )
    
    optimization_method = forms.ChoiceField(
        choices=[
            ('balanced', 'バランス重視'),
            ('preference', '希望重視'),
            ('efficiency', '効率重視'),
            ('fairness', '公平性重視'),
        ],
        label='最適化方法',
        initial='balanced'
    )
    
    consider_consecutive_days = forms.BooleanField(
        label='連続勤務日数を考慮',
        initial=True,
        required=False
    )
    
    balance_workload = forms.BooleanField(
        label='勤務負荷を均等化',
        initial=True,
        required=False
    )
    
    respect_rest_time = forms.BooleanField(
        label='休憩時間を厳守',
        initial=True,
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'period',
            'optimization_method',
            HTML('<div class="card mt-3"><div class="card-header">詳細設定</div><div class="card-body">'),
            'consider_consecutive_days',
            'balance_workload',
            'respect_rest_time',
            HTML('</div></div>'),
            FormActions(
                Submit('preview', '🔍 プレビュー', css_class='btn btn-outline-primary'),
                Submit('execute', '🤖 AI最適化実行', css_class='btn btn-primary'),
            )
        )


class HolidayRequestForm(forms.Form):
    """休暇申請フォーム"""
    
    holiday_type = forms.ModelChoiceField(
        queryset=HolidayType.objects.filter(is_active=True),
        label='休暇種別'
    )
    
    start_date = forms.DateField(
        label='開始日',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    end_date = forms.DateField(
        label='終了日',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    reason = forms.CharField(
        label='理由',
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'holiday_type',
            Row(
                Column('start_date', css_class='col-md-6'),
                Column('end_date', css_class='col-md-6'),
            ),
            'reason',
            Submit('submit', '📋 申請', css_class='btn btn-warning btn-lg mobile-btn')
        )
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError('終了日は開始日以降の日付を選択してください。')
            
            # 過去の日付チェック
            if start_date < timezone.now().date():
                raise ValidationError('過去の日付は選択できません。')
        
        return cleaned_data


class FeedbackForm(forms.Form):
    """フィードバック・要望フォーム"""
    
    CATEGORY_CHOICES = [
        ('bug', '🐛 バグ報告'),
        ('feature', '💡 機能要望'),
        ('improvement', '📈 改善提案'),
        ('question', '❓ 質問'),
        ('other', '🗨️ その他'),
    ]
    
    category = forms.ChoiceField(
        choices=CATEGORY_CHOICES,
        label='カテゴリー'
    )
    
    subject = forms.CharField(
        label='件名',
        max_length=100
    )
    
    message = forms.CharField(
        label='内容',
        widget=forms.Textarea(attrs={'rows': 5})
    )
    
    priority = forms.ChoiceField(
        choices=[
            ('low', '低'),
            ('medium', '中'),
            ('high', '高'),
            ('urgent', '緊急'),
        ],
        label='優先度',
        initial='medium'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('category', css_class='col-md-6'),
                Column('priority', css_class='col-md-6'),
            ),
            'subject',
            'message',
            Submit('submit', '📤 送信', css_class='btn btn-info btn-lg mobile-btn')
        )
