from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("verify/", views.verify_email, name="verify"),
    path("verify/resend/", views.resend_code, name="resend_code"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("password-reset/", views.PasswordResetRequestView.as_view(), name="password_reset"),
    path("password-reset/sent/", views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("password-reset/<uidb64>/<token>/", views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("password-reset/complete/", views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
]
