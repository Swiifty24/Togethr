import calendar as pycal
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Case, Count, F, IntegerField, Q, When
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from accounts.models import User

from . import services
from .forms import ActivityForm, DiscoveryFilterForm
from .models import Activity, Category, Participation
from .services import ActivityError

TABS = [
    ("all", "All"), ("created", "Created by me"), ("joined", "Joined"),
    ("upcoming", "Upcoming"), ("completed", "Completed"), ("canceled", "Canceled"),
]


# ---- helpers ---------------------------------------------------------------
def _with_people(qs):
    return qs.select_related("organizer__profile", "category").with_counts()


def _attach_my_response(activities, user):
    activities = list(activities)
    mine = dict(Participation.objects.filter(user=user, activity_id__in=[a.pk for a in activities])
                .values_list("activity_id", "response"))
    labels = dict(Participation.RESPONSE_CHOICES)
    for a in activities:
        a.my_response = mine.get(a.pk)
        a.my_response_label = labels.get(a.my_response, "")
        a.is_mine = a.organizer_id == user.pk
    return activities


def _joined_ids(user):
    return Participation.objects.filter(user=user, response=Participation.JOIN).values("activity_id")


def _mine(user):
    """Activities the user organizes or has joined (sub-query, so counts stay correct)."""
    return Activity.objects.filter(Q(organizer=user) | Q(pk__in=_joined_ids(user)))


def _next(request, fallback):
    target = request.POST.get("next") or ""
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return target
    return fallback


def _get_visible(request, pk):
    activity = get_object_or_404(_with_people(Activity.objects.all()), pk=pk)
    user = request.user
    if activity.visibility == Activity.INVITE_ONLY and not (
        activity.organizer_id == user.pk or user.is_superuser
        or Participation.objects.filter(activity=activity, user=user).exists()
    ):
        raise Http404
    return activity


def _get_owned(request, pk):
    activity = get_object_or_404(_with_people(Activity.objects.all()), pk=pk)
    if activity.organizer_id != request.user.pk:
        raise Http404  # don't reveal other people's invite-only plans
    return activity


# ---- Home: discovery -------------------------------------------------------
@login_required
@never_cache
def home(request):
    services.sync_statuses()
    user = request.user
    today = timezone.localdate()
    filters = DiscoveryFilterForm(request.GET or None)
    if filters.is_bound:
        filters.is_valid()

    base = _with_people(Activity.objects.discoverable().filter(date__gte=today).exclude(organizer=user))
    explore = base
    if filters.is_bound:
        d = filters.cleaned_data
        if d.get("q"):
            explore = explore.filter(Q(title__icontains=d["q"]) | Q(description__icontains=d["q"]))
        if d.get("category"):
            explore = explore.filter(category=d["category"])
        if d.get("date"):
            explore = explore.filter(date=d["date"])
        if d.get("location"):
            explore = explore.filter(location__icontains=d["location"])
        if d.get("availability") == "open":
            explore = explore.filter(Q(max_participants__isnull=True) | Q(joined_count__lt=F("max_participants")))
    page = Paginator(explore.order_by("date", "start_time", "pk"), 9).get_page(request.GET.get("page"))
    page.object_list = _attach_my_response(page.object_list, user)

    upcoming = _attach_my_response(
        _with_people(_mine(user).filter(status__in=Activity.OPEN_STATUSES, date__gte=today)).order_by("date", "start_time")[:4],
        user,
    )

    seen = [a.pk for a in page.object_list] + [a.pk for a in upcoming]
    liked = set(_mine(user).values_list("category_id", flat=True)) - {None}
    suggested = _attach_my_response(
        base.exclude(pk__in=seen).exclude(participations__user=user)
        .annotate(match=Case(When(category_id__in=liked, then=0), default=1, output_field=IntegerField()))
        .order_by("match", "date", "start_time")[:6],
        user,
    )
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "activities/home.html", {
        "filters": filters, "filters_active": filters.is_bound and filters.is_active,
        "categories": Category.objects.all(), "page": page, "upcoming": upcoming, "suggested": suggested,
        "querystring": query.urlencode(),
    })


# ---- My activities ---------------------------------------------------------
@login_required
@never_cache
def my_activities(request):
    services.sync_statuses()
    user, today = request.user, timezone.localdate()
    tab = request.GET.get("tab", "all")
    if tab not in dict(TABS):
        tab = "all"
    if tab == "created":
        qs = Activity.objects.filter(organizer=user)
    elif tab == "joined":
        qs = Activity.objects.filter(pk__in=_joined_ids(user)).exclude(organizer=user)
    else:
        qs = _mine(user)
    if tab == "upcoming":
        qs = qs.filter(status__in=Activity.OPEN_STATUSES, date__gte=today)
    elif tab == "completed":
        qs = qs.filter(status=Activity.COMPLETED)
    elif tab == "canceled":
        qs = qs.filter(status=Activity.CANCELED)
    past_first = tab in ("completed", "canceled")
    qs = _with_people(qs).order_by("-date", "-start_time") if past_first else _with_people(qs).order_by("date", "start_time")
    page = Paginator(qs, 12).get_page(request.GET.get("page"))
    page.object_list = _attach_my_response(page.object_list, user)
    return render(request, "activities/my_activities.html", {"tabs": TABS, "tab": tab, "page": page})


# ---- Create / edit / cancel -----------------------------------------------
@login_required
@never_cache
def create(request):
    form = ActivityForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        activity = form.save(commit=False)
        activity.organizer = request.user
        activity.save()
        messages.success(request, "Your activity is live! Invite some friends to get things going.")
        return redirect("activities:detail", pk=activity.pk)
    return render(request, "activities/activity_form.html", {"form": form, "activity": None})


@login_required
@never_cache
def edit(request, pk):
    activity = _get_owned(request, pk)
    if activity.status not in Activity.OPEN_STATUSES or activity.has_ended:
        messages.error(request, "This activity can't be edited any more.")
        return redirect("activities:detail", pk=pk)
    before = {f: getattr(activity, f) for f in ("date", "start_time", "end_time", "location")}
    form = ActivityForm(request.POST or None, request.FILES or None, instance=activity)
    if request.method == "POST" and form.is_valid():
        activity = form.save()
        labels = []
        if before["date"] != activity.date or before["start_time"] != activity.start_time or before["end_time"] != activity.end_time:
            labels.append("date or time")
        if before["location"] != activity.location:
            labels.append("location")
        services.recalculate_status(activity)
        services.notify_changes(activity, labels)
        messages.success(request, "Your changes were saved.")
        return redirect("activities:detail", pk=pk)
    return render(request, "activities/activity_form.html", {"form": form, "activity": activity})


@login_required
@never_cache
def cancel(request, pk):
    activity = _get_owned(request, pk)
    if request.method == "POST":
        try:
            services.cancel_activity(activity, request.user)
        except ActivityError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "The activity was canceled and everyone involved was notified.")
        return redirect("activities:detail", pk=pk)
    return render(request, "activities/activity_cancel.html", {"activity": activity})


# ---- Detail, participants --------------------------------------------------
@login_required
@never_cache
def detail(request, pk):
    services.sync_statuses()
    activity = _get_visible(request, pk)
    user = request.user
    mine = Participation.objects.filter(activity=activity, user=user).first()
    is_organizer = activity.organizer_id == user.pk
    people = activity.participations.select_related("user__profile")
    joined = [p for p in people if p.response == Participation.JOIN]
    return render(request, "activities/activity_detail.html", {
        "activity": activity, "my_part": mine, "is_organizer": is_organizer,
        "joined": joined[:12], "joined_total": len(joined),
        "can_respond": not is_organizer and activity.is_open and (mine is not None or activity.visibility == Activity.PUBLIC),
        "pending_replies": sum(1 for p in people if p.response == Participation.INVITED),
    })


@login_required
@never_cache
def participants(request, pk):
    services.sync_statuses()
    activity = _get_visible(request, pk)
    is_organizer = activity.organizer_id == request.user.pk
    people = list(activity.participations.select_related("user__profile"))
    groups = [
        ("Going", Participation.JOIN), ("Not sure", Participation.NOT_SURE),
        ("Waiting for a reply", Participation.INVITED), ("Can't join", Participation.CANT_JOIN),
    ]
    grouped = [(label, [p for p in people if p.response == key]) for label, key in groups]
    candidates, q = [], request.GET.get("q", "").strip()
    can_invite = is_organizer and activity.is_open
    if can_invite and len(q) >= 2:
        taken = [p.user_id for p in people] + [request.user.pk]
        candidates = list(
            User.objects.filter(is_active=True, email_verified=True)
            .filter(Q(username__icontains=q) | Q(full_name__icontains=q))
            .exclude(pk__in=taken).select_related("profile").order_by("full_name")[:10]
        )
    return render(request, "activities/participants.html", {
        "activity": activity, "grouped": grouped, "is_organizer": is_organizer, "can_invite": can_invite,
        "q": q, "candidates": candidates, "total": len(people),
    })


@login_required
@require_POST
def invite(request, pk):
    activity = _get_owned(request, pk)
    if not activity.is_open:
        messages.error(request, "This activity is no longer open for invitations.")
        return redirect("activities:participants", pk=pk)
    ids = [int(i) for i in request.POST.getlist("user_ids") if i.isdigit()]
    users = User.objects.filter(pk__in=ids, is_active=True, email_verified=True)
    count = services.invite_users(activity, request.user, users)
    if count:
        messages.success(request, f"Invited {count} {'person' if count == 1 else 'people'}.")
    else:
        messages.info(request, "Nobody new was invited. Pick at least one person from the search results.")
    return redirect("activities:participants", pk=pk)


@login_required
@require_POST
def remove_participant(request, pk, participation_pk):
    activity = _get_owned(request, pk)
    participation = get_object_or_404(Participation, pk=participation_pk, activity=activity)
    services.remove_participant(activity, participation)
    messages.success(request, f"{participation.user.get_full_name()} was removed.")
    return redirect("activities:participants", pk=pk)


# ---- Responding ------------------------------------------------------------
def _respond(request, pk, response, success):
    try:
        services.set_response(pk, request.user, response)
    except ActivityError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, success)
    return redirect(_next(request, redirect("activities:detail", pk=pk).url))


@login_required
@require_POST
def join(request, pk):
    return _respond(request, pk, Participation.JOIN, "You're in! See you there.")


@login_required
@require_POST
def respond(request, pk):
    response = request.POST.get("response", "")
    texts = {Participation.JOIN: "You're in! See you there.", Participation.CANT_JOIN: "Got it. You can't join.",
             Participation.NOT_SURE: "Marked as not sure. You can change this any time."}
    if response not in texts:
        messages.error(request, "Please choose Join, Can't Join or Not Sure.")
        return redirect("activities:detail", pk=pk)
    return _respond(request, pk, response, texts[response])


@login_required
@require_POST
def leave(request, pk):
    try:
        services.leave_activity(pk, request.user)
    except ActivityError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "You left the activity.")
    return redirect(_next(request, redirect("activities:detail", pk=pk).url))


# ---- Invitations -----------------------------------------------------------
@login_required
@never_cache
def invitations(request):
    services.sync_statuses()
    tab = request.GET.get("tab", "waiting")
    qs = Participation.objects.filter(user=request.user, invited_by__isnull=False).select_related(
        "activity__organizer__profile", "activity__category", "invited_by"
    ).annotate(
        activity_joined_count=Count(
            "activity__participations",
            filter=Q(activity__participations__response=Participation.JOIN),
            distinct=True,
        )
    )
    if tab == "waiting":
        qs = qs.filter(response=Participation.INVITED, activity__status__in=Activity.OPEN_STATUSES)
    else:
        tab = "all"
    page = Paginator(qs.order_by("-created_at"), 10).get_page(request.GET.get("page"))
    for item in page.object_list:
        item.activity.joined_count = item.activity_joined_count
    return render(request, "activities/invitations.html", {"page": page, "tab": tab})


# ---- Calendar --------------------------------------------------------------
@login_required
@never_cache
def calendar_view(request):
    services.sync_statuses()
    today = timezone.localdate()
    try:
        year, month = (int(x) for x in request.GET.get("month", "").split("-"))
        first = date(year, month, 1)
    except (ValueError, TypeError):
        first = today.replace(day=1)
    weeks_dates = pycal.Calendar(firstweekday=6).monthdatescalendar(first.year, first.month)
    start, end = weeks_dates[0][0], weeks_dates[-1][-1]

    user = request.user
    responses = dict(Participation.objects.filter(user=user, activity__date__range=(start, end))
                     .values_list("activity_id", "response"))
    activities = Activity.objects.filter(date__range=(start, end)).filter(
        Q(organizer=user) | Q(pk__in=list(responses))
    ).exclude(status=Activity.CANCELED).select_related("category").order_by("start_time")
    by_day, agenda = {}, []
    for a in activities:
        if a.organizer_id == user.pk:
            kind = "organizer"
        else:
            kind = {"join": "joined", "not_sure": "maybe", "invited": "invited"}.get(responses.get(a.pk))
        if kind is None:
            continue
        a.kind = kind
        by_day.setdefault(a.date, []).append(a)
        if a.date.month == first.month:
            agenda.append(a)
    weeks = [[{"date": d, "in_month": d.month == first.month, "is_today": d == today, "items": by_day.get(d, [])}
              for d in week] for week in weeks_dates]
    return render(request, "activities/calendar.html", {
        "weeks": weeks, "month": first, "agenda": sorted(agenda, key=lambda a: (a.date, a.start_time)),
        "prev": _shift_month(first, -1), "next": _shift_month(first, 1), "today_month": today.replace(day=1),
        "weekdays": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    })


def _shift_month(first, delta):
    index = first.year * 12 + first.month - 1 + delta
    return date(index // 12, index % 12 + 1, 1)
