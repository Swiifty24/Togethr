import string

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class PasswordComplexityValidator:
    """
    Enforces Togethr's password policy on the server. The browser-side checklist
    (static/js/password.js) mirrors these exact rules for instant feedback, but
    this validator is the authority.

    Django's own MinimumLength (8), CommonPassword, Numeric and
    UserAttributeSimilarity validators run alongside this one.
    """

    # Easily guessed fragments that make an otherwise "complex" password weak
    # (for example "Password1!"). Keep in sync with nothing: the template tag
    # passes this tuple to the browser so there is a single source of truth.
    WEAK_FRAGMENTS = (
        "password",
        "passw0rd",
        "qwerty",
        "123456",
        "abcdef",
        "letmein",
        "welcome",
        "iloveyou",
        "admin",
        "togethr",
    )

    def validate(self, password, user=None):
        errors = []
        if not any(c in string.ascii_uppercase for c in password):
            errors.append(ValidationError(
                _("Your password must contain at least one uppercase letter (A–Z)."),
                code="password_no_upper",
            ))
        if not any(c in string.ascii_lowercase for c in password):
            errors.append(ValidationError(
                _("Your password must contain at least one lowercase letter (a–z)."),
                code="password_no_lower",
            ))
        if not any(c in string.digits for c in password):
            errors.append(ValidationError(
                _("Your password must contain at least one number (0–9)."),
                code="password_no_digit",
            ))
        if not any(c in string.punctuation for c in password):
            errors.append(ValidationError(
                _("Your password must contain at least one special character (for example @ # $ % ! &)."),
                code="password_no_special",
            ))
        lowered = password.lower()
        if any(fragment in lowered for fragment in self.WEAK_FRAGMENTS):
            errors.append(ValidationError(
                _("Your password contains a common, easily guessed word or pattern."),
                code="password_weak_pattern",
            ))
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _(
            "Your password must contain an uppercase letter, a lowercase letter, "
            "a number and a special character, and must not contain common words or patterns."
        )
