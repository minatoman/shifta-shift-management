# schedule/tasks.py
"""
Shifta Celery Tasks
スマートフォン対応シフト管理システム
非同期処理タスク定義
"""

from celery import Celery, shared_task
from celery.schedules import crontab
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Celeryアプリケーションの初期化
app = Celery('shifta')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@shared_task(bind=True, max_retries=3)
def optimize_schedule_task(self, period_id):
    """
    AIスケジュール最適化タスク
    大量のデータ処理のため非同期で実行
    """
    try:
        from .models import SchedulePeriod, ShiftAssignment
        from .ai_scheduler import ShiftOptimizer
        
        logger.info(f"スケジュール最適化開始: Period {period_id}")
        
        # 対象期間の取得
        period = SchedulePeriod.objects.get(id=period_id)
        
        # 既存の割り当てをクリア
        ShiftAssignment.objects.filter(
            date__range=[period.start_date, period.end_date]
        ).delete()
        
        # AI最適化実行
        optimizer = ShiftOptimizer()
        result = optimizer.optimize_period(period)
        
        if result['success']:
            logger.info(f"スケジュール最適化完了: Period {period_id}")
            
            # 最適化結果の保存
            period.optimization_status = 'completed'
            period.optimization_score = result.get('score', 0)
            period.optimization_completed_at = timezone.now()
            period.save()
            
            # 成功通知の送信
            send_optimization_notification.delay(period_id, 'success', result)
            
        else:
            logger.error(f"スケジュール最適化失敗: Period {period_id}, {result.get('error', '')}")
            
            # 失敗ステータスの更新
            period.optimization_status = 'failed'
            period.optimization_error = result.get('error', '不明なエラー')
            period.save()
            
            # エラー通知の送信
            send_optimization_notification.delay(period_id, 'error', result)
        
        return result
        
    except Exception as exc:
        logger.error(f"スケジュール最適化でエラー: {exc}")
        
        # リトライ処理
        if self.request.retries < self.max_retries:
            logger.info(f"タスクを再実行します (試行回数: {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        # 最終的に失敗した場合
        try:
            period = SchedulePeriod.objects.get(id=period_id)
            period.optimization_status = 'failed'
            period.optimization_error = str(exc)
            period.save()
        except:
            pass
        
        raise exc


@shared_task
def send_optimization_notification(period_id, status, result):
    """最適化完了/失敗通知の送信"""
    try:
        from .models import SchedulePeriod
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        period = SchedulePeriod.objects.get(id=period_id)
        
        # 管理者ユーザーを取得
        admin_users = User.objects.filter(is_staff=True, is_active=True)
        
        if status == 'success':
            subject = f'シフト最適化完了: {period.name}'
            template = 'emails/optimization_success.html'
        else:
            subject = f'シフト最適化エラー: {period.name}'
            template = 'emails/optimization_error.html'
        
        # メール送信
        for admin in admin_users:
            message = render_to_string(template, {
                'user': admin,
                'period': period,
                'result': result,
                'status': status,
            })
            
            send_mail(
                subject=subject,
                message='',
                html_message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[admin.email],
                fail_silently=False,
            )
        
        logger.info(f"最適化通知送信完了: {period_id} ({status})")
        
    except Exception as exc:
        logger.error(f"通知送信エラー: {exc}")


@shared_task
def send_shift_reminders():
    """シフト希望提出リマインダーの送信"""
    try:
        from .models import SchedulePeriod
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        today = timezone.now().date()
        
        # 明日が締切の期間を取得
        tomorrow = today + timedelta(days=1)
        periods = SchedulePeriod.objects.filter(
            request_deadline=tomorrow,
            is_active=True
        )
        
        for period in periods:
            # まだ希望を提出していないスタッフを取得
            submitted_users = period.shift_requests.values_list('user', flat=True).distinct()
            pending_users = User.objects.filter(
                is_active=True,
                groups__name='スタッフ'
            ).exclude(id__in=submitted_users)
            
            # リマインダー送信
            for user in pending_users:
                message = render_to_string('emails/shift_reminder.html', {
                    'user': user,
                    'period': period,
                    'deadline': period.request_deadline,
                })
                
                send_mail(
                    subject=f'シフト希望提出リマインダー: {period.name}',
                    message='',
                    html_message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
        
        logger.info("シフトリマインダー送信完了")
        
    except Exception as exc:
        logger.error(f"リマインダー送信エラー: {exc}")


@shared_task
def generate_monthly_reports():
    """月次レポートの自動生成"""
    try:
        from .models import SchedulePeriod, ShiftAssignment
        from .utils import generate_report_data
        
        # 前月のデータを対象とする
        last_month = timezone.now().replace(day=1) - timedelta(days=1)
        year, month = last_month.year, last_month.month
        
        # 対象期間のシフト割り当てを取得
        assignments = ShiftAssignment.objects.filter(
            date__year=year,
            date__month=month
        )
        
        if assignments.exists():
            # レポートデータ生成
            report_data = generate_report_data(assignments)
            
            # レポートファイルの保存
            # TODO: ファイル保存処理の実装
            
            logger.info(f"月次レポート生成完了: {year}/{month}")
        
    except Exception as exc:
        logger.error(f"月次レポート生成エラー: {exc}")


@shared_task
def cleanup_old_data():
    """古いデータのクリーンアップ"""
    try:
        from .models import SchedulePeriod, ShiftRequest, ShiftAssignment
        
        # 1年以上前のデータを削除
        cutoff_date = timezone.now().date() - timedelta(days=365)
        
        # 古い期間とその関連データを削除
        old_periods = SchedulePeriod.objects.filter(end_date__lt=cutoff_date)
        deleted_count = 0
        
        for period in old_periods:
            # 関連データの削除
            ShiftRequest.objects.filter(period=period).delete()
            ShiftAssignment.objects.filter(
                date__range=[period.start_date, period.end_date]
            ).delete()
            
            # 期間の削除
            period.delete()
            deleted_count += 1
        
        logger.info(f"古いデータクリーンアップ完了: {deleted_count}件の期間を削除")
        
    except Exception as exc:
        logger.error(f"データクリーンアップエラー: {exc}")


def setup_periodic_tasks():
    """定期実行タスクのセットアップ"""
    
    # 毎日18:00にシフトリマインダーを送信
    app.conf.beat_schedule = {
        'send-shift-reminders': {
            'task': 'schedule.tasks.send_shift_reminders',
            'schedule': crontab(hour=18, minute=0),
        },
        
        # 毎月1日の早朝に月次レポートを生成
        'generate-monthly-reports': {
            'task': 'schedule.tasks.generate_monthly_reports',
            'schedule': crontab(hour=3, minute=0, day_of_month=1),
        },
        
        # 毎週日曜日の深夜にデータクリーンアップ
        'cleanup-old-data': {
            'task': 'schedule.tasks.cleanup_old_data',
            'schedule': crontab(hour=2, minute=0, day_of_week=0),
        },
    }
    
    app.conf.timezone = 'Asia/Tokyo'


# Celery設定
if hasattr(settings, 'CELERY_BROKER_URL'):
    app.conf.update(
        broker_url=settings.CELERY_BROKER_URL,
        result_backend=settings.CELERY_RESULT_BACKEND,
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='Asia/Tokyo',
        enable_utc=True,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        worker_max_tasks_per_child=1000,
    )
