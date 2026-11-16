---
name: web-privacy-auth
description: "Use when adding login, sign up, a welcome page, permissions, private pages, share links, forms, or file uploads to a Django website so private data stays private."
---

# Login, privacy, and safe forms

## Decide what is public
List each page as public, logged-in, owner-only, or staff-only and record it in
AGENTS.md. Default to private. For personal or friends-only content, the first page is
a public welcome page (name, pitch, Sign Up, Log In), never a feed of real user content.

## Entry flow
    # settings.py
    LOGIN_URL = "login"
    LOGIN_REDIRECT_URL = "home"
    LOGOUT_REDIRECT_URL = "welcome"

    def welcome(request):
        if request.user.is_authenticated:
            return redirect("home")
        return render(request, "welcome.html")

Use Django's LoginView, LogoutView, and UserCreationForm. Never hand-write password
handling. Put @login_required on every private view.

## Object-level access
Being logged in is not enough. Check ownership in the view:

    def can_view(user, obj):
        return obj.owner_id == user.id or obj.members.filter(pk=user.pk).exists()

    obj = get_object_or_404(Thing, pk=pk)
    if not can_view(request.user, obj):
        raise Http404   # 404 so we do not confirm it exists

Only the owner edits or deletes. Share links use a random UUID token, not the id.

## Forms and requests
Changes use POST with {% csrf_token %}. Use the ORM, never raw SQL from user input.
Never use |safe on user text. Validate on the server in clean().

## Uploads
MEDIA_URL = "/media/" and MEDIA_ROOT = BASE_DIR / "media". ImageField needs Pillow.
Forms need enctype="multipart/form-data" and request.FILES. Limit size (about 2 MB) and
type. Add media/ to .gitignore.

## Secrets
Never paste real keys or passwords into prompts or Git. DEBUG = True only for
development. Do not loosen ALLOWED_HOSTS or CSRF settings to silence an error.

## Checklist
Logged out, open each private URL: it must redirect to login. As user B, open user A's
record by id: it must return 404. State-changing forms must reject GET.