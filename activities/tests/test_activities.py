import io
from datetime import timedelta

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Notification, User
from activities import services
from activities.models import Activity, Category, Participation

PW = "Tr33house!Sky"


def make_user(name):
    return User.objects.create_user(name, f"{name}@example.com", PW, full_name=name.title())


def make_activity(organizer, **kw):
    when = timezone.localtime() + timedelta(days=3)
    data = dict(organizer=organizer, title="Beach day", description="Bring snacks", date=when.date(),
                start_time=when.time().replace(microsecond=0), location="Sta. Cruz", min_participants=2,
                category=Category.objects.first())
    data.update(kw)
    return Activity.objects.create(**data)


class StatusRuleTests(TestCase):
    def setUp(self):
        self.org = make_user("olive")
        self.people = [make_user(f"p{i}") for i in range(4)]
        self.act = make_activity(self.org, min_participants=2, max_participants=3)

    def refresh(self):
        self.act.refresh_from_db()
        return self.act.status

    def test_reaches_minimum_confirms_and_notifies_then_drops_back(self):
        services.set_response(self.act.pk, self.people[0], "join")
        self.assertEqual(self.refresh(), "pending")
        services.set_response(self.act.pk, self.people[1], "join")
        self.assertEqual(self.refresh(), "confirmed")
        self.assertTrue(Notification.objects.filter(user=self.people[0], title="Activity confirmed").exists())
        services.set_response(self.act.pk, self.people[1], "cant_join")  # change of mind
        self.assertEqual(self.refresh(), "pending")
        self.assertTrue(Notification.objects.filter(user=self.org, title="Back to pending").exists())

    def test_not_sure_and_cant_join_dont_count(self):
        services.set_response(self.act.pk, self.people[0], "not_sure")
        services.set_response(self.act.pk, self.people[1], "cant_join")
        self.assertEqual(Activity.objects.with_counts().get(pk=self.act.pk).joined_count, 0)

    def test_capacity_enforced_and_no_duplicates(self):
        for p in self.people[:3]:
            services.set_response(self.act.pk, p, "join")
        with self.assertRaises(services.ActivityError):
            services.set_response(self.act.pk, self.people[3], "join")
        services.set_response(self.act.pk, self.people[0], "join")  # same answer again is harmless
        self.assertEqual(Participation.objects.filter(activity=self.act).count(), 3)

    def test_organizer_cannot_join_and_canceled_is_closed(self):
        with self.assertRaises(services.ActivityError):
            services.set_response(self.act.pk, self.org, "join")
        services.cancel_activity(self.act, self.org)
        with self.assertRaises(services.ActivityError):
            services.set_response(self.act.pk, self.people[0], "join")

    def test_cancel_notifies_everyone(self):
        services.invite_users(self.act, self.org, [self.people[0]])
        services.set_response(self.act.pk, self.people[1], "join")
        services.cancel_activity(self.act, self.org)
        for p in self.people[:2]:
            self.assertTrue(Notification.objects.filter(user=p, title="Activity canceled").exists())

    def test_past_activities_resolve(self):
        past = timezone.localtime() - timedelta(days=1)
        done = make_activity(self.org, title="Done", date=past.date(), start_time=past.time(), status="confirmed")
        missed = make_activity(self.org, title="Missed", date=past.date(), start_time=past.time())
        services.sync_statuses()
        done.refresh_from_db(); missed.refresh_from_db()
        self.assertEqual((done.status, missed.status), ("completed", "canceled"))


class ActivityViewTests(TestCase):
    def setUp(self):
        self.org, self.sam, self.lee = make_user("olive"), make_user("sam"), make_user("lee")
        self.act = make_activity(self.org, title="Sunset hike", description="Bring water")

    def test_login_redirects_to_home_and_pages_render(self):
        r = self.client.post(reverse("accounts:login"), {"identifier": "sam", "password": PW})
        self.assertRedirects(r, reverse("activities:home"))
        for name in ["home", "my_activities", "create", "invitations", "calendar"]:
            self.assertEqual(self.client.get(reverse(f"activities:{name}")).status_code, 200, name)
        for name in ["notifications", "profile", "settings"]:
            self.assertEqual(self.client.get(reverse(f"members:{name}")).status_code, 200, name)
        page = self.client.get(reverse("activities:home"))
        self.assertNotContains(page, "ashboard")
        self.assertContains(page, "Welcome back, Sam")

    def test_home_discovery_search_filters_and_excludes_own(self):
        make_activity(self.sam, title="Sam's own plan")
        self.client.force_login(self.sam)
        page = self.client.get(reverse("activities:home"))
        self.assertContains(page, "Sunset hike")
        self.assertNotContains(page, "Sam's own plan")
        self.assertContains(self.client.get(reverse("activities:home") + "?q=water"), "Sunset hike")
        self.assertContains(self.client.get(reverse("activities:home") + "?q=zzzz"), "Nothing matches your search")
        self.assertContains(self.client.get(reverse("activities:home") + "?location=Nowhere"), "Nothing matches your search")
        self.assertContains(self.client.get(reverse("activities:home") + "?location=cruz&category=" + self.act.category.slug), "1 available")

    def test_join_button_flow_and_my_activities(self):
        self.client.force_login(self.sam)
        r = self.client.post(reverse("activities:join", args=[self.act.pk]), {"next": reverse("activities:home")})
        self.assertRedirects(r, reverse("activities:home"))
        self.assertTrue(Participation.objects.filter(activity=self.act, user=self.sam, response="join").exists())
        self.assertContains(self.client.get(reverse("activities:my_activities") + "?tab=joined"), "Sunset hike")
        self.assertContains(self.client.get(reverse("activities:home")), "Your upcoming activities")
        self.client.post(reverse("activities:leave", args=[self.act.pk]))
        self.assertFalse(Participation.objects.filter(activity=self.act, user=self.sam).exists())

    def test_invite_only_hidden_from_strangers_and_open_redirect_blocked(self):
        secret = make_activity(self.org, title="Secret", visibility="invite_only")
        self.client.force_login(self.sam)
        self.assertEqual(self.client.get(reverse("activities:detail", args=[secret.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("activities:home")), "Secret")
        self.assertEqual(self.client.post(reverse("activities:join", args=[secret.pk])).status_code, 302)
        self.assertFalse(Participation.objects.filter(activity=secret, user=self.sam).exists())
        r = self.client.post(reverse("activities:join", args=[self.act.pk]), {"next": "https://evil.example/"})
        self.assertRedirects(r, reverse("activities:detail", args=[self.act.pk]))

    def test_invitation_flow(self):
        self.client.force_login(self.org)
        r = self.client.get(reverse("activities:participants", args=[self.act.pk]) + "?q=lee")
        self.assertContains(r, "Lee")
        self.client.post(reverse("activities:invite", args=[self.act.pk]), {"user_ids": [self.lee.pk]})
        self.assertTrue(Notification.objects.filter(user=self.lee, title="You're invited!").exists())
        self.client.force_login(self.lee)
        self.assertContains(self.client.get(reverse("activities:invitations")), "Sunset hike")
        self.client.post(reverse("activities:respond", args=[self.act.pk]), {"response": "not_sure"})
        self.assertEqual(Participation.objects.get(user=self.lee).response, "not_sure")
        self.assertNotContains(self.client.get(reverse("activities:invitations")), "Sunset hike")  # replied
        self.assertContains(self.client.get(reverse("activities:invitations") + "?tab=all"), "Sunset hike")

    def test_only_organizer_can_manage(self):
        self.client.force_login(self.sam)
        for name in ["edit", "cancel"]:
            self.assertEqual(self.client.post(reverse(f"activities:{name}", args=[self.act.pk])).status_code, 404, name)
        self.assertEqual(self.client.post(reverse("activities:invite", args=[self.act.pk]), {"user_ids": [self.lee.pk]}).status_code, 404)
        self.act.refresh_from_db(); self.assertEqual(self.act.status, "pending")

    def test_create_validates_and_saves_with_image(self):
        self.client.force_login(self.sam)
        url = reverse("activities:create")
        past = (timezone.localdate() - timedelta(days=1)).isoformat()
        cat = Category.objects.first().pk
        bad = self.client.post(url, {"title": "x", "description": "d", "category": cat, "date": past, "start_time": "10:00",
                                     "location": "Park", "min_participants": 5, "max_participants": 2, "visibility": "public"})
        self.assertContains(bad, "future")
        self.assertContains(bad, "can&#x27;t be lower")
        buf = io.BytesIO()
        Image.new("RGB", (40, 24), "#4B55C8").save(buf, "PNG")
        png = buf.getvalue()
        fake = self.client.post(url, {"title": "T", "description": "d", "category": cat, "date": (timezone.localdate() + timedelta(days=5)).isoformat(),
                                      "start_time": "18:00", "location": "x", "min_participants": 2, "visibility": "public",
                                      "cover_image": SimpleUploadedFile("evil.png", b"not an image", "image/png")})
        self.assertContains(fake, "valid image")
        future = (timezone.localdate() + timedelta(days=5)).isoformat()
        ok = self.client.post(url, {"title": "Board games", "description": "Bring one", "category": cat, "date": future,
                                    "start_time": "18:00", "end_time": "21:00", "location": "My place", "min_participants": 3,
                                    "visibility": "public", "cover_image": SimpleUploadedFile("c.png", png, "image/png")})
        made = Activity.objects.get(title="Board games")
        self.assertRedirects(ok, reverse("activities:detail", args=[made.pk]))
        self.assertEqual(made.organizer, self.sam)
        self.assertTrue(made.cover_image.name.startswith("activity_covers/"))
        made.cover_image.delete(save=False)

    def test_edit_notifies_on_change_and_calendar_renders(self):
        services.set_response(self.act.pk, self.sam, "join")
        self.client.force_login(self.org)
        data = {"title": self.act.title, "description": "Bring water", "category": self.act.category_id,
                "date": self.act.date.isoformat(), "start_time": self.act.start_time.strftime("%H:%M"),
                "location": "New meeting point", "min_participants": 2, "visibility": "public"}
        self.client.post(reverse("activities:edit", args=[self.act.pk]), data)
        self.assertTrue(Notification.objects.filter(user=self.sam, title="Activity updated").exists())
        month = self.act.date.strftime("%Y-%m")
        self.assertContains(self.client.get(reverse("activities:calendar") + f"?month={month}"), "Sunset hike")
        self.assertEqual(self.client.get(reverse("activities:calendar") + "?month=garbage").status_code, 200)

    def test_notifications_open_marks_read(self):
        note = Notification.objects.create(user=self.sam, title="Hi", url=reverse("activities:home"))
        self.client.force_login(self.sam)
        self.assertEqual(self.client.get(reverse("members:notification_open", args=[note.pk])).status_code, 405)
        self.assertRedirects(self.client.post(reverse("members:notification_open", args=[note.pk])), reverse("activities:home"))
        note.refresh_from_db(); self.assertTrue(note.is_read)
        other = Notification.objects.create(user=self.lee, title="Private")
        self.assertEqual(self.client.post(reverse("members:notification_open", args=[other.pk])).status_code, 404)
