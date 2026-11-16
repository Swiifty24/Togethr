from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.urls import reverse, NoReverseMatch
from django.contrib import messages
from .forms import RegisterForm


# ── Public ───────────────────────────────────────────────────────────────

def welcome(request):
    """Public landing page at '/' — always visible to everyone."""
    return render(request, "welcome.html")


# ── Auth ─────────────────────────────────────────────────────────────────

def register_view(request):
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome to TOGETHR! 🎉")
            return redirect("home")
    else:
        form = RegisterForm()
    return render(request, "register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, "Signed in successfully!")
            return redirect("home")
        else:
            messages.error(request, "Invalid username or password.")
    return render(request, "login.html")


def logout_view(request):
    logout(request)
    messages.info(request, "You've been signed out.")
    return redirect("welcome")


# ── Logged-in pages ──────────────────────────────────────────────────────

@login_required(login_url="/login/")
def home(request):
    """Main page after sign-in."""
    return render(request, "home.html")


# ── Staff Area ───────────────────────────────────────────────────────────

@staff_member_required
def staff_dashboard(request):
    """Staff-only dashboard summarizing users, activities, and RSVPs.
    
    Protected with @staff_member_required: non-staff and unauthenticated
    users are blocked and redirected to admin login.
    """
    # Real queries for Django's built-in User model
    total_users = User.objects.count()
    recent_users = User.objects.order_by("-date_joined")[:5]

    # Query Activity and Participation if defined in models.py;
    # otherwise show clearly marked placeholders.
    try:
        from .models import Activity
        has_activity_model = True
        total_activities = Activity.objects.count()
        if hasattr(Activity, "status"):
            cancelled_activities = Activity.objects.filter(status="cancelled").count()
        elif hasattr(Activity, "is_cancelled"):
            cancelled_activities = Activity.objects.filter(is_cancelled=True).count()
        else:
            cancelled_activities = 0
        recent_activities = Activity.objects.select_related("creator").order_by("-id")[:5]
    except (ImportError, AttributeError):
        has_activity_model = False
        # Placeholder stats until Activity model is created in models.py:
        # Real query: total_activities = Activity.objects.count()
        # Real query: cancelled_activities = Activity.objects.filter(status="cancelled").count()
        # Real query: recent_activities = Activity.objects.select_related("creator").order_by("-date")[:5]
        total_activities = None
        cancelled_activities = None
        recent_activities = []

    try:
        from .models import Participation
        has_participation_model = True
        confirmed_count = Participation.objects.filter(status="confirmed").count()
        pending_count = Participation.objects.filter(status="pending").count()
    except (ImportError, AttributeError):
        try:
            from .models import RSVP
            has_participation_model = True
            confirmed_count = RSVP.objects.filter(status="confirmed").count()
            pending_count = RSVP.objects.filter(status="pending").count()
        except (ImportError, AttributeError):
            has_participation_model = False
            # Placeholder stats until Participation/RSVP model is created in models.py:
            # Real query: confirmed_count = Participation.objects.filter(status="confirmed").count()
            # Real query: pending_count = Participation.objects.filter(status="pending").count()
            confirmed_count = None
            pending_count = None

    # Safe Admin Changelist URLs for Quick Links
    try:
        users_admin_url = reverse("admin:auth_user_changelist")
    except NoReverseMatch:
        users_admin_url = "/admin/auth/user/"

    try:
        activities_admin_url = reverse("admin:WebApp_Project_activity_changelist")
    except NoReverseMatch:
        activities_admin_url = "/admin/"

    try:
        participations_admin_url = reverse("admin:WebApp_Project_participation_changelist")
    except NoReverseMatch:
        participations_admin_url = "/admin/"

    context = {
        "total_users": total_users,
        "recent_users": recent_users,
        "has_activity_model": has_activity_model,
        "total_activities": total_activities,
        "cancelled_activities": cancelled_activities,
        "recent_activities": recent_activities,
        "has_participation_model": has_participation_model,
        "confirmed_count": confirmed_count,
        "pending_count": pending_count,
        "users_admin_url": users_admin_url,
        "activities_admin_url": activities_admin_url,
        "participations_admin_url": participations_admin_url,
    }
    return render(request, "staff/dashboard.html", context)

