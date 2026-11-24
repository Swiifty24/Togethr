import pymysql
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the MySQL/MariaDB database named in DB_NAME (default: togethr) if it doesn't exist yet."

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        name = db["NAME"]
        if not name.replace("_", "").isalnum():
            raise CommandError("DB_NAME may only contain letters, numbers and underscores.")
        try:
            connection = pymysql.connect(
                host=db["HOST"], port=int(db["PORT"] or 3306), user=db["USER"], password=db["PASSWORD"],
            )
        except pymysql.MySQLError as exc:
            raise CommandError(
                f"Could not connect to MySQL at {db['HOST']}:{db['PORT']} as '{db['USER']}': {exc}\n"
                "Is MySQL running (XAMPP control panel) and are DB_USER / DB_PASSWORD correct?"
            )
        with connection, connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        self.stdout.write(self.style.SUCCESS(f"Database '{name}' is ready."))
