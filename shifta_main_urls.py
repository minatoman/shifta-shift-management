# shifta/urls.py
"""
Shifta Project Main URL Configuration
スマートフォン対応シフト管理システム
メインURL設定ファイル
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.http import HttpResponse
from django.shortcuts import render

# 基本的な設定確認用ビュー
def health_check(request):
    """システムヘルスチェック"""
    return HttpResponse("OK", content_type="text/plain")

def system_info(request):
    """システム情報表示"""
    if not request.user.is_superuser:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Access denied")
    
    return render(request, 'debug/system_info.html', {
        'debug': settings.DEBUG,
        'version': '1.0.0',
        'django_version': __import__('django').get_version(),
    })

# メインURL設定
urlpatterns = [
    # Django管理画面
    path('django-admin/', admin.site.urls),
    
    # ホームページ（シフトアプリにリダイレクト）
    path('', RedirectView.as_view(url='/schedule/', permanent=False)),
    
    # シフト管理システム
    path('schedule/', include('schedule.urls')),
    
    # システム監視
    path('health/', health_check, name='health_check'),
    path('system-info/', system_info, name='system_info'),
]

# 開発環境用設定
if settings.DEBUG:
    import debug_toolbar
    
    # Django Debug Toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]
    
    # 静的ファイルとメディアファイルの配信
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    # 開発用追加URL
    from django.views.generic import TemplateView
    
    urlpatterns += [
        # 開発用テストページ
        path('dev/test/', TemplateView.as_view(template_name='dev/test.html'), name='dev_test'),
        path('dev/mobile-test/', TemplateView.as_view(template_name='dev/mobile_test.html'), name='mobile_test'),
        path('dev/api-test/', TemplateView.as_view(template_name='dev/api_test.html'), name='api_test'),
    ]

# カスタムエラーハンドラー
handler404 = 'schedule.views.handler404'
handler500 = 'schedule.views.handler500'
handler403 = 'schedule.views.handler403'
handler400 = 'schedule.views.handler400'

# セキュリティ関連URL（本番環境用）
if not settings.DEBUG:
    from django.views.generic import TemplateView
    
    urlpatterns += [
        # セキュリティポリシー
        path('.well-known/security.txt', TemplateView.as_view(
            template_name='security/security.txt',
            content_type='text/plain'
        )),
        
        # ロボットポリシー
        path('robots.txt', TemplateView.as_view(
            template_name='robots.txt',
            content_type='text/plain'
        )),
        
        # サイトマップ
        path('sitemap.xml', TemplateView.as_view(
            template_name='sitemap.xml',
            content_type='application/xml'
        )),
    ]

# 管理画面のカスタマイズ
admin.site.site_header = 'Shifta 管理画面'
admin.site.site_title = 'Shifta Admin'
admin.site.index_title = 'シフト管理システム'
