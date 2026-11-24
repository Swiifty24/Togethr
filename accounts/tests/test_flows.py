import re
from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import ActivityLog, EmailVerification, User
from accounts.services import hash_code

STRONG = "Tr33house!Sky"


def register(client, **over):
    data = {"full_name": "Jessa Flores", "username": "jessa", "email": "Jessa@Example.com",
            "password1": STRONG, "password2": STRONG}
    data.update(over)
    return client.post(reverse("accounts:register"), data)


def last_code():
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


class RegistrationTests(TestCase):
    def test_register_creates_inactive_unverified_user_and_sends_code(self):
        r = register(self.client)
        self.assertRedirects(r, reverse("accounts:verify"))
        u = User.objects.get(username="jessa")
        self.assertFalse(u.is_active)
        self.assertFalse(u.email_verified)
        self.assertEqual(u.email, "jessa@example.com")
        self.assertNotEqual(u.password, STRONG)
        self.assertTrue(u.password.startswith("pbkdf2_"))
        self.assertTrue(hasattr(u, "profile"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["jessa@example.com"])

    def test_password_policy_enforced_server_side(self):
        for bad in ["Sh0rt!A", "alllowercase1!", "ALLUPPERCASE1!", "NoNumbers!!", "NoSpecial123A", "Password1!x", "12345678"]:
            r = register(self.client, password1=bad, password2=bad)
            self.assertEqual(r.status_code, 200, bad)
            self.assertFalse(User.objects.exists(), bad)

    def test_mismatch_and_duplicates(self):
        self.assertEqual(register(self.client, password2="Different1!x").status_code, 200)
        register(self.client)
        self.client.logout()
        r = register(self.client, username="JESSA", email="other@example.com")
        self.assertContains(r, "already taken")
        r = register(self.client, username="other", email="JESSA@example.com")
        self.assertContains(r, "already exists")
        self.assertEqual(User.objects.count(), 1)


class VerificationTests(TestCase):
    def setUp(self):
        register(self.client)
        self.user = User.objects.get(username="jessa")

    def test_correct_code_activates_then_cannot_be_reused(self):
        code = last_code()
        r = self.client.post(reverse("accounts:verify"), {"code": code})
        self.assertContains(r, "all set")
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active and self.user.email_verified)
        self.assertTrue(EmailVerification.objects.get().consumed_at)
        self.assertEqual(self.client.post(reverse("accounts:verify"), {"code": code}).status_code, 302)  # session cleared

    def test_wrong_code_attempt_limit_locks_code(self):
        good = last_code()
        wrong = "000000" if good != "000000" else "111111"
        for _ in range(5):
            r = self.client.post(reverse("accounts:verify"), {"code": wrong})
        self.assertContains(r, "Too many incorrect")
        r = self.client.post(reverse("accounts:verify"), {"code": good})
        self.assertNotContains(r, "all set")
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_expired_code_rejected(self):
        EmailVerification.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        r = self.client.post(reverse("accounts:verify"), {"code": last_code()})
        self.assertContains(r, "expired")
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_resend_cooldown_then_new_code_invalidates_old(self):
        old = last_code()
        self.client.post(reverse("accounts:resend_code"))
        self.assertEqual(len(mail.outbox), 1)  # blocked by cooldown
        EmailVerification.objects.update(created_at=timezone.now() - timedelta(minutes=2))
        self.client.post(reverse("accounts:resend_code"))
        self.assertEqual(len(mail.outbox), 2)
        new = last_code()
        if new != old:
            r = self.client.post(reverse("accounts:verify"), {"code": old})
            self.assertNotContains(r, "all set")
        r = self.client.post(reverse("accounts:verify"), {"code": new})
        self.assertContains(r, "all set")

    def test_cannot_verify_someone_elses_account(self):
        code = last_code()
        other = self.client_class()
        r = other.post(reverse("accounts:verify"), {"code": code})
        self.assertRedirects(r, reverse("accounts:login"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_code_stored_hashed(self):
        v = EmailVerification.objects.get()
        self.assertNotIn(last_code(), v.code_hash)
        self.assertEqual(v.code_hash, hash_code(self.user.pk, last_code()))


class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("sam", "sam@example.com", STRONG, full_name="Sam Reyes")

    def login(self, ident="sam", pw=STRONG, **extra):
        return self.client.post(reverse("accounts:login"), {"identifier": ident, "password": pw, **extra})

    def test_login_by_username_or_email_and_redirect_by_role(self):
        self.assertRedirects(self.login(), reverse("activities:home"))
        self.client.post(reverse("accounts:logout"))
        self.assertRedirects(self.login("SAM@example.com"), reverse("activities:home"))
        self.client.post(reverse("accounts:logout"))
        User.objects.create_superuser("root", "root@example.com", STRONG, full_name="Root")
        self.assertRedirects(self.login("root"), reverse("adminpanel:home"))

    def test_unverified_cannot_login_and_gets_new_code(self):
        u = User.objects.create(username="new", email="new@example.com", full_name="New", is_active=False, email_verified=False)
        u.set_password(STRONG); u.save()
        r = self.login("new")
        self.assertRedirects(r, reverse("accounts:verify"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(len(mail.outbox), 1)

    def test_deactivated_cannot_login(self):
        self.user.is_active = False; self.user.save()
        self.assertContains(self.login(), "deactivated")

    def test_wrong_password_generic_and_lockout(self):
        for _ in range(5):
            r = self.login(pw="Wrong-pass1!")
        self.assertContains(r, "Incorrect")
        r = self.login()  # right password but locked
        self.assertContains(r, "Too many failed attempts")
        self.assertEqual(ActivityLog.objects.filter(action=ActivityLog.LOGIN_FAILED).count(), 5)

    def test_logout_ends_session_and_requires_post(self):
        self.login()
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.client.post(reverse("accounts:logout"))
        self.assertRedirects(self.client.get(reverse("activities:home")), f"{reverse('accounts:login')}?next={reverse('activities:home')}")

    def test_open_redirect_blocked(self):
        r = self.login(next="https://evil.example/")
        self.assertRedirects(r, reverse("activities:home"))


class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("sam", "sam@example.com", STRONG, full_name="Sam Reyes")

    def test_full_reset_flow(self):
        r = self.client.post(reverse("accounts:password_reset"), {"email": "sam@example.com"})
        self.assertRedirects(r, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        link = re.search(r"http://\S+/accounts/password-reset/\S+/\S+/", mail.outbox[0].body).group(0)
        r = self.client.get(link, follow=True)
        post_url = r.redirect_chain[-1][0]
        self.assertEqual(self.client.post(post_url, {"new_password1": "weak", "new_password2": "weak"}).status_code, 200)
        r = self.client.post(post_url, {"new_password1": "Brand#NewPass9x", "new_password2": "Brand#NewPass9x"})
        self.assertRedirects(r, reverse("accounts:password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Brand#NewPass9x"))
        self.assertContains(self.client.get(link, follow=True), "can't be used")  # single use

    def test_unknown_email_gives_same_response_no_mail(self):
        r = self.client.post(reverse("accounts:password_reset"), {"email": "nobody@example.com"})
        self.assertRedirects(r, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)


class MemberPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("sam", "sam@example.com", STRONG, full_name="Sam Reyes")
        self.client.force_login(self.user)

    def test_pages_render(self):
        for name in ["profile", "settings"]:
            self.assertEqual(self.client.get(reverse(f"members:{name}")).status_code, 200, name)

    def test_profile_update(self):
        r = self.client.post(reverse("members:profile"), {"full_name": "Sam R", "username": "samr", "location": "Zamboanga", "bio": "Hi"})
        self.assertRedirects(r, reverse("members:profile"))
        self.user.refresh_from_db()
        self.assertEqual((self.user.full_name, self.user.username, self.user.profile.location), ("Sam R", "samr", "Zamboanga"))

    def test_change_password_keeps_session_and_validates(self):
        bad = self.client.post(reverse("members:settings"), {"old_password": STRONG, "new_password1": "weakpass", "new_password2": "weakpass"})
        self.assertEqual(bad.status_code, 200)
        ok = self.client.post(reverse("members:settings"), {"old_password": STRONG, "new_password1": "Another#Pass42", "new_password2": "Another#Pass42"})
        self.assertRedirects(ok, reverse("members:settings"))
        self.assertEqual(self.client.get(reverse("activities:home")).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Another#Pass42"))


class AdminAccessTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("root", "root@example.com", STRONG, full_name="Root Admin")
        self.member = User.objects.create_user("sam", "sam@example.com", STRONG, full_name="Sam Reyes")
        self.urls = [reverse("adminpanel:home"), reverse("adminpanel:user_list"), reverse("adminpanel:user_create"),
                     reverse("adminpanel:user_detail", args=[self.admin.pk]), reverse("adminpanel:user_edit", args=[self.admin.pk])]

    def test_anonymous_redirected_member_forbidden(self):
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 302, url)
        self.client.force_login(self.member)
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        for name in ["user_toggle_active", "user_delete"]:
            self.assertEqual(self.client.post(reverse(f"adminpanel:{name}", args=[self.admin.pk])).status_code, 403)
        self.assertEqual(self.client.get("/django-admin/").status_code, 302)  # not staff

    def test_admin_pages_and_user_management(self):
        self.client.force_login(self.admin)
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertContains(self.client.get(reverse("adminpanel:user_list") + "?q=sam&status=active"), "Sam Reyes")
        r = self.client.post(reverse("adminpanel:user_create"), {
            "full_name": "New Person", "username": "newp", "email": "newp@example.com", "role": "member",
            "is_active": "on", "email_verified": "on", "password1": "Created#Pass77", "password2": "Created#Pass77"})
        created = User.objects.get(username="newp")
        self.assertRedirects(r, reverse("adminpanel:user_detail", args=[created.pk]))
        self.assertTrue(created.email_verified and created.is_active and not created.is_superuser)
        self.client.post(reverse("adminpanel:user_toggle_active", args=[created.pk]))
        created.refresh_from_db(); self.assertFalse(created.is_active)
        self.client.post(reverse("adminpanel:user_edit", args=[created.pk]), {
            "full_name": "New Person", "username": "newp", "email": "newp@example.com", "role": "super_admin",
            "is_active": "on", "email_verified": "on"})
        created.refresh_from_db(); self.assertTrue(created.is_superuser and created.is_staff)
        self.assertTrue(ActivityLog.objects.filter(action=ActivityLog.ADMIN_ROLE_CHANGED).exists())
        self.assertEqual(self.client.get(reverse("adminpanel:user_delete", args=[created.pk])).status_code, 200)
        self.assertTrue(User.objects.filter(pk=created.pk).exists())  # GET doesn't delete
        self.client.post(reverse("adminpanel:user_delete", args=[created.pk]))
        self.assertFalse(User.objects.filter(pk=created.pk).exists())

    def test_cannot_delete_or_deactivate_self_or_demote_last_admin(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("adminpanel:user_delete", args=[self.admin.pk]))
        self.client.post(reverse("adminpanel:user_toggle_active", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        r = self.client.post(reverse("adminpanel:user_edit", args=[self.admin.pk]), {
            "full_name": "Root", "username": "root", "email": "root@example.com", "role": "member",
            "is_active": "on", "email_verified": "on"})
        self.assertEqual(r.status_code, 200)
        self.admin.refresh_from_db(); self.assertTrue(self.admin.is_superuser)


class ErrorPageTests(TestCase):
    def test_404_custom(self):
        r = self.client.get("/does-not-exist/")
        self.assertContains(r, "Page not found", status_code=404)

    def test_landing(self):
        self.assertContains(self.client.get("/"), "Better when we")
