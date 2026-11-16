---
name: web-ui-from-design
description: "Use when turning a design, prototype, or Figma screenshot into Django templates and CSS, or when styling pages, buttons, forms, cards, badges, and empty states consistently."
---

# Building pages from a design

## Method
1. List the screens; map each to a URL, view, and template.
2. Extract design tokens (colors, font, spacing, radius). Colors sampled from a
   screenshot are approximate: confirm exact values in Figma (Dev Mode or Inspect).
3. Put tokens in one CSS file as variables and use var(--name) everywhere. No hard-coded
   colors in templates.
4. Build shared pieces first (base template, navigation, buttons, cards, fields,
   badges, modals), then the pages.
5. Check phone width and desktop width.

## Token template
    :root {
      --primary: #FF5A43;  --primary-tint: #FFF3F1;  --primary-soft: #FFDAD4;
      --danger: #E53935;   --danger-bg: #FCE4E5;
      --success: #059669;  --success-bg: #ECFDF5;    --pending: #FF7A00;
      --text: #0F172A;     --text-secondary: #5B6071; --text-muted: #8C8B8F;
      --bg: #F6F7FA;       --card: #FFFFFF;           --border: #E9EEF5;
      --radius: 12px;      --space: 16px;
    }

## Django structure
base.html (head, nav, block content); base_auth.html for welcome, login, sign up;
partials/ for repeated pieces used with {% include %}; static files in
<app>/static/ loaded with {% static %}; show {% if messages %} for feedback.

## Four states for every screen
Empty (friendly message plus a button), loading, error (message plus a way back), and
filled. List pattern:

    {% for item in items %}
      {% include "partials/item_card.html" %}
    {% empty %}
      <p>Nothing here yet.</p>
    {% endfor %}

## Quality bar
Contrast at least 4.5:1; badges carry text, not color alone; every input has a label;
tap targets at least 44px; images have alt text; one font family and a small spacing
scale; do not invent styles; compare to the design and test at phone width.