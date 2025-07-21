# schedule/views.py
"""
Shifta - スマートフォン対応シフト管理システム
ビューレイヤー（コントローラー）

機能:
- スタッフ向け画面（希望提出、マイスケジュール確認）
- 管理者向け画面（ダッシュボード、シフト調整）
- API エンドポイント（Ajax通信用）
"""

import json
import logging
from datetime import datetime, timedelta, date
from calendar import monthrange
from typing import Dict, List, Optional

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, View
from django.http import JsonResponse, HttpResponse, Http404
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.conf import settings

from .models import (
    SchedulePeriod, StaffProfile, ShiftRequest, ShiftAssignment,
    DailyRequirement, HolidayBalance, HolidayType, JobType, ScheduleLog
)

logger = logging.getLogger(__name__)

# --- ユーティリティ関数 ---

def is_admin(user):
    """管理者権限チェック"""
    return user.is_authenticated and (user.is_superuser or user.is_staff)

def get_current_staff_profile(user):
    """現在のユーザーのスタッフプロフィールを取得"""
    try:
        return user.profile
    except:
        return None

def generate_date_list(start_date: date, end_date: date) -> List[Dict]:
    """日付リストを生成（曜日情報付き）"""
    date_list = []
    current_date = start_date
    weekday_names = ['日', '月', '火', '水', '木', '金', '土']
    
    while current_date <= end_date:
        date_list.append({
            'date': current_date,
            'weekday': current_date.weekday(),
            'weekday_name': weekday_names[current_date.weekday()],
            'month': current_date.month
        })
        current_date += timedelta(days=1)
    
    return date_list

# --- スタッフ向けビュー ---

class MyScheduleView(LoginRequiredMixin, TemplateView):
    """マイスケジュール表示（スマートフォン用）"""
    template_name = 'schedule/my_schedule.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        staff_profile = get_current_staff_profile(self.request.user)
        if not staff_profile:
            messages.error(self.request, 'スタッフプロフィールが設定されていません。')
            return context
        
        # 表示月の取得（デフォルトは現在月）
        year = int(self.request.GET.get('year', datetime.now().year))
        month = int(self.request.GET.get('month', datetime.now().month))
        current_month = date(year, month, 1)
        
        # 月間のシフト割り当てを取得
        month_start = current_month
        month_end = date(year, month, monthrange(year, month)[1])
        
        assignments = ShiftAssignment.objects.filter(
            staff=staff_profile,
            date__range=(month_start, month_end)
        ).order_by('date')
        
        # 休日残数を取得
        holiday_balances = HolidayBalance.objects.filter(
            staff=staff_profile,
            year=year,
            holiday_type__is_active=True
        ).select_related('holiday_type')
        
        # 月間統計の計算
        work_days = assignments.filter(is_workday=True).count()
        holiday_days = assignments.filter(is_workday=False).count()
        total_days = monthrange(year, month)[1]
        remaining_days = total_days - assignments.count()
        
        context.update({
            'current_month': current_month,
            'assignments': assignments,
            'holiday_balances': holiday_balances,
            'monthly_stats': {
                'work_days': work_days,
                'holiday_days': holiday_days,
                'total_days': total_days,
                'remaining_days': remaining_days,
            },
            'staff_profile': staff_profile,
        })
        
        return context


class ShiftRequestView(LoginRequiredMixin, View):
    """シフト希望提出（スマートフォン用）"""
    template_name = 'schedule/shift_request.html'
    
    def get(self, request, *args, **kwargs):
        staff_profile = get_current_staff_profile(request.user)
        if not staff_profile:
            messages.error(request, 'スタッフプロフィールが設定されていません。')
            return redirect('schedule:profile_setup')
        
        # アクティブな期間を取得
        try:
            period = SchedulePeriod.objects.filter(is_active=True).latest('created_at')
        except SchedulePeriod.DoesNotExist:
            messages.error(request, 'シフト期間が設定されていません。')
            return render(request, self.template_name, {'period': None})
        
        # 日付リストの生成
        date_list = generate_date_list(period.start_date, period.end_date)
        
        # 既存の希望を取得
        existing_requests = {
            req.date: req.priority 
            for req in ShiftRequest.objects.filter(staff=staff_profile, period=period)
        }
        
        # 日付リストに既存希望を結合
        for date_info in date_list:
            date_info['current_priority'] = existing_requests.get(date_info['date'])
        
        # 締切までの日数計算
        days_until_deadline = (period.request_deadline.date() - timezone.now().date()).days
        
        context = {
            'period': period,
            'date_list': date_list,
            'days_until_deadline': max(0, days_until_deadline),
            'staff_profile': staff_profile,
        }
        
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        """希望の保存処理"""
        try:
            data = json.loads(request.body)
            action = data.get('action')
            period_id = data.get('period_id')
            requests_data = data.get('requests', {})
            
            staff_profile = get_current_staff_profile(request.user)
            period = get_object_or_404(SchedulePeriod, id=period_id)
            
            # 締切チェック
            if not period.is_request_open:
                return JsonResponse({
                    'success': False,
                    'message': '希望提出期間が終了しています。'
                })
            
            with transaction.atomic():
                # 既存の希望を削除
                ShiftRequest.objects.filter(
                    staff=staff_profile,
                    period=period
                ).delete()
                
                # 新しい希望を作成
                new_requests = []
                for date_str, priority in requests_data.items():
                    try:
                        request_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        if period.start_date <= request_date <= period.end_date:
                            new_requests.append(
                                ShiftRequest(
                                    staff=staff_profile,
                                    period=period,
                                    date=request_date,
                                    priority=int(priority)
                                )
                            )
                    except (ValueError, TypeError):
                        continue
                
                # バルクインサート
                ShiftRequest.objects.bulk_create(new_requests)
            
            # 自動保存かフル提出かで異なるメッセージ
            if action == 'auto_save':
                message = '自動保存しました。'
            else:
                message = f'希望を提出しました。（{len(new_requests)}件）'
                
                # 提出ログを記録
                ScheduleLog.objects.create(
                    period=period,
                    action='request_submit',
                    user=request.user,
                    description=f'{staff_profile.display_name}が希望を提出',
                    success=True
                )
            
            return JsonResponse({
                'success': True,
                'message': message,
                'period_id': period_id,
                'count': len(new_requests)
            })
            
        except Exception as e:
            logger.error(f'シフト希望保存エラー: {str(e)}')
            return JsonResponse({
                'success': False,
                'message': 'システムエラーが発生しました。'
            })


class HolidayBalanceView(LoginRequiredMixin, TemplateView):
    """休日残数確認"""
    template_name = 'schedule/holiday_balance.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        staff_profile = get_current_staff_profile(self.request.user)
        if staff_profile:
            year = int(self.request.GET.get('year', datetime.now().year))
            
            balances = HolidayBalance.objects.filter(
                staff=staff_profile,
                year=year
            ).select_related('holiday_type')
            
            context.update({
                'balances': balances,
                'year': year,
                'staff_profile': staff_profile,
            })
        
        return context


# --- 管理者向けビュー ---

class AdminDashboardView(UserPassesTestMixin, TemplateView):
    """管理者ダッシュボード（PC用）"""
    template_name = 'schedule/admin_dashboard.html'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 利用可能な期間一覧
        available_periods = SchedulePeriod.objects.all().order_by('-start_date')
        
        # 現在選択中の期間
        period_id = self.request.GET.get('period_id')
        if period_id:
            current_period = get_object_or_404(SchedulePeriod, id=period_id)
        else:
            current_period = available_periods.first()
        
        if not current_period:
            context.update({
                'available_periods': available_periods,
                'current_period': None,
                'stats': {},
                'alerts': [{'level': 'warning', 'icon': 'exclamation-triangle', 
                          'message': 'シフト期間が設定されていません。'}]
            })
            return context
        
        # 統計情報の計算
        stats = self._calculate_stats(current_period)
        
        # AI実行状況の確認
        ai_status = self._get_ai_status(current_period)
        
        # 最近のログ
        recent_logs = ScheduleLog.objects.filter(
            period=current_period
        ).order_by('-created_at')[:10]
        
        # アラート一覧
        alerts = self._generate_alerts(current_period, stats)
        
        context.update({
            'available_periods': available_periods,
            'current_period': current_period,
            'stats': stats,
            'ai_status': ai_status,
            'recent_logs': recent_logs,
            'alerts': alerts,
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        """AI実行などのアクション処理"""
        action = request.POST.get('action')
        period_id = request.POST.get('period_id')
        
        if action == 'run_ai' and period_id:
            try:
                # 非同期でAIスケジューラを実行
                from .tasks import run_ai_scheduler_task
                
                task = run_ai_scheduler_task.delay(int(period_id), request.user.id)
                
                messages.success(request, 'AIによるシフト作成を開始しました。完了まで数分かかります。')
                
                return JsonResponse({
                    'success': True,
                    'message': 'AI処理を開始しました。',
                    'task_id': task.id
                })
                
            except Exception as e:
                logger.error(f'AI実行エラー: {str(e)}')
                return JsonResponse({
                    'success': False,
                    'message': f'AI実行エラー: {str(e)}'
                })
        
        return JsonResponse({
            'success': False,
            'message': '無効なアクションです。'
        })
    
    def _calculate_stats(self, period: SchedulePeriod) -> Dict:
        """統計情報の計算"""
        total_staff = StaffProfile.objects.filter(is_active=True).count()
        
        # 希望提出状況
        submitted_staff = StaffRequest.objects.filter(
            period=period
        ).values('staff').distinct().count()
        
        # 必要人数設定状況
        total_days = (period.end_date - period.start_date).days + 1
        requirements_set = DailyRequirement.objects.filter(
            period=period
        ).values('date').distinct().count()
        
        # 完成度計算
        has_requests = submitted_staff > 0
        has_requirements = requirements_set > 0
        can_run_ai = has_requests and has_requirements
        
        completion_rate = 0
        if total_staff > 0:
            completion_rate = (submitted_staff / total_staff) * 50
        if total_days > 0:
            completion_rate += (requirements_set / total_days) * 50
        
        return {
            'total_staff': total_staff,
            'submitted_requests': submitted_staff,
            'requirements_set': requirements_set,
            'completion_rate': int(completion_rate),
            'can_run_ai': can_run_ai,
            'has_requests': has_requests,
            'has_requirements': has_requirements,
            'progress_offset': 283 - (283 * completion_rate / 100),  # SVG circle progress
        }
    
    def _get_ai_status(self, period: SchedulePeriod) -> Dict:
        """AI実行状況の取得"""
        # 実装では Celery タスクの状況をチェック
        # ここでは簡易版
        latest_log = ScheduleLog.objects.filter(
            period=period,
            action='ai_create'
        ).order_by('-created_at').first()
        
        return {
            'is_running': False,  # 実際はCeleryタスク状況をチェック
            'progress': 0,
            'estimated_time': 0,
            'last_result': {
                'success': latest_log.success if latest_log else None,
                'message': latest_log.description if latest_log else None,
                'created_at': latest_log.created_at if latest_log else None,
                'execution_time': latest_log.execution_time if latest_log else None,
                'assignments_count': 0,  # 実際の割り当て数を計算
            } if latest_log else None
        }
    
    def _generate_alerts(self, period: SchedulePeriod, stats: Dict) -> List[Dict]:
        """アラート一覧の生成"""
        alerts = []
        
        if stats['submitted_requests'] == 0:
            alerts.append({
                'level': 'danger',
                'icon': 'exclamation-triangle',
                'message': 'まだ希望提出がありません。スタッフに提出を促してください。'
            })
        
        if stats['requirements_set'] == 0:
            alerts.append({
                'level': 'warning',
                'icon': 'calendar-x',
                'message': '必要人数が設定されていません。'
            })
        
        if period.is_request_open:
            days_left = (period.request_deadline.date() - timezone.now().date()).days
            if days_left <= 1:
                alerts.append({
                    'level': 'warning',
                    'icon': 'clock',
                    'message': f'希望提出締切まで{days_left}日です。'
                })
        
        return alerts


class AdminCalendarView(UserPassesTestMixin, TemplateView):
    """管理者用シフト調整カレンダー（PC用）"""
    template_name = 'schedule/admin_calendar.html'
    
    def test_func(self):
        return is_admin(self.request.user)


# --- API エンドポイント ---

class ScheduleAPIView(LoginRequiredMixin, View):
    """スケジュール関連API"""
    
    def get(self, request, *args, **kwargs):
        """月間スケジュールデータの取得"""
        try:
            year = int(request.GET.get('year', datetime.now().year))
            month = int(request.GET.get('month', datetime.now().month))
            
            staff_profile = get_current_staff_profile(request.user)
            if not staff_profile:
                return JsonResponse({'error': 'スタッフプロフィールが見つかりません'}, status=404)
            
            # 月間のシフト割り当てを取得
            month_start = date(year, month, 1)
            month_end = date(year, month, monthrange(year, month)[1])
            
            assignments = ShiftAssignment.objects.filter(
                staff=staff_profile,
                date__range=(month_start, month_end)
            ).select_related('holiday_type')
            
            # JSON形式に変換
            assignments_data = {}
            for assignment in assignments:
                date_str = assignment.date.strftime('%Y-%m-%d')
                assignments_data[date_str] = {
                    'isWorkday': assignment.is_workday,
                    'holidayType': assignment.holiday_type.name if assignment.holiday_type else '',
                    'notes': assignment.notes or '',
                    'manuallyAdjusted': assignment.manually_adjusted,
                    'createdByAi': assignment.created_by_ai,
                    'updatedAt': assignment.updated_at.strftime('%Y-%m-%d %H:%M')
                }
            
            # 統計情報
            work_days = sum(1 for a in assignments_data.values() if a['isWorkday'])
            holiday_days = len(assignments_data) - work_days
            
            return JsonResponse({
                'success': True,
                'assignments': assignments_data,
                'stats': {
                    'work_days': work_days,
                    'holiday_days': holiday_days,
                    'total_days': len(assignments_data)
                }
            })
            
        except Exception as e:
            logger.error(f'スケジュールAPI取得エラー: {str(e)}')
            return JsonResponse({'error': 'データ取得エラー'}, status=500)


# --- エラーハンドリング ---

def handler404(request, exception):
    """404エラーハンドラー"""
    return render(request, 'schedule/404.html', status=404)

def handler500(request):
    """500エラーハンドラー"""
    return render(request, 'schedule/500.html', status=500)


# --- Celeryタスク（非同期処理）---

try:
    from celery import shared_task
    
    @shared_task
    def run_ai_scheduler_task(period_id: int, user_id: Optional[int] = None):
        """AI スケジューラの非同期実行"""
        try:
            from .scheduler.ai_engine import ShiftSchedulerService
            
            result = ShiftSchedulerService.generate_schedule(period_id, user_id)
            
            return {
                'success': result['success'],
                'message': result['message'],
                'assignments_count': result.get('assignments_count', 0),
                'execution_time': result.get('execution_time', 0)
            }
            
        except Exception as e:
            logger.error(f'AI スケジューラタスクエラー: {str(e)}')
            return {
                'success': False,
                'message': f'エラー: {str(e)}',
                'assignments_count': 0,
                'execution_time': 0
            }
    
except ImportError:
    # Celeryが利用できない場合のフォールバック
    logger.warning('Celery が利用できません。同期処理で実行されます。')
    
    def run_ai_scheduler_task(period_id: int, user_id: Optional[int] = None):
        """同期版AI スケジューラ実行"""
        from .scheduler.ai_engine import ShiftSchedulerService
        return ShiftSchedulerService.generate_schedule(period_id, user_id)
