# Claude Code Brief: Carousel Templates + Renderer Update

## Context

This app generates Muay Thai fighter profile cards and posts them to Instagram.
The pipeline is: fetcher → enricher → renderer → uploader → publisher.

The renderer currently produces a single 1080x1080 JPEG from `templates/card.html`.
We are converting to a **3-slide Instagram carousel** because the single card has too
much content for the font sizes to be readable on a phone screen.

---

## Enriched Data Shape

This is the dict that the renderer receives from the enricher. Templates must work
with this exact shape. All fields except `name` may be `None`.

```python
{
    "name": "Rodtang Jitmuangnon",           # str, always present
    "nickname": None,                         # str | None
    "nationality": "Thai",                    # str | None
    "gym": "Jitmuangnon Gym",               # str | None
    "record_wins": None,                      # int | None
    "record_losses": None,                    # int | None
    "record_kos": None,                       # int | None
    "fighting_style": "Aggressive pressure fighter with devastating clinch work",  # str
    "signature_weapons": [                    # list[str]
        "Liver shot",
        "Elbow strikes",
        "Knee strikes",
        "Clinch dominance"
    ],
    "attributes": {                           # dict[str, int], scores 1-10
        "aggression": 9,
        "power": 8,
        "footwork": 8,
        "clinch": 9,
        "cardio": 8,
        "technique": 8
    },
    "bio": "Rodtang Jitmuangnon is one of the most accomplished...",  # str, 3-5 sentences
    "fun_fact": "Rodtang began training Muay Thai at age seven..."    # str, 1 sentence
}
```

---

## Design System

All three slides must share this design system exactly — they need to look like a
coherent set when viewed as a carousel.

**Colors:**
- Background: `#0d0d1a` (near black)
- Card gradient: `linear-gradient(135deg, #0d0d1a 0%, #1a1a2e 50%, #16213e 100%)`
- Primary accent: `#e63946` (red)
- Secondary accent: `#ff6b35` (orange)
- Text primary: `#ffffff`
- Text secondary: `#cccccc`
- Text muted: `#888888`
- Surface: `#1e1e35`

**Fonts (Google Fonts — already used in existing card.html):**
- `Bebas Neue` — display/name only
- `Oswald` weights 400, 600, 700 — headings, labels, UI elements
- `Inter` weights 400, 500 — body text

**Decorative elements present on all slides:**
- 6px gradient top bar: `linear-gradient(90deg, #e63946, #ff6b35, #e63946)`
- "MUAY THAI CARDS" branding in bottom-left in Bebas Neue, `#444`, 22px
- Slide indicator in bottom-right: "1 / 3", "2 / 3", "3 / 3" in Oswald, `#555`, 16px

**Sizing:**
- Every slide: exactly 1080x1080px
- `body` and `.card` must both be exactly `width: 1080px; height: 1080px; overflow: hidden`
- Padding: 56px on all sides (slightly more than existing card.html's 48px to give content more breathing room)

---

## Slide 1 — Impact Slide (`slide_1_impact.html`)

**Purpose:** Stop the scroll. This is the first thing people see. Big, bold, poster-like.
Minimal text, maximum visual weight.

**Layout (top to bottom):**

1. **Fighter name** — Bebas Neue, 120px, white, uppercase, line-height 0.9. If the name
   is longer than ~20 characters it should wrap naturally — do not reduce font size.

2. **Nickname** — if `fighter.nickname` is not None, show it below the name in Oswald
   400, 32px, `#e63946`, uppercase, letter-spacing 6px, wrapped in quotes. Skip entirely
   if None — do not show an empty space.

3. **Divider** — same gradient line as existing card: `linear-gradient(90deg, #e63946, transparent)`, 2px height, full width, 32px margin top and bottom.

4. **Fighting style** — Oswald 700, 36px, `#ff6b35`, uppercase, letter-spacing 3px,
   line-height 1.2. This is the hero content of this slide — it should feel large and
   prominent.

5. **Large decorative number** — positioned in the bottom-right area of the card as a
   background element (position: absolute, z-index 0, opacity 0.04). Show the total
   number of signature weapons as a massive number in Bebas Neue, ~400px font size,
   `#ffffff`. This creates a subtle visual texture without competing with the content.
   If no weapons, use the number of attributes (always 6).

6. **Gym and nationality row** — Oswald 400, 22px, `#888`, letter-spacing 3px, uppercase.
   Format: `GYM · NATIONALITY`. Skip either if None. This sits above the footer.

**Jinja2 conditionals needed:**
- `{% if fighter.nickname %}` around nickname block
- `{% if fighter.gym %}{{ fighter.gym }}{% if fighter.nationality %} · {% endif %}{% endif %}`
- `{% if fighter.nationality %}{{ fighter.nationality }}{% endif %}`

---

## Slide 2 — Stats Slide (`slide_2_stats.html`)

**Purpose:** The analytical deep-dive. Fans who swipe past slide 1 want the numbers.

**Layout:**

**Header (consistent across slides 2 and 3):**
- Fighter name in Bebas Neue, 48px, white — smaller, acting as a section header
- Thin red divider below it
- Margin bottom 32px before main content

**Main content — two columns:**

Left column (55% width):
- Section label "FIGHTER ATTRIBUTES" in Oswald 600, 16px, `#e63946`, letter-spacing 5px
- Six attribute rows, each containing:
  - Label: Oswald 600, 20px, `#cccccc`, uppercase, letter-spacing 2px, fixed width 140px
  - Bar track: flex-grow 1, height 14px, background `#1e1e35`, border-radius 7px
  - Bar fill: `linear-gradient(90deg, #e63946, #ff6b35)`, width `{{ score * 10 }}%`
  - Score: Oswald 700, 28px, white, fixed width 40px, text-align right
  - Row margin-bottom: 20px

Right column (45% width):
- Section label "SIGNATURE WEAPONS" in Oswald 600, 16px, `#e63946`, letter-spacing 5px
- Each weapon as a tag: Oswald 600, 18px, uppercase, letter-spacing 1px
  - Background: `rgba(230, 57, 70, 0.12)`
  - Border: `1px solid rgba(230, 57, 70, 0.35)`
  - Color: `#ff8a93`
  - Padding: 10px 20px
  - Border-radius: 4px
  - Margin: 0 8px 12px 0
  - Display: inline-block

- If `fighter.record_wins` is not None, show record below weapons:
  - Section label "RECORD" in same style
  - `{{ fighter.record_wins }}-{{ fighter.record_losses }}` in Oswald 700, 48px, white
  - "W — L" label below in Oswald 400, 16px, `#888`, letter-spacing 3px
  - If `fighter.record_kos` not None: "{{ fighter.record_kos }} KO" below that in `#ff6b35`

---

## Slide 3 — Story Slide (`slide_3_story.html`)

**Purpose:** The human story. This is what makes people follow the account.

**Layout:**

**Header:** Same as Slide 2 — fighter name 48px + divider.

**Main content — single column, full width:**

1. **Section label** "FIGHTER PROFILE" — same style as other section labels

2. **Bio** — Inter 400, 22px, `#cccccc`, line-height 1.8. This is the primary content
   of this slide. It should feel comfortable and readable — like reading a sports magazine.
   No truncation. If the text overflows the card something is wrong with the bio length
   (the enricher limits it to 3-5 sentences).

3. **Spacing** — 40px between bio and fun fact box

4. **Fun fact box:**
   - Background: `rgba(255, 107, 53, 0.08)`
   - Left border: 4px solid `#ff6b35`
   - Border-radius: `0 8px 8px 0`
   - Padding: 24px 28px
   - Label: "DID YOU KNOW" in Oswald 600, 14px, `#ff6b35`, letter-spacing 4px, uppercase, margin-bottom 12px
   - Text: Inter 400, 20px, `#bbbbbb`, line-height 1.7

5. **Source credit** — "Source: Wikipedia" in Inter 400, 14px, `#444`, sitting just
   above the footer. Only show if `fighter.wikipedia_url` is present (it may not be
   in the enriched data — check first).

---

## Changes to `server/renderer.py`

Replace the current `render_card()` function with two new functions.
**Do not implement business logic — stub only. Leave TODO comments.**

### `render_carousel(enriched_data: dict[str, Any]) -> list[Path]`

```python
async def render_carousel(enriched_data: dict[str, Any]) -> list[Path]:
    """Render all three carousel slides and return their paths.

    Args:
        enriched_data: dict returned from enricher.enrich_fighter()

    Returns:
        list of 3 Paths in order: [impact_path, stats_path, story_path]
    """
    # TODO: call render_slide() for each template in order
    # TODO: return list of 3 paths
    pass
```

### `render_slide(enriched_data: dict, template_name: str, slide_num: int) -> Path`

```python
async def render_slide(
    enriched_data: dict[str, Any],
    template_name: str,
    slide_num: int
) -> Path:
    """Render a single carousel slide to JPEG.

    Args:
        enriched_data: dict returned from enricher.enrich_fighter()
        template_name: filename of the template e.g. "slide_1_impact.html"
        slide_num: 1, 2, or 3 — used in the output filename

    Returns:
        Path to the generated JPEG

    TODO:
    - Load template from templates/ using Jinja2 FileSystemLoader
    - Render template with fighter=enriched_data
    - Generate output path using make_output_path() with slide_num
    - Launch Playwright Chromium headless
    - set_viewport_size 1080x1080
    - set_content(html, wait_until="networkidle")
    - screenshot to output_path
    - close browser
    - Return output_path
    - Wrap in try/except, raise RenderError on failure
    """
    pass
```

### `make_output_path(fighter_name: str, slide_num: int) -> Path`

Update the existing `make_output_path` to accept `slide_num`:

```python
def make_output_path(fighter_name: str, slide_num: int) -> Path:
    slug = fighter_name.lower().replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("output") / f"{slug}_{timestamp}_slide{slide_num}.jpg"
```

---

## Changes to `server/api.py`

Update the `/generate` route's response model — `card_path` becomes `card_paths` (a list):

```python
class GenerateResponse(BaseModel):
    status: str
    card_paths: list[str]   # was: card_path: str
    caption: str
```

Update the route body to call `render_carousel` instead of `render_card` and return the list:

```python
card_paths = await renderer.render_carousel(enriched_data)

return GenerateResponse(
    status="ok",
    card_paths=[str(p) for p in card_paths],
    caption=enriched_data.get("bio", ""),
)
```

The `/post` route will also need updating eventually to handle carousel posting,
but leave it as-is for now with a TODO comment noting it needs carousel support.

---

## Test File to Create: `test/test_renderer.py`

Create a test file that calls `render_carousel()` with hardcoded enriched data.
The developer will use this to test the templates without hitting the full pipeline.

```python
import asyncio
from server.renderer import render_carousel

enriched_data = {
    "name": "Rodtang Jitmuangnon",
    "nickname": None,
    "nationality": "Thai",
    "gym": "Jitmuangnon Gym",
    "record_wins": None,
    "record_losses": None,
    "record_kos": None,
    "fighting_style": "Aggressive pressure fighter with devastating clinch work and elite cardio",
    "signature_weapons": [
        "Liver shot",
        "Elbow strikes",
        "Knee strikes from clinch",
        "Clinch dominance"
    ],
    "attributes": {
        "aggression": 9,
        "power": 8,
        "footwork": 8,
        "clinch": 9,
        "cardio": 9,
        "technique": 8
    },
    "bio": "Rodtang Jitmuangnon is one of the most accomplished and highest-paid Muay Thai fighters in the world. Starting his professional career at just eight years old to support his family, he moved to Bangkok at fourteen to join Jitmuangnon gym. He captured the ONE Flyweight Muay Thai World Championship in 2019 and became the longest-reigning champion in the division with five successful title defenses. Known for his relentless aggression, elite cardio, and devastating liver shots, Rodtang holds the record for most decision wins in ONE Championship history.",
    "fun_fact": "Rodtang began training Muay Thai at age seven and competed professionally at eight to help his family financially.",
    "wikipedia_url": "https://en.wikipedia.org/wiki/Rodtang_Jitmuangnon"
}

async def main():
    paths = await render_carousel(enriched_data)
    for path in paths:
        print(f"Slide saved to: {path}")

asyncio.run(main())
```

---

## Files to Create/Modify Summary

| File | Action |
|---|---|
| `templates/slide_1_impact.html` | Create — fully implemented |
| `templates/slide_2_stats.html` | Create — fully implemented |
| `templates/slide_3_story.html` | Create — fully implemented |
| `templates/card.html` | Leave as-is — keep for reference |
| `server/renderer.py` | Modify — replace render_card with render_carousel + render_slide stubs, update make_output_path |
| `server/api.py` | Modify — update GenerateResponse and /generate route |
| `test/test_renderer.py` | Create — test file with hardcoded data |

---

## Final Instructions for Claude Code

1. Create all three template files fully implemented — these are not stubs.
2. The templates must render correctly at 1080x1080 with no content overflow.
3. Use `{% if %}` guards for every nullable field — never assume a field is present.
4. `render_carousel()` and `render_slide()` in renderer.py are stubs with TODO comments — do not implement them. The developer will write these.
5. `make_output_path()` should be fully updated to include `slide_num`.
6. After creating files, verify the templates are valid HTML by checking for unclosed tags.
7. Do NOT run the renderer — the developer will test it themselves.
