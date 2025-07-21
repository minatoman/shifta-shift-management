# schedule/scheduler/ai_engine.py
"""
Shifta AIスケジューラ
PuLPを使用した数理最適化によるシフト自動作成システム

機能:
- スタッフの希望を最大限考慮
- 職種別必要人数の確保
- 連勤制限・月間勤務日数制限の遵守
- 複数の制約条件下での最適解の導出
"""

import pulp
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from django.db import transaction
from django.utils import timezone

from ..models import (
    SchedulePeriod, StaffProfile, ShiftRequest, DailyRequirement,
    ShiftAssignment, HolidayType, ScheduleLog
)

logger = logging.getLogger(__name__)


class ShiftOptimizer:
    """
    シフト最適化エンジン
    PuLPライブラリを使用して制約最適化問題を解く
    """
    
    def __init__(self, period_id: int):
        self.period = SchedulePeriod.objects.get(id=period_id)
        self.staff_list = StaffProfile.objects.filter(is_active=True)
        self.date_range = self._generate_date_range()
        self.requests = self._load_shift_requests()
        self.requirements = self._load_daily_requirements()
        
        # 最適化変数
        self.is_working = {}
        self.problem = None
        
        logger.info(f"シフト最適化を開始: {self.period.name}")
        logger.info(f"対象スタッフ数: {self.staff_list.count()}")
        logger.info(f"対象期間: {len(self.date_range)}日間")

    def _generate_date_range(self) -> List[datetime.date]:
        """対象期間の日付リストを生成"""
        dates = []
        current_date = self.period.start_date
        while current_date <= self.period.end_date:
            dates.append(current_date)
            current_date += timedelta(days=1)
        return dates

    def _load_shift_requests(self) -> Dict:
        """スタッフの希望を読み込み"""
        requests = {}
        for request in ShiftRequest.objects.filter(period=self.period):
            key = (request.staff.id, request.date)
            requests[key] = request.priority
        
        logger.info(f"読み込み済み希望件数: {len(requests)}")
        return requests

    def _load_daily_requirements(self) -> Dict:
        """日別必要人数を読み込み"""
        requirements = {}
        for req in DailyRequirement.objects.filter(period=self.period):
            key = (req.date, req.job_type.id)
            requirements[key] = {
                'min_count': req.min_staff_count,
                'required_count': req.required_staff_count
            }
        
        logger.info(f"読み込み済み必要人数設定: {len(requirements)}")
        return requirements

    def create_optimization_problem(self):
        """最適化問題の定義"""
        logger.info("最適化問題を構築中...")
        
        # 1. 問題の初期化
        self.problem = pulp.LpProblem("ShiftScheduling", pulp.LpMaximize)
        
        # 2. 決定変数の定義
        self._create_decision_variables()
        
        # 3. 目的関数の設定
        self._set_objective_function()
        
        # 4. 制約条件の追加
        self._add_constraints()
        
        logger.info("最適化問題の構築完了")

    def _create_decision_variables(self):
        """決定変数の作成: is_working[staff_id][date_str]"""
        for staff in self.staff_list:
            for date in self.date_range:
                date_str = date.strftime('%Y-%m-%d')
                var_name = f"work_{staff.id}_{date_str}"
                self.is_working[(staff.id, date_str)] = pulp.LpVariable(
                    var_name, cat='Binary'
                )

    def _set_objective_function(self):
        """目的関数の設定: 希望の優先度に基づくスコア最大化"""
        objective_terms = []
        
        for staff in self.staff_list:
            for date in self.date_range:
                date_str = date.strftime('%Y-%m-%d')
                var = self.is_working[(staff.id, date_str)]
                
                # スタッフの希望を取得
                request_key = (staff.id, date)
                priority = self.requests.get(request_key, 2)  # デフォルト: 勤務可
                
                # 優先度に応じたスコア設定
                if priority == 3:  # 勤務最優先
                    objective_terms.append(10 * var)
                elif priority == 2:  # 勤務可
                    objective_terms.append(1 * var)
                elif priority == 1:  # 休み希望
                    objective_terms.append(-100 * var)  # 大きなペナルティ
        
        self.problem += pulp.lpSum(objective_terms), "TotalPriorityScore"

    def _add_constraints(self):
        """制約条件の追加"""
        logger.info("制約条件を追加中...")
        
        # A. 日別最低人数の確保
        self._add_daily_minimum_constraints()
        
        # B. スタッフ別月間勤務日数制限
        self._add_monthly_workday_constraints()
        
        # C. 最大連勤制限
        self._add_consecutive_workday_constraints()
        
        # D. 休み希望の強制実現（追加のペナルティ制約）
        self._add_holiday_request_constraints()

    def _add_daily_minimum_constraints(self):
        """日別・職種別最低人数制約"""
        constraint_count = 0
        
        for date in self.date_range:
            for job_type_id in self._get_all_job_type_ids():
                req_key = (date, job_type_id)
                if req_key in self.requirements:
                    min_count = self.requirements[req_key]['min_count']
                    
                    # 該当職種のスタッフの勤務変数の合計 >= 最低人数
                    staff_vars = [
                        self.is_working[(s.id, date.strftime('%Y-%m-%d'))]
                        for s in self.staff_list 
                        if s.job_type and s.job_type.id == job_type_id
                    ]
                    
                    if staff_vars:
                        constraint_name = f"daily_min_{date}_{job_type_id}"
                        self.problem += (
                            pulp.lpSum(staff_vars) >= min_count,
                            constraint_name
                        )
                        constraint_count += 1
        
        logger.info(f"日別最低人数制約: {constraint_count}件")

    def _add_monthly_workday_constraints(self):
        """月間勤務日数制約"""
        constraint_count = 0
        
        for staff in self.staff_list:
            if staff.work_style:
                # 月間勤務日数の合計変数
                monthly_vars = [
                    self.is_working[(staff.id, date.strftime('%Y-%m-%d'))]
                    for date in self.date_range
                ]
                
                # 最低勤務日数制約
                if staff.work_style.min_shifts_per_month > 0:
                    self.problem += (
                        pulp.lpSum(monthly_vars) >= staff.work_style.min_shifts_per_month,
                        f"min_monthly_{staff.id}"
                    )
                    constraint_count += 1
                
                # 最大勤務日数制約
                self.problem += (
                    pulp.lpSum(monthly_vars) <= staff.work_style.max_shifts_per_month,
                    f"max_monthly_{staff.id}"
                )
                constraint_count += 1
        
        logger.info(f"月間勤務日数制約: {constraint_count}件")

    def _add_consecutive_workday_constraints(self):
        """最大連勤制約"""
        constraint_count = 0
        
        for staff in self.staff_list:
            if staff.work_style and staff.work_style.allow_consecutive_days > 0:
                max_consecutive = staff.work_style.allow_consecutive_days
                
                # 連続するmax_consecutive + 1日間のうち、
                # 勤務日がmax_consecutive日を超えてはいけない
                for i in range(len(self.date_range) - max_consecutive):
                    consecutive_vars = [
                        self.is_working[(staff.id, self.date_range[i + j].strftime('%Y-%m-%d'))]
                        for j in range(max_consecutive + 1)
                    ]
                    
                    self.problem += (
                        pulp.lpSum(consecutive_vars) <= max_consecutive,
                        f"consecutive_{staff.id}_{i}"
                    )
                    constraint_count += 1
        
        logger.info(f"最大連勤制約: {constraint_count}件")

    def _add_holiday_request_constraints(self):
        """休み希望の強制制約（優先度1の日は必ず休み）"""
        constraint_count = 0
        
        for staff in self.staff_list:
            for date in self.date_range:
                request_key = (staff.id, date)
                if self.requests.get(request_key) == 1:  # 休み希望
                    date_str = date.strftime('%Y-%m-%d')
                    var = self.is_working[(staff.id, date_str)]
                    
                    # 休み希望の日は勤務させない（強制制約）
                    self.problem += (
                        var == 0,
                        f"holiday_request_{staff.id}_{date_str}"
                    )
                    constraint_count += 1
        
        logger.info(f"休み希望強制制約: {constraint_count}件")

    def _get_all_job_type_ids(self) -> List[int]:
        """システム内の全職種IDを取得"""
        return list(set(
            s.job_type.id for s in self.staff_list 
            if s.job_type is not None
        ))

    def solve(self) -> Tuple[bool, str]:
        """最適化問題を解く"""
        if not self.problem:
            return False, "最適化問題が定義されていません"
        
        logger.info("最適化計算を開始...")
        start_time = datetime.now()
        
        try:
            # PuLPソルバーで解く
            self.problem.solve(pulp.PULP_CBC_CMD(msg=0))
            
            execution_time = (datetime.now() - start_time).total_seconds()
            status = pulp.LpStatus[self.problem.status]
            
            logger.info(f"最適化完了: {status} (実行時間: {execution_time:.2f}秒)")
            
            if status == 'Optimal':
                return True, "最適解が見つかりました"
            elif status == 'Feasible':
                return True, "実行可能解が見つかりました"
            else:
                return False, f"解が見つかりませんでした: {status}"
                
        except Exception as e:
            logger.error(f"最適化中にエラーが発生: {str(e)}")
            return False, f"計算エラー: {str(e)}"

    def save_results(self) -> int:
        """最適化結果をデータベースに保存"""
        if not self.problem or pulp.LpStatus[self.problem.status] not in ['Optimal', 'Feasible']:
            raise ValueError("有効な解が存在しません")
        
        logger.info("結果をデータベースに保存中...")
        assignment_count = 0
        
        # 既存の割り当てを削除
        with transaction.atomic():
            ShiftAssignment.objects.filter(
                date__range=(self.period.start_date, self.period.end_date)
            ).delete()
            
            # 新しい割り当てを作成
            assignments_to_create = []
            
            for staff in self.staff_list:
                for date in self.date_range:
                    date_str = date.strftime('%Y-%m-%d')
                    var = self.is_working[(staff.id, date_str)]
                    
                    if pulp.value(var) == 1:
                        # 勤務日として保存
                        assignments_to_create.append(
                            ShiftAssignment(
                                staff=staff,
                                date=date,
                                is_workday=True,
                                created_by_ai=True,
                                manually_adjusted=False
                            )
                        )
                        assignment_count += 1
                    else:
                        # 休日として保存（デフォルトの休日種別を使用）
                        default_holiday = HolidayType.objects.filter(
                            name='週休'
                        ).first()
                        
                        assignments_to_create.append(
                            ShiftAssignment(
                                staff=staff,
                                date=date,
                                is_workday=False,
                                holiday_type=default_holiday,
                                created_by_ai=True,
                                manually_adjusted=False
                            )
                        )
            
            # バルクインサートで効率的に保存
            ShiftAssignment.objects.bulk_create(assignments_to_create)
        
        logger.info(f"結果保存完了: {assignment_count}件の勤務割り当て")
        return assignment_count


class ShiftSchedulerService:
    """
    シフト作成サービス
    最適化エンジンを制御し、結果の管理を行う
    """
    
    @staticmethod
    def generate_schedule(period_id: int, user_id: Optional[int] = None) -> Dict:
        """
        指定期間のシフトを自動生成
        
        Args:
            period_id: 対象期間のID
            user_id: 実行ユーザーのID
            
        Returns:
            結果辞書（成功/失敗、メッセージ、統計情報等）
        """
        start_time = datetime.now()
        
        try:
            # 1. 最適化エンジンの初期化
            optimizer = ShiftOptimizer(period_id)
            
            # 2. 最適化問題の構築
            optimizer.create_optimization_problem()
            
            # 3. 問題を解く
            success, message = optimizer.solve()
            
            if not success:
                # 失敗ログを記録
                ShiftSchedulerService._log_execution(
                    period_id, 'ai_create', user_id, 
                    message, False, 
                    (datetime.now() - start_time).total_seconds()
                )
                return {
                    'success': False,
                    'message': message,
                    'assignments_count': 0
                }
            
            # 4. 結果の保存
            assignments_count = optimizer.save_results()
            
            # 5. 成功ログを記録
            execution_time = (datetime.now() - start_time).total_seconds()
            ShiftSchedulerService._log_execution(
                period_id, 'ai_create', user_id,
                f"{assignments_count}件の割り当てを作成", True,
                execution_time
            )
            
            return {
                'success': True,
                'message': f'シフトの自動作成が完了しました。{assignments_count}件の勤務を割り当てました。',
                'assignments_count': assignments_count,
                'execution_time': execution_time
            }
            
        except Exception as e:
            logger.error(f"シフト作成中にエラーが発生: {str(e)}")
            
            # エラーログを記録
            ShiftSchedulerService._log_execution(
                period_id, 'ai_create', user_id,
                f"エラー: {str(e)}", False,
                (datetime.now() - start_time).total_seconds()
            )
            
            return {
                'success': False,
                'message': f'シフト作成中にエラーが発生しました: {str(e)}',
                'assignments_count': 0
            }

    @staticmethod
    def _log_execution(period_id: int, action: str, user_id: Optional[int],
                      description: str, success: bool, execution_time: float):
        """実行ログの記録"""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            log_entry = ScheduleLog(
                period_id=period_id,
                action=action,
                user_id=user_id,
                description=description,
                success=success,
                execution_time=execution_time
            )
            log_entry.save()
            
        except Exception as e:
            logger.error(f"ログ記録エラー: {str(e)}")

    @staticmethod
    def get_optimization_statistics(period_id: int) -> Dict:
        """最適化結果の統計情報を取得"""
        try:
            period = SchedulePeriod.objects.get(id=period_id)
            assignments = ShiftAssignment.objects.filter(
                date__range=(period.start_date, period.end_date)
            )
            
            total_assignments = assignments.count()
            workday_assignments = assignments.filter(is_workday=True).count()
            holiday_assignments = total_assignments - workday_assignments
            
            # 希望実現率の計算
            total_requests = ShiftRequest.objects.filter(period=period).count()
            fulfilled_requests = 0
            
            for request in ShiftRequest.objects.filter(period=period):
                assignment = assignments.filter(
                    staff=request.staff, date=request.date
                ).first()
                
                if assignment:
                    if request.priority == 1 and not assignment.is_workday:
                        fulfilled_requests += 1  # 休み希望が実現
                    elif request.priority in [2, 3] and assignment.is_workday:
                        fulfilled_requests += 1  # 勤務希望が実現
            
            fulfillment_rate = (fulfilled_requests / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'total_assignments': total_assignments,
                'workday_assignments': workday_assignments,
                'holiday_assignments': holiday_assignments,
                'total_requests': total_requests,
                'fulfilled_requests': fulfilled_requests,
                'fulfillment_rate': round(fulfillment_rate, 1)
            }
            
        except Exception as e:
            logger.error(f"統計情報取得エラー: {str(e)}")
            return {}


# Celeryタスク用のラッパー関数
def run_shift_optimization_task(period_id: int, user_id: Optional[int] = None):
    """
    Celeryで非同期実行するためのタスク関数
    """
    return ShiftSchedulerService.generate_schedule(period_id, user_id)
