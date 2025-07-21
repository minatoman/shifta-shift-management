# schedule/urls.py
"""
Shifta URL Configuration
スマートフォン対応シフト管理システムのURL設定
"""

from django.urls import path, include
from django.views.generic import RedirectView
from . import views

app_name = 'schedule'

# スタッフ向けURL（スマートフォン用）
staff_patterns = [
    # マイスケジュール
    path('my-schedule/', views.MyScheduleView.as_view(), name='my_schedule'),
    
    # シフト希望提出
    path('shift-request/', views.ShiftRequestView.as_view(), name='shift_request'),
    
    # 休日残数確認
    path('holiday-balance/', views.HolidayBalanceView.as_view(), name='holiday_balance'),
    
    # プロフィール設定
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/setup/', views.ProfileSetupView.as_view(), name='profile_setup'),
]

# 管理者向けURL（PC用）
admin_patterns = [
    # 管理者ダッシュボード
    path('dashboard/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    
    # シフト調整カレンダー
    path('calendar/', views.AdminCalendarView.as_view(), name='admin_calendar'),
    
    # スタッフ管理
    path('staff/', views.AdminStaffListView.as_view(), name='admin_staff'),
    path('staff/<int:staff_id>/', views.AdminStaffDetailView.as_view(), name='admin_staff_detail'),
    path('staff/<int:staff_id>/edit/', views.AdminStaffEditView.as_view(), name='admin_staff_edit'),
    
    # システム設定
    path('settings/', views.AdminSettingsView.as_view(), name='admin_settings'),
    path('settings/periods/', views.PeriodManagementView.as_view(), name='period_management'),
    path('settings/job-types/', views.JobTypeManagementView.as_view(), name='job_type_management'),
    path('settings/holiday-types/', views.HolidayTypeManagementView.as_view(), name='holiday_type_management'),
    
    # レポート
    path('reports/', views.AdminReportsView.as_view(), name='admin_reports'),
    path('reports/monthly/<int:year>/<int:month>/', views.MonthlyReportView.as_view(), name='monthly_report'),
    
    # データ管理
    path('data/export/', views.ExportDataView.as_view(), name='export_data'),
    path('data/backup/', views.BackupDataView.as_view(), name='backup_data'),
    path('data/import/', views.ImportDataView.as_view(), name='import_data'),
    
    # 通知管理
    path('notifications/send/', views.SendNotificationsView.as_view(), name='send_notifications'),
    path('notifications/history/', views.NotificationHistoryView.as_view(), name='notification_history'),
]

# API エンドポイント
api_patterns = [
    # スケジュール関連
    path('schedule/monthly/', views.ScheduleAPIView.as_view(), name='api_schedule_monthly'),
    path('schedule/daily/<str:date>/', views.DailyScheduleAPIView.as_view(), name='api_schedule_daily'),
    
    # シフト希望関連
    path('requests/<int:period_id>/', views.ShiftRequestAPIView.as_view(), name='api_shift_requests'),
    path('requests/bulk/', views.BulkRequestAPIView.as_view(), name='api_bulk_requests'),
    
    # 管理者用API
    path('admin/stats/<int:period_id>/', views.AdminStatsAPIView.as_view(), name='api_admin_stats'),
    path('admin/ai-status/<int:period_id>/', views.AIStatusAPIView.as_view(), name='api_ai_status'),
    path('admin/assignments/', views.AssignmentAPIView.as_view(), name='api_assignments'),
    
    # データエクスポート
    path('export/excel/<int:period_id>/', views.ExcelExportView.as_view(), name='export_excel'),
    path('export/ical/', views.ICalExportView.as_view(), name='export_ical'),
    path('export/pdf/<int:period_id>/', views.PDFExportView.as_view(), name='export_pdf'),
    
    # システム状態
    path('system/health/', views.SystemHealthView.as_view(), name='system_health'),
    path('system/version/', views.SystemVersionView.as_view(), name='system_version'),
]

# 認証関連
auth_patterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('password-change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('password-reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
]

# 公開ページ
public_patterns = [
    # 公開スケジュール表示（共有用）
    path('public/<int:year>/<int:month>/', views.PublicScheduleView.as_view(), name='public_schedule'),
    
    # ヘルプページ
    path('help/', views.HelpView.as_view(), name='help'),
    path('help/staff/', views.StaffHelpView.as_view(), name='staff_help'),
    path('help/admin/', views.AdminHelpView.as_view(), name='admin_help'),
    
    # 利用規約・プライバシーポリシー
    path('terms/', views.TermsView.as_view(), name='terms'),
    path('privacy/', views.PrivacyView.as_view(), name='privacy'),
]

# メインのURL設定
urlpatterns = [
    # ホームページ（ダッシュボードにリダイレクト）
    path('', views.HomeView.as_view(), name='home'),
    
    # スタッフ向けページ
    path('staff/', include(staff_patterns)),
    
    # 管理者向けページ
    path('admin/', include(admin_patterns)),
    
    # API エンドポイント
    path('api/', include(api_patterns)),
    
    # 認証関連
    path('auth/', include(auth_patterns)),
    
    # 公開ページ
    path('', include(public_patterns)),
    
    # 開発・デバッグ用（本番環境では削除）
    path('debug/', views.DebugView.as_view(), name='debug'),
    path('test/', views.TestView.as_view(), name='test'),
]

# レガシーURL（互換性のため）
legacy_patterns = [
    # 旧URL形式からの自動リダイレクト
    path('schedule/', RedirectView.as_view(pattern_name='schedule:my_schedule', permanent=True)),
    path('request/', RedirectView.as_view(pattern_name='schedule:shift_request', permanent=True)),
    path('admin-dashboard/', RedirectView.as_view(pattern_name='schedule:admin_dashboard', permanent=True)),
]

urlpatterns += legacy_patterns

# エラーハンドリング用のURL（プロジェクトのmain urls.pyで設定）
handler404 = 'schedule.views.handler404'
handler500 = 'schedule.views.handler500'
