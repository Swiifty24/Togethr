from datetime import datetime

from django import forms
from django.utils import timezone

from accounts.forms import StyledFormMixin

from .models import Activity, Category, Participation

MAX_IMAGE_MB = 5


class ActivityForm(StyledFormMixin, forms.ModelForm):
    remove_cover = forms.BooleanField(label="Remove the current cover image", required=False)

    class Meta:
        model = Activity
        fields = [
            "title", "description", "cover_image", "category", "date", "start_time", "end_time",
            "location", "min_participants", "max_participants", "visibility",
        ]
        labels = {
            "title": "Activity title", "cover_image": "Cover image", "date": "Date",
            "start_time": "Start time", "end_time": "End time (optional)",
            "min_participants": "Minimum participants", "max_participants": "Maximum participants (optional)",
            "visibility": "Who can find it?",
        }
        help_texts = {
            "min_participants": "The activity is confirmed once this many people join.",
            "max_participants": "Leave empty for no limit.",
            "cover_image": "JPG, PNG or WebP, up to 5 MB.",
        }
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Sunset hike at Pasonanca"}),
            "description": forms.Textarea(attrs={"rows": 5, "placeholder": "What's the plan? What should people bring?"}),
            "location": forms.TextInput(attrs={"placeholder": "Where are we meeting?"}),
            "date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "cover_image": forms.FileInput(attrs={"accept": "image/*"}),
            "visibility": forms.RadioSelect,
            "min_participants": forms.NumberInput(attrs={"min": 1}),
            "max_participants": forms.NumberInput(attrs={"min": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].required = True
        self.fields["category"].empty_label = "Choose a category"
        self.fields["category"].queryset = Category.objects.all()
        self.style_fields()
        if not self.instance.pk:
            del self.fields["remove_cover"]

    def clean_title(self):
        return " ".join(self.cleaned_data["title"].split())

    def clean_cover_image(self):
        image = self.cleaned_data.get("cover_image")
        if image and hasattr(image, "size") and image.size > MAX_IMAGE_MB * 1024 * 1024:
            raise forms.ValidationError(f"Please choose an image under {MAX_IMAGE_MB} MB.")
        return image

    def clean(self):
        cleaned = super().clean()
        date, start, end = cleaned.get("date"), cleaned.get("start_time"), cleaned.get("end_time")
        low, high = cleaned.get("min_participants"), cleaned.get("max_participants")
        if date and start:
            moved = not self.instance.pk or (date, start) != (self.instance.date, self.instance.start_time)
            if moved and timezone.make_aware(datetime.combine(date, start)) <= timezone.now():
                self.add_error("date", "Pick a date and start time in the future.")
        if start and end and end <= start:
            self.add_error("end_time", "The end time must be after the start time.")
        if low and high and high < low:
            self.add_error("max_participants", "The maximum can't be lower than the minimum.")
        if high and self.instance.pk and high < self.instance.join_count:
            self.add_error("max_participants", f"{self.instance.join_count} people have already joined.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.cleaned_data.get("remove_cover") and not self.cleaned_data.get("cover_image"):
            obj.cover_image = ""
        if commit:
            obj.save()
        return obj


class DiscoveryFilterForm(forms.Form):
    q = forms.CharField(required=False, max_length=100)
    category = forms.ModelChoiceField(Category.objects.all(), required=False, to_field_name="slug")
    date = forms.DateField(required=False)
    location = forms.CharField(required=False, max_length=100)
    availability = forms.ChoiceField(required=False, choices=[("", "Any"), ("open", "Has open slots")])

    @property
    def is_active(self):
        return self.is_bound and any(self.cleaned_data.get(k) for k in ("q", "category", "date", "location", "availability"))
