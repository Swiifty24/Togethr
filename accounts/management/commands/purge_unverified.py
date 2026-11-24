from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User


class Command(BaseCommand):
    help = "Delete self-registered accounts that never verified their email (frees up their username/email)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7, help="Delete unverified accounts older than N days (default 7).")
        parser.add_argument("--dry-run", action="store_true", help="Only report what would be deleted.")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options["days"])
        stale = User.objects.filter(email_verified=False, is_superuser=False, date_joined__lt=cutoff)
        count = stale.count()
        if options["dry_run"]:
            self.stdout.write(f"{count} unverified account(s) would be deleted.")
            return
        stale.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} unverified account(s)."))
