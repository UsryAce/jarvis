"""UI/UX Design & Creative Generation Skill for JARVIS."""
from typing import Any, Dict, List
from src.skills.registry import Skill


class DesignSkill(Skill):
    """UI/UX design, interface generation, photo/video creation, creative assets."""

    name = "design"
    description = "UI/UX design, interface mockups, photo/video generation, creative assets"
    triggers = ["design", "ui", "ux", "interface", "mockup", "wireframe", "prototype", 
                "photo", "image", "video", "creative", "brand", "logo", "landing page",
                "dashboard", "mobile app", "web app", "figma", "design system"]

    # Design principles
    PRINCIPLES = {
        "heuristics": [
            "Visibility of system status",
            "Match between system and real world",
            "User control and freedom",
            "Consistency and standards",
            "Error prevention",
            "Recognition rather than recall",
            "Flexibility and efficiency of use",
            "Aesthetic and minimalist design",
            "Help users recognize, diagnose, recover from errors",
            "Help and documentation",
        ],
        "gestalt": [
            "Proximity", "Similarity", "Continuity", "Closure", 
            "Figure/Ground", "Symmetry", "Common Fate"
        ],
        "accessibility": [
            "Perceivable", "Operable", "Understandable", "Robust"
        ],
    }

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        text = context.get("text", "").lower() if context else ""
        
        if "landing page" in text or "landing" in text:
            return await self._landing_page_design(params, text)
        elif "dashboard" in text:
            return await self._dashboard_design(params, text)
        elif "mobile app" in text or "app design" in text:
            return await self._mobile_app_design(params, text)
        elif "design system" in text or "style guide" in text:
            return await self._design_system(params, text)
        elif "wireframe" in text or "mockup" in text:
            return await self._wireframe_mockup(params, text)
        elif "photo" in text or "image" in text or "generate" in text:
            return await self._image_generation(params, text)
        elif "video" in text:
            return await self._video_generation(params, text)
        elif "brand" in text or "logo" in text:
            return await self._brand_identity(params, text)
        elif "accessibility" in text or "a11y" in text:
            return await self._accessibility_audit(params, text)
        elif "prototype" in text:
            return await self._prototyping(params, text)
        else:
            return await self._design_help()

    async def _landing_page_design(self, params: Dict, text: str) -> str:
        """Landing page structure and copy."""
        product = params.get("product", "SaaS product")
        audience = params.get("audience", "B2B professionals")
        goal = params.get("goal", "demo signups")
        
        return f"""**Landing Page Design: {product}**

**Target Audience:** {audience}
**Primary Goal:** {goal}
**Framework:** PAS (Problem-Agitation-Solution) + Social Proof

---

### **Above the Fold (Hero)**
| Element | Specification |
|---------|---------------|
| **Headline** | [Benefit-driven, <10 words, includes keyword] |
| **Subheadline** | [Clarifies headline, addresses objection, <20 words] |
| **CTA Primary** | [Action verb + outcome, e.g., "Start Free Trial"] |
| **CTA Secondary** | [Lower commitment, e.g., "Watch Demo"] |
| **Hero Visual** | [Product screenshot, demo video, or illustration] |
| **Trust Signal** | [Logos, numbers, or "Trusted by 1,000+ teams"] |

**Hero Copy Formula:**
> **Headline:** [End result] without [pain point]
> **Subheadline:** [How it works in one sentence] — [Key differentiator]

---

### **Below the Fold Sections**

**1. Problem Section (Agitation)**
- **Headline:** "The [Problem] Costing You [Time/Money/Stress]"
- **3 Pain Points** with icons + brief descriptions
- **Stat:** "[X]% of [audience] struggle with this"

**2. Solution Section**
- **Headline:** "Meet [Product] — [One-sentence value prop]"
- **3 Key Benefits** (not features) with illustrations
- **Demo:** Interactive screenshot or short video (60s max)

**3. How It Works (3-4 Steps)**
```
Step 1: [Action] → Step 2: [Action] → Step 3: [Result]
```

**4. Features Grid (6-8 features)**
| Feature | Benefit | Icon |
|---------|---------|------|
| [Feature] | [User outcome] | [Icon] |

**5. Social Proof**
- **Testimonials:** 3-5 (photo, name, title, company, result)
- **Logos:** 10-20 recognizable companies
- **Case Studies:** 2-3 with metrics (linked to full pages)
- **Reviews:** G2/Capterra ratings + "Read 200+ reviews"

**6. Pricing (if self-serve)**
- **3 Tiers:** Starter / Professional / Enterprise
- **Toggle:** Monthly / Annual (save 20%)
- **FAQ:** 5-7 common questions

**7. Final CTA Section**
- **Headline:** "Ready to [achieve outcome]?"
- **CTA:** Primary button + "No credit card required"
- **Trust:** "Cancel anytime · SOC2 certified · 99.9% uptime"

---

### **Mobile Considerations**
- Stack sections vertically
- Hero: Headline 32px, Subheadline 18px, CTA 48px touch target
- Sticky CTA bar on scroll
- Compress images (WebP, <100KB)
- Test on 375px, 414px viewports

### **Conversion Optimization Checklist**
- [ ] Headline passes "5-second test"
- [ ] Single primary CTA above fold
- [ ] Social proof within first 2 scrolls
- [ ] Form ≤5 fields (progressive profiling)
- [ ] Page load <3s (LCP <2.5s)
- [ ] Clear value prop in <10 words
- [ ] Objection handling in FAQ
- [ ] Exit intent capture (optional)

### **A/B Test Priorities**
1. Headline (benefit vs feature vs question)
2. Hero visual (screenshot vs video vs illustration)
3. CTA copy ("Start Free" vs "Get Demo" vs "Try Now")
4. Social proof (logos vs testimonials vs numbers)
5. Form length (3 vs 5 vs 7 fields)"""

    async def _dashboard_design(self, params: Dict, text: str) -> str:
        """Dashboard UI/UX design."""
        dashboard_type = params.get("type", "analytics")  # analytics, operational, executive, kpi
        users = params.get("users", "internal team")
        
        return f"""**Dashboard Design: {dashboard_type.title()} for {users}**

**Dashboard Type:** {dashboard_type.title()}
**Primary Users:** {users}
**Refresh Cadence:** {params.get("refresh", "Real-time / Daily / Weekly")}

---

### **Layout Principles**
| Principle | Application |
|-----------|-------------|
| **F-Pattern** | Key metrics top-left, details right/down |
| **Progressive Disclosure** | Overview → Filter → Drill-down → Detail |
| **Visual Hierarchy** | Size, color, position = importance |
| **Cognitive Load** | Max 5-7 KPIs visible, group related |
| **Action-Oriented** | Every metric answers "So what? Now what?" |

---

### **Screen Layout (Desktop 1440px+)**

```
┌─────────────────────────────────────────────────────────────────┐
│  HEADER (60px)  Logo | Global Filters | User | Notifications   │
├──────────────┬──────────────────────────────────────────────────┤
│              │                                                    │
│  SIDEBAR     │  MAIN CONTENT AREA                                │
│  (240px)     │                                                   │
│              │  ┌────────────────────────────────────────────┐  │
│  Navigation  │  │  KEY METRICS ROW (4-5 cards)               │  │
│  - Overview  │  │  [Metric] [Trend] [Sparkline] [Target]     │  │
│  - Reports   │  └────────────────────────────────────────────┘  │
│  - Analytics │                                                   │
│  - Settings  │  ┌──────────────┬──────────────┬──────────────┐  │
│              │  │  CHART 1     │  CHART 2     │  CHART 3     │  │
│  Filters     │  │  (Primary)   │  (Secondary) │  (Tertiary)  │  │
│  [Date]      │  │              │              │              │  │
│  [Segment]   │  └──────────────┴──────────────┴──────────────┘  │
│  [Compare]   │                                                   │
│              │  ┌────────────────────────────────────────────┐  │
│  Quick Actions│  │  DATA TABLE / DETAIL VIEW                 │  │
│  - Export    │  │  [Sortable, Filterable, Paginated]        │  │
│  - Schedule  │  └────────────────────────────────────────────┘  │
│  - Alert     │                                                   │
└──────────────┴──────────────────────────────────────────────────┘
```

---

### **Key Metrics Cards (Design Specs)**
```
┌─────────────────────────────────────┐
│  $127,450        ↗ +12.3% vs last   │
│  MRR                          month │
│  ████████████░░░░░░░░░░ 72% target  │
│  Target: $180,000                   │
└─────────────────────────────────────┘
```
- **Large number** (32-48px, bold)
- **Label** below (14px, muted)
- **Trend** (color: green/red, icon)
- **Progress bar** to target (optional)
- **Hover:** Tooltip with breakdown

---

### **Chart Types by Use Case**
| Question | Chart Type | Best Practices |
|----------|------------|----------------|
| Trend over time | Line / Area | Max 5 lines, highlight current |
| Comparison | Bar / Column | Sort by value, highlight current |
| Composition | Stacked Bar / Donut | Max 5 segments, label % |
| Distribution | Histogram / Box | Show median, quartiles |
| Relationship | Scatter / Bubble | Trend line, correlation |
| Geospatial | Choropleth / Symbol | Log scale for skewed data |
| Funnel | Funnel Chart | Show conversion % at each step |

---

### **Color System (Data Visualization)**
```css
/* Semantic Colors */
--color-success: #10B981;   /* Green - positive, on-track */
--color-warning: #F59E0B;   /* Amber - attention needed */
--color-danger: #EF4444;    /* Red - critical, off-track */
--color-info: #3B82F6;      /* Blue - neutral, informational */

/* Categorical Palette (Colorblind-safe) */
--chart-1: #0072B2;  --chart-2: #D55E00;
--chart-3: #009E73;  --chart-4: #CC79A7;
--chart-5: #56B4E9;  --chart-6: #F0E442;

/* Sequential (for heatmaps) */
--seq-1: #EFF6FF; --seq-2: #DBEAFE; --seq-3: #93C5FD;
--seq-4: #60A5FA; --seq-5: #3B82F6; --seq-6: #2563EB;
--seq-7: #1D4ED8; --seq-8: #1E40AF; --seq-9: #1E3A8A;
```

---

### **Responsive Breakpoints**
| Breakpoint | Layout Changes |
|------------|----------------|
| **1440px+** | Full sidebar, 3-4 column grid |
| **1024px** | Collapsible sidebar, 2-column grid |
| **768px** | Drawer sidebar, stacked cards, horizontal scroll tables |
| **640px** | Bottom nav, single column, swipeable charts |

---

### **Interactions & States**
| State | Visual | Behavior |
|-------|--------|----------|
| **Loading** | Skeleton screens | Progressive reveal |
| **Empty** | Illustration + CTA | Guide to action |
| **Error** | Inline + toast | Retry button |
| **Hover** | Highlight row | Tooltip with details |
| **Selection** | Checkbox + highlight | Bulk actions bar |
| **Drill-down** | Modal / Slide-over | Breadcrumb navigation |

---

### **Accessibility (WCAG 2.1 AA)**
- [ ] Color contrast 4.5:1 (text), 3:1 (UI)
- [ ] Color not sole info carrier (patterns + color)
- [ ] Keyboard navigation (tab order, focus visible)
- [ ] Screen reader labels (aria-label, table headers)
- [ ] Reduced motion option (disable animations)
- [ ] High contrast mode support
- [ ] Text resize to 200% without horizontal scroll

*Want a specific dashboard template (SaaS metrics, E-commerce, Marketing, Sales, Ops)?*"""

    async def _mobile_app_design(self, params: Dict, text: str) -> str:
        """Mobile app design guidelines."""
        platform = params.get("platform", "ios+android")
        app_type = params.get("type", "productivity")
        
        return f"""**Mobile App Design: {app_type.title()} ({platform.upper()})**

**Platform:** {platform.upper()}
**App Type:** {app_type.title()}

---

### **Design Systems by Platform**

**iOS (Human Interface Guidelines)**
- **Navigation:** Tab Bar (3-5 tabs), Navigation Bar, Back gesture
- **Typography:** SF Pro (17pt body, 28pt title, 34pt large title)
- **Spacing:** 8pt grid, 16pt margins, 20pt touch targets minimum
- **Colors:** Semantic (label, systemBackground, separator)
- **Corner Radius:** 8pt (cards), 12pt (sheets), 16pt (modals)
- **Shadows:** 4 levels (elevation)
- **Icons:** SF Symbols (consistent weight)

**Android (Material Design 3)**
- **Navigation:** Bottom Nav (3-5), Top App Bar, Navigation Drawer
- **Typography:** Roboto/Inter (16sp body, 22sp headline, 57sp display)
- **Spacing:** 4dp grid, 16dp margins, 48dp touch targets
- **Colors:** Dynamic Color (Material You), tonal palettes
- **Corner Radius:** 12dp (small), 16dp (medium), 28dp (large)
- **Elevation:** 6 levels (surface containers)
- **Icons:** Material Icons (filled, outlined, rounded, sharp)

---

### **Screen Architecture**

**Standard App Flow:**
```
ONBOARDING → AUTH → HOME → FEATURE → DETAIL → SETTINGS
   │          │       │        │         │          │
   ▼          ▼       ▼        ▼         ▼          ▼
Welcome    Login/    Tab Bar  List/     Detail     Profile,
Slides     Signup    (3-5)   Grid      View       Account,
Perms      Biometrics                Actions    Help
```

**Key Screens Checklist:**
- [ ] **Splash** (brand, <2s, async init)
- [ ] **Onboarding** (3-5 slides, skip option, value props)
- [ ] **Auth** (Email/password, SSO, Magic link, Biometric)
- [ ] **Home/Dashboard** (Personalized, Primary action prominent)
- [ ] **Search** (Instant results, Filters, History, Suggestions)
- [ ] **Detail** (Hero image, Actions, Related, Share)
- [ ] **Profile/Settings** (Account, Notifications, Privacy, Help)
- [ ] **Empty States** (Illustration, Copy, Primary CTA)
- [ ] **Error States** (Inline, Toast, Full-screen, Retry)
- [ ] **Loading** (Skeleton, Progress, Pull-to-refresh)

---

### **Navigation Patterns**

| Pattern | Use Case | Max Items |
|---------|----------|-----------|
| **Tab Bar** | Primary destinations | 3-5 |
| **Bottom Sheet** | Secondary actions | Variable |
| **Modal** | Focused task | Single |
| **Navigation Stack** | Hierarchical content | Unlimited |
| **Drawer** | Secondary navigation | 7+ |
| **Segmented Control** | Filter/view switch | 2-4 |

---

### **Component Library (Core)**

**Buttons:**
```
Primary:    Filled, high emphasis
Secondary:  Outlined, medium emphasis  
Tertiary:   Text only, low emphasis
Destructive: Red, confirmed destructive
```

**Inputs:**
- Text Field: Label, placeholder, helper text, error state
- Select: Native picker (iOS) / Dropdown (Android)
- Toggle: Switch (on/off), Checkbox (multi), Radio (single)
- Slider: Range with labels
- Date/Time: Native pickers

**Lists & Cards:**
- **List Item:** Icon/Avatar, Title, Subtitle, Trailing (chevron/badge/action)
- **Card:** Container, 12-16dp radius, elevation 1-2
- **Section Header:** Sticky, bold, uppercase optional

---

### **Responsive & Adaptive**
| Size Class | iOS | Android | Layout |
|------------|-----|---------|--------|
| **Compact** | iPhone | Phone | Single column |
| **Regular** | iPad | Tablet/Foldable | Two-column, Sidebar |
| **Landscape** | Both | Both | Adaptive split |

---

### **Performance & Polish**
- [ ] 60fps animations (prefer transform/opacity)
- [ ] Haptic feedback (selection, success, error, warning)
- [ ] Offline-first (cache, sync, conflict resolution)
- [ ] Deep links + Universal Links / App Links
- [ ] Push notifications (relevant, actionable, respectful)
- [ ] App shortcuts / Quick actions
- [ ] Spotlight / App Search indexing
- [ ] VoiceOver / TalkBack support
- [ ] Dynamic Type / Font scaling
- [ ] RTL language support

---

### **Design Handoff Checklist**
- [ ] Figma file organized (Pages: Flows, Components, Screens, Icons)
- [ ] Components documented (variants, states, specs)
- [ ] Color styles (light/dark, semantic)
- [ ] Text styles (platform-specific)
- [ ] Spacing tokens (4, 8, 16, 24, 32, 40, 48, 64)
- [ ] Shadow/elevation tokens
- [ ] Border radius tokens
- [ ] Interaction specs (transitions, easing, duration)
- [ ] Asset export (1x, 2x, 3x / mdpi, hdpi, xhdpi, xxhdpi, xxxhdpi)
- [ ] Animation specs (Lottie / After Effects)
- [ ] Accessibility annotations

*Want a specific screen designed (onboarding, settings, checkout, feed, etc.)?*"""

    async def _design_system(self, params: Dict, text: str) -> str:
        """Design system architecture."""
        return """**Design System Architecture**

**Purpose:** Single source of truth for design + code consistency across products.

---

### **Three-Layer Token Architecture**

**Layer 1: Primitive Tokens (Raw Values)**
```json
{
  "color": {
    "blue-50": "#EFF6FF",
    "blue-100": "#DBEAFE",
    "blue-500": "#3B82F6",
    "blue-600": "#2563EB",
    "blue-900": "#1E3A8A",
    "gray-50": "#F9FAFB",
    "gray-900": "#111827",
    "white": "#FFFFFF",
    "black": "#000000"
  },
  "spacing": {
    "0": "0",
    "1": "0.25rem",   /* 4px */
    "2": "0.5rem",    /* 8px */
    "3": "0.75rem",   /* 12px */
    "4": "1rem",      /* 16px */
    "5": "1.25rem",   /* 20px */
    "6": "1.5rem",    /* 24px */
    "8": "2rem",      /* 32px */
    "10": "2.5rem",   /* 40px */
    "12": "3rem",     /* 48px */
    "16": "4rem"      /* 64px */
  },
  "typography": {
    "fontFamilies": {
      "sans": "Inter, system-ui, sans-serif",
      "mono": "JetBrains Mono, monospace"
    },
    "fontSizes": {
      "xs": "0.75rem",    /* 12px */
      "sm": "0.875rem",   /* 14px */
      "base": "1rem",     /* 16px */
      "lg": "1.125rem",   /* 18px */
      "xl": "1.25rem",   /* 20px */
      "2xl": "1.5rem",   /* 24px */
      "3xl": "1.875rem", /* 30px */
      "4xl": "2.25rem",  /* 36px */
      "5xl": "3rem"      /* 48px */
    },
    "fontWeights": {
      "normal": "400",
      "medium": "500",
      "semibold": "600",
      "bold": "700"
    },
    "lineHeights": {
      "tight": "1.25",
      "normal": "1.5",
      "relaxed": "1.75"
    }
  },
  "borderRadius": {
    "none": "0",
    "sm": "0.25rem",    /* 4px */
    "md": "0.375rem",   /* 6px */
    "lg": "0.5rem",     /* 8px */
    "xl": "0.75rem",    /* 12px */
    "2xl": "1rem",      /* 16px */
    "full": "9999px"
  },
  "shadows": {
    "sm": "0 1px 2px 0 rgb(0 0 0 / 0.05)",
    "md": "0 4px 6px -1px rgb(0 0 0 / 0.1)",
    "lg": "0 10px 15px -3px rgb(0 0 0 / 0.1)",
    "xl": "0 20px 25px -5px rgb(0 0 0 / 0.1)"
  },
  "transitions": {
    "fast": "150ms ease",
    "normal": "200ms ease",
    "slow": "300ms ease"
  },
  "breakpoints": {
    "sm": "640px",
    "md": "768px",
    "lg": "1024px",
    "xl": "1280px",
    "2xl": "1536px"
  }
}
```

**Layer 2: Semantic Tokens (Purpose-Driven)**
```json
{
  "color": {
    "background": {
      "primary": "{color.gray-50}",
      "secondary": "{color.white}",
      "tertiary": "{color.gray-100}",
      "inverse": "{color.gray-900}"
    },
    "text": {
      "primary": "{color.gray-900}",
      "secondary": "{color.gray-600}",
      "tertiary": "{color.gray-400}",
      "inverse": "{color.white}",
      "link": "{color.blue-600}",
      "linkHover": "{color.blue-700}"
    },
    "border": {
      "light": "{color.gray-200}",
      "medium": "{color.gray-300}",
      "dark": "{color.gray-400}",
      "focus": "{color.blue-500}"
    },
    "status": {
      "success": "{color.green-600}",
      "successBg": "{color.green-50}",
      "warning": "{color.amber-600}",
      "warningBg": "{color.amber-50}",
      "danger": "{color.red-600}",
      "dangerBg": "{color.red-50}",
      "info": "{color.blue-600}",
      "infoBg": "{color.blue-50}"
    },
    "brand": {
      "primary": "{color.blue-600}",
      "primaryHover": "{color.blue-700}",
      "primaryBg": "{color.blue-50}"
    }
  }
}
```

**Layer 3: Component Tokens (Component-Specific)**
```json
{
  "button": {
    "height": {
      "sm": "32px",
      "md": "40px",
      "lg": "48px"
    },
    "paddingX": {
      "sm": "{spacing.3}",
      "md": "{spacing.4}",
      "lg": "{spacing.6}"
    },
    "borderRadius": "{borderRadius.lg}",
    "fontSize": "{typography.fontSizes.sm}",
    "fontWeight": "{typography.fontWeights.medium}"
  },
  "input": {
    "height": "40px",
    "paddingX": "{spacing.3}",
    "paddingY": "{spacing.2}",
    "borderRadius": "{borderRadius.md}",
    "borderWidth": "1px",
    "fontSize": "{typography.fontSizes.base}"
  },
  "card": {
    "padding": "{spacing.6}",
    "borderRadius": "{borderRadius.xl}",
    "shadow": "{shadows.md}",
    "borderWidth": "1px",
    "borderColor": "{color.border.light}"
  }
}
```

---

### **Component Library Structure**

```
design-system/
├── tokens/                 # Design tokens (JSON/TS/CSS)
│   ├── primitive.json
│   ├── semantic.json
│   └── component.json
├── components/             # React/Vue/Svelte components
│   ├── atoms/              # Button, Input, Icon, Badge, Avatar
│   ├── molecules/          # Card, FormField, Dropdown, Toast
│   ├── organisms/          # Header, Sidebar, Table, Modal
│   ├── templates/          # Page layouts, Dashboard shell
│   └── pages/              # Complete page examples
├── hooks/                  # useTokens, useMediaQuery, useTheme
├── utils/                  # clsx, classNames, formatters
├── styles/                 # Global CSS, reset, variables
├── icons/                  # SVG icon components
├── docs/                   # Storybook, documentation
└── package.json
```

---

### **Theming Strategy**

**Light/Dark Mode:**
```css
:root {
  /* Light mode (default) */
  --bg-primary: {color.background.primary};
  --text-primary: {color.text.primary};
  --border-light: {color.border.light};
}

[data-theme="dark"] {
  --bg-primary: {color.gray-900};
  --text-primary: {color.gray-50};
  --border-light: {color.gray-700};
}

/* Auto-detect */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg-primary: {color.gray-900};
    --text-primary: {color.gray-50};
  }
}
```

**Brand Theming (Multi-tenant):**
```css
[data-brand="customer-a"] {
  --brand-primary: #7C3AED;   /* Purple */
  --brand-primary-hover: #6D28D9;
}
[data-brand="customer-b"] {
  --brand-primary: #059669;   /* Emerald */
  --brand-primary-hover: #047857;
}
```

---

### **Documentation (Storybook)**

**Story Structure per Component:**
```tsx
// Button.stories.tsx
export default {
  title: 'Atoms/Button',
  component: Button,
  argTypes: {
    variant: { control: 'select', options: ['primary', 'secondary', 'ghost', 'danger'] },
    size: { control: 'select', options: ['sm', 'md', 'lg'] },
    disabled: { control: 'boolean' },
  },
};

export const Primary = { args: { variant: 'primary', children: 'Button' } };
export const Secondary = { args: { variant: 'secondary', children: 'Button' } };
export const Loading = { args: { variant: 'primary', isLoading: true } };
export const AllVariants = { /* ... */ };
```

**Required Docs per Component:**
- [ ] Props table (auto-generated)
- [ ] Usage guidelines (when to use/avoid)
- [ ] Accessibility notes
- [ ] Design spec link (Figma)
- [ ] Code examples (React, HTML, Vue)
- [ ] Migration guide (if breaking changes)

---

### **Governance & Versioning**

**Versioning:** Semantic Versioning (MAJOR.MINOR.PATCH)
- **PATCH:** Bug fixes, token value tweaks
- **MINOR:** New components, new tokens, new variants
- **MAJOR:** Breaking changes (token rename, component API)

**Release Process:**
1. Changes in `main` branch
2. Changeset generates changelog
3. Version bump + publish to npm
4. Update Figma library
4. Notify consumers (Slack, email)
5. Update documentation site

**Adoption Metrics:**
- Component usage across repos
- Bundle size impact
- Accessibility audit scores
- Design/developer satisfaction survey"""

    async def _wireframe_mockup(self, params: Dict, text: str) -> str:
        """Wireframe and mockup guidance."""
        fidelity = params.get("fidelity", "mid")  # low, mid, high
        
        return f"""**Wireframe & Mockup Process: {fidelity.title()}-Fidelity**

**Fidelity Levels:**
| Level | Purpose | Tools | Time | Detail |
|-------|---------|-------|------|--------|
| **Low** | Ideation, flows, layout | Paper, FigJam, Excalidraw, Balsamiq | 5-15 min/screen | Boxes, lines, labels |
| **Mid** | Structure, content, UX | Figma, Sketch, Adobe XD | 30-60 min/screen | Real copy, grayscale, spacing |
| **High** | Visual design, handoff | Figma, Framer, Origami | 1-4 hrs/screen | Colors, type, images, interactions |

---

### **Wireframe Templates (Common Patterns)**

**1. SaaS Dashboard (Mid-Fi)**
```
┌─────────────────────────────────────────────────────────────┐
│  ☰  [Logo]  Product Name          [Search]  [Notif]  [User] │
├────────────┬────────────────────────────────────────────────┤
│            │                                                 │
│  NAV       │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────┐ │
│  ▸ Overview│  │ Metric 1│ │ Metric 2│ │ Metric 3│ │Metric 4│ │
│  ▸ Analytics│ │ $127K   │ │ 2,451   │ │ 12.3%   │ │ 4.2   │ │
│  ▸ Reports │ │ ↗ 12%   │ │ ↗ 8%    │ │ ↘ 2%    │ │ → 0%  │ │
│  ▸ Team    │ └─────────┘ └─────────┘ └─────────┘ └───────┘ │
│  ▸ Settings│                                                 │
│            │  ┌─────────────────────┐ ┌─────────────────┐  │
│  FILTERS   │  │   LINE CHART        │ │   BAR CHART     │  │
│  [Date ▼]  │  │   (Revenue trend)   │ │   (By channel)  │  │
│  [Seg ▼]   │  │                     │ │                 │  │
│  [Comp ▼]  │  └─────────────────────┘ └─────────────────┘  │
│            │                                                 │
│  [Export]  │  ┌─────────────────────────────────────────┐  │
│  [Alert]   │  │  DATA TABLE                              │  │
│            │  │  ▼  | Name      | Status | Value | Act  │  │
│            │  │       | Acme Corp | Active | $50K  | ⋮  │  │
│            │  │       | Globex    | Trial  | $12K  | ⋮  │  │
│            │  └─────────────────────────────────────────┘  │
└────────────┴────────────────────────────────────────────────┘
```

**2. E-Commerce Product Page (Mid-Fi)**
```
┌─────────────────────────────────────────────────────────────┐
│  ← Back                    [Share]  [Wishlist]  [Cart: 3]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐  ┌─────────────────────────────────┐  │
│  │                 │  │  Product Name                    │  │
│  │   MAIN IMAGE    │  │  ⭐⭐⭐⭐⭐  (247 reviews)          │  │
│  │   (Zoom on      │  │  $129.00  ~~$159.00~~  Save 19% │  │
│  │    hover)       │  │                                 │  │
│  │                 │  │  [Color: ● ● ● ▼]  [Size: S M L] │  │
│  └─────────────────┘  │                                 │  │
│  ◀ [Thumb] [Thumb]    │  QTY: [-] 1 [+]    [Add to Cart] │  │
│  [Thumb] [Thumb] ▶    │  [Buy Now]  [Save for Later]     │  │
│                       │                                 │  │
│                       │  ✓ Free 2-day shipping           │  │
│                       │  ✓ 30-day returns                │  │
│                       │  ✓ Secure checkout               │  │
│                       └─────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  TABS:  [Description] [Specs] [Reviews (247)] [Q&A (12)]   │
├─────────────────────────────────────────────────────────────┤
│  Description content...                                     │
│                                                             │
│  REVIEWS:  ⭐⭐⭐⭐⭐  "Amazing quality!" - Sarah M.          │
│  [View all 247]                                             │
└─────────────────────────────────────────────────────────────┘
```

**3. Mobile Onboarding Flow (Low-Fi)**
```
Screen 1          Screen 2          Screen 3          Screen 4
┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐
│         │      │         │      │         │      │         │
│  [Illus]│      │  [Illus]│      │  [Illus]│      │  [Illus]│
│         │      │         │      │         │      │         │
│ Welcome │      │  Save   │      │  Work   │      │  Ready  │
│ to App  │      │  Time   │      │  Smarter│      │  to Go  │
│         │      │         │      │         │      │         │
│ [Next]  │      │ [Next]  │      │ [Next]  │      │[Get St.]│
│ [Skip]  │      │ [Skip]  │      │ [Skip]  │      │         │
└─────────┘      └─────────┘      └─────────┘      └─────────┘
```

---

### **Wireframe Best Practices**

**Content-First Approach:**
1. **Real copy** (not Lorem Ipsum) - reveals length issues
2. **Real data** (not placeholders) - reveals truncation/overflow
3. **Real images** (or aspect-ratio boxes) - reveals layout breaks

**Annotation Layer:**
```
┌─────────────────────────────────────┐
│  [Component]                        │
│  ① Loading state: skeleton          │
│  ② Empty state: illustration + CTA  │
│  ③ Error inline: red text + icon    │
│  ④ Hover: highlight + tooltip       │
│  ⑤ Click: navigate to /detail/:id   │
└─────────────────────────────────────┘
```

**Responsive Annotations:**
- **Desktop (>1024px):** 3-column grid
- **Tablet (768-1024px):** 2-column, sidebar drawer
- **Mobile (<768px):** Single column, bottom nav

---

### **Handoff Checklist (Mid → High Fidelity)**

**For Developers:**
- [ ] Spacing tokens used (not magic numbers)
- [ ] Color tokens referenced (not hex values)
- [ ] Typography scale followed
- [ ] Component variants documented
- [ ] States defined (default, hover, focus, disabled, loading, error)
- [ ] Responsive breakpoints specified
- [ ] Accessibility attributes noted (aria-labels, roles)
- [ ] Animation specs (easing, duration, delay)
- [ ] Asset exports ready (SVG icons, WebP images, @2x/@3x)

**For Designers:**
- [ ] Design system components used
- [ ] Consistent spacing/rhythm
- [ ] Alignment to 8px grid
- [ ] Visual hierarchy clear
- [ ] Color contrast verified (WCAG AA)
- [ ] Dark mode variants
- [ ] Edge cases covered (long text, no data, errors)

---

### **Prototyping Tools Comparison**

| Tool | Best For | Learning Curve | Collaboration | Handoff |
|------|----------|----------------|---------------|---------|
| **Figma** | All fidelity, design systems | Low | Excellent | DevMode, inspect |
| **Framer** | High-fidelity, interactive, code | Medium | Good | React code export |
| **Origami** | Complex interactions, native | High | Limited | Patch export |
| **Principle** | Animation, micro-interactions | Low | Manual | Video/GIF |
| **ProtoPie** | Advanced logic, sensors | Medium | Cloud | Specs export |
| **Axure** | Complex logic, enterprise | High | Team projects | HTML specs |

*Want a specific wireframe template (checkout, settings, calendar, kanban, etc.)?*"""

    async def _image_generation(self, params: Dict, text: str) -> str:
        """AI image generation guidance."""
        return """**AI Image Generation for Design & Marketing**

**Top Models (2024):**
| Model | Best For | Access | Cost | Strengths |
|-------|----------|--------|------|-----------|
| **Midjourney v6** | Artistic, photorealistic, concepts | Discord/Web | $10-120/mo | Aesthetic quality, style range |
| **DALL-E 3** | Precise prompts, text in images | ChatGPT/API | $20/mo / API | Prompt adherence, safety |
| **Stable Diffusion XL** | Custom models, control, local | Local/API | Free / API | ControlNet, LoRA, free local |
| **Flux** | Photorealistic, text, open | Local/API | Free / API | Quality, speed, open weights |
| **Ideogram** | Text rendering, logos, typography | Web/API | Free tier | Best text in images |
| **Recraft** | Vector, illustrations, icons | Web/API | Free tier | SVG export, brand consistency |
| **Adobe Firefly** | Commercial safe, stock style | Creative Cloud | Included | IP indemnification |

---

### **Prompt Engineering Framework**

**Structure:**
```
[SUBJECT] + [STYLE] + [COMPOSITION] + [LIGHTING] + [TECHNICAL] + [NEGATIVE]
```

**Templates by Use Case:**

**Product Photography:**
```
Professional product photo of [product], [angle: hero/closeup/lifestyle],
[background: clean white / gradient / contextual environment],
[lighting: studio softbox / natural window / dramatic rim light],
[technical: 8k, 85mm lens, f/8, ISO 100, commercial photography],
--no blur, watermark, text, distortion, amateur
```

**UI/UX Illustrations:**
```
[Concept: onboarding/empty state/error/success], 
[style: flat design / isometric / 3D clay / line art / glassmorphism],
[color palette: brand colors / pastel / monochrome / high contrast],
[composition: centered / rule of thirds / diagonal flow],
[technical: vector style, clean edges, scalable, 4k],
--no photorealistic, 3d render, gradient mesh, complex shadows
```

**Marketing Hero/Banner:**
```
[Hero image for: product launch / feature announcement / campaign],
[layout: wide 16:9 / square 1:1 / vertical 9:16],
[focus: product + human / lifestyle scene / abstract visualization],
[mood: energetic / professional / calm / innovative / trustworthy],
[style: modern tech / editorial / minimal / bold / organic],
[technical: high resolution, commercial quality, brand colors],
--no clutter, low quality, generic stock photo look, watermark
```

**Social Media Content:**
```
[Platform: Instagram / LinkedIn / Twitter / TikTok thumbnail],
[Format: carousel slide / single post / story / reel cover],
[Content: tip / statistic / quote / before-after / process],
[Style: branded template / kinetic typography / photo collage],
[Technical: safe zones for UI, aspect ratio correct, text readable],
--no watermark, low resolution, off-brand colors, cluttered
```

---

### **Control & Consistency (Advanced)**

**ControlNet (Stable Diffusion/Flux):**
| Control Type | Use Case | Input |
|--------------|----------|-------|
| **Canny** | Edge preservation | Line drawing → render |
| **Depth** | 3D structure | Depth map → consistent perspective |
| **OpenPose** | Human poses | Skeleton → character in pose |
| **Tile** | High-res upscale | Low-res → detailed high-res |
| **IP-Adapter** | Style/image reference | Reference image → apply style |
| **LineArt** | Sketch to render | Hand sketch → polished |

**LoRA (Low-Rank Adaptation):**
- Train on 10-50 brand images → consistent style/character
- Mix multiple LoRAs (style + character + lighting)
- Shareable, lightweight (<200MB)

**IP-Adapter / Reference:**
- Single reference image → apply style/composition
- No training needed, instant

---

### **Brand Consistency Workflow**

**1. Define Visual Language:**
```
Brand Colors: Primary #3B82F6, Secondary #10B981, Accent #F59E0B
Typography: Inter (UI), Display: Space Grotesk
Style: Clean, modern, 8px radius, subtle shadows
Iconography: Lucide/Phosphor, 2px stroke, 24px grid
Photography: Natural light, diverse people, authentic moments
```

**2. Create Reference Sheets:**
- Brand guidelines → PDF for prompting
- LoRA training set (20-50 curated images)
- ControlNet reference library (poses, compositions)

**3. Production Pipeline:**
```
Prompt Library (Notion/Airtable)
    ↓
Batch Generation (API/ComfyUI/Automatic1111)
    ↓
Curation & Selection (Human review)
    ↓
Post-Process (Upscale, Background remove, Color correct)
    ↓
Asset Management (Figma/Drive/DAM)
    ↓
Deployment (CMS, Social, Ads, Product)
```

---

### **Video Generation (AI)**

| Model | Best For | Access | Duration | Resolution |
|-------|----------|--------|----------|------------|
| **Runway Gen-3** | Cinematic, realistic | Web/API | 5-10s | 720p/1080p |
| **Luma Dream Machine** | Camera moves, consistency | Web/API | 5s | 1024x1024 |
| **Kling** | High quality, physics | Web/API | 5-10s | 1080p |
| **Sora** | Complex scenes, long | Limited | 60s | 1080p |
| **Pika** | Creative, stylized | Web/Discord | 3-5s | 1024x1024 |
| **Stable Video Diffusion** | Open source, local | Local | 2-4s | 576x1024 |

**Video Prompt Structure:**
```
[CAMERA: static / pan left / zoom in / orbit / dolly / handheld],
[SUBJECT: detailed description],
[ENVIRONMENT: setting, lighting, atmosphere],
[STYLE: cinematic / documentary / commercial / artistic],
[TECHNICAL: 4k, 24fps, shallow depth of field, anamorphic],
[NEGATIVE: blur, distortion, morphing, warping, low quality]
```

**Image-to-Video (Best Quality):**
1. Generate perfect keyframe in Midjourney/Flux
2. Use as input for Runway/Kling/Luma
3. Add camera direction in prompt
4. Extend with multiple generations + stitch

---

### **Post-Processing Pipeline**
```bash
# Upscale (2x-4x)
Real-ESRGAN / Topaz Gigapixel / Magnific AI

# Background Removal
RMBG-1.4 / BiRefNet / Remove.bg API

# Color Grading
Match brand palette / DaVinci Resolve / Lightroom

# Format Optimization
WebP (images) / AVIF (next-gen) / MP4/H.265 (video)
Responsive sizes (srcset) / Lazy loading
```

---

### **Legal & Ethical**
- [ ] **Commercial license** verified for model
- [ ] **No copyrighted characters/logos** in training
- [ ] **Model releases** for recognizable people
- [ ] **Disclosure** if required by platform/law
- [ ] **Bias audit** for diverse representation
- [ ] **Watermarking** for provenance (C2PA)

**Safe Commercial Models:**
- Adobe Firefly (trained on Adobe Stock)
- DALL-E 3 (OpenAI indemnification)
- Midjourney (commercial with paid plan)
- Stable Diffusion (open, your responsibility)

*Want specific prompts for your use case (hero, avatar, icon set, pattern, etc.)?*"""

    async def _video_generation(self, params: Dict, text: str) -> str:
        return await self._image_generation(params, text)  # Covered in image generation

    async def _brand_identity(self, params: Dict, text: str) -> str:
        """Brand identity design."""
        return """**Brand Identity System**

**Core Elements:**
| Element | Deliverables | Specifications |
|---------|--------------|----------------|
| **Logo** | Primary, Secondary, Icon, Wordmark | SVG, PNG @1x/2x/3x, mono, safe space |
| **Color** | Primary, Secondary, Tertiary, Neutrals | HEX, RGB, CMYK, PANTONE, HSL, a11y pairs |
| **Typography** | Display, Heading, Body, Mono | Font files, sizes, weights, line heights |
| **Iconography** | System (UI), Marketing, Social | 24px grid, 2px stroke, filled/outlined |
| **Imagery** | Photography style, Illustration style | Mood boards, do/don't, filters |
| **Voice** | Tone, Vocabulary, Grammar, Principles | Examples per channel |
| **Motion** | Easing, Duration, Choreography | Tokens, Lottie/After Effects |

---

### **Logo System**

**Variations Required:**
```
Primary (Full)          Secondary (Stacked)         Icon (Mark Only)
┌─────────────────┐     ┌─────────┐                ┌─────┐
│  ● Brand Name   │     │   ●     │                │  ●  │
│                 │     │ Brand   │                │     │
│  Tagline opt.   │     │ Name    │                └─────┘
└─────────────────┘     └─────────┘

Wordmark Only         Favicon (32px)          App Icon (1024px)
┌─────────────────┐     ┌───┐                 ┌───────┐
│  BRAND NAME     │     │ ● │                 │   ●   │
└─────────────────┘     └───┘                 │ BRAND │
                                              └───────┘
```

**Clear Space & Minimum Size:**
- Clear space = height of "B" in logotype (minimum)
- Minimum width: 24px (digital), 0.75" (print)
- No other elements in clear space

**Color Versions:**
- Full color (primary)
- Single color: Primary brand color
- Single color: White (on dark)
- Single color: Black (on light)
- Mono: Grayscale

---

### **Color System**

**Accessibility-First Palette:**
```css
/* Primary - must pass 4.5:1 on white AND 3:1 on gray-100 */
--primary-50:  #EFF6FF;   /* Lightest tint */
--primary-100: #DBEAFE;
--primary-200: #BFDBFE;
--primary-300: #93C5FD;
--primary-400: #60A5FA;
--primary-500: #3B82F6;   /* MAIN BRAND COLOR */
--primary-600: #2563EB;   /* Hover - passes 4.5:1 on white */
--primary-700: #1D4ED8;   /* Active - passes 7:1 on white */
--primary-800: #1E40AF;
--primary-900: #1E3A8A;   /* Darkest shade */
--primary-950: #172554;

/* Semantic mappings */
--color-primary: var(--primary-600);
--color-primary-hover: var(--primary-700);
--color-primary-bg: var(--primary-50);
--color-primary-text: var(--primary-900);
--color-on-primary: white;  /* Text on primary-600 */
```

**Testing Checklist:**
- [ ] Primary on white: 4.5:1 ✓
- [ ] Primary on gray-100: 3:1 ✓
- [ ] White on primary-600: 4.5:1 ✓
- [ ] All semantic pairs tested
- [ ] Colorblind] Simulated: Protanopia, Deuteranopia, Tritanopia ✓

---

### **Typography Scale**

**System Font Stack (Performance):**
```css
--font-sans: system-ui, -apple-system, BlinkMacSystemFont, 
             'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
--font-mono: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, monospace;
```

**Custom Font (Brand):**
```css
@font-face {
  font-family: 'Brand Display';
  src: url('/fonts/brand-display.woff2') format('woff2');
  font-display: swap;
  font-weight: 400 700;
}

--font-display: 'Brand Display', var(--font-sans);
```

**Type Scale (Modular Scale 1.25):**
| Token | Size | Line Height | Weight | Use Case |
|-------|------|-------------|--------|----------|
| --text-xs | 12px | 1.5 | 400 | Captions, labels |
| --text-sm | 14px | 1.5 | 400 | Body small, meta |
| --text-base | 16px | 1.5 | 400 | Body, paragraphs |
| --text-lg | 18px | 1.5 | 400 | Body large, lead |
| --text-xl | 20px | 1.4 | 500 | Subheadings |
| --text-2xl | 24px | 1.3 | 600 | H3, card titles |
| --text-3xl | 30px | 1.25 | 600 | H2, section headers |
| --text-4xl | 36px | 1.2 | 700 | H1, page titles |
| --text-5xl | 48px | 1.1 | 700 | Hero, marketing |
| --text-6xl | 60px | 1.05 | 700 | Billboard, hero large |

---

### **Iconography System**

**Grid & Rules:**
- **Grid:** 24×24px (base), 16×16px (small), 32×32px (large)
- **Stroke:** 2px (regular), 1.5px (small), 2.5px (large)
- **Corner Radius:** 2px (internal), 4px (external)
- **Style:** Outline (default), Filled (active/selected), Duotone (decorative)
- **Alignment:** Optical center, not mathematical

**Naming Convention:**
```
icons/
├── navigation/
│   ├── chevron-right.svg
│   ├── chevron-left.svg
│   ├── menu.svg
│   └── close.svg
├── actions/
│   ├── add.svg
│   ├── edit.svg
│   ├── delete.svg
│   ├── download.svg
│   └── share.svg
├── status/
│   ├── success.svg
│   ├── warning.svg
│   ├── error.svg
│   └── info.svg
└── brand/
    ├── logo-mark.svg
    ├── twitter.svg
    ├── linkedin.svg
    └── github.svg
```

---

### **Brand Voice Guidelines**

**Voice Attributes (Pick 3-4):**
| Attribute | Description | Example |
|-----------|-------------|---------|
| **Confident** | Authoritative, decisive | "Ship faster with certainty" |
| **Approachable** | Friendly, human | "We've got your back" |
| **Clever** | Witty, intelligent | "Your code, but better" |
| **Direct** | Concise, no fluff | "Deploy in minutes" |
| **Inspiring** | Visionary, motivating | "Build the future" |
| **Trustworthy** | Reliable, transparent | "99.99% uptime, guaranteed" |

**Do's and Don'ts:**
| Do | Don't |
|----|-------|
| Use active voice | Use passive voice |
| Lead with benefit | Lead with feature |
| Be specific | Use vague superlatives |
| Show, don't tell | Use marketing jargon |
| Address user directly | Talk about "the user" |
| Use contractions | Be overly formal |

**Channel Adaptation:**
| Channel | Tone | Length | Example |
|---------|------|--------|---------|
| **Website** | Confident, clear | Medium | "Ship 10x faster" |
| **Email** | Helpful, personal | Short | "Quick tip for your deploy" |
| **Social** | Engaging, human | Very short | "Just shipped: dark mode 🌙" |
| **Docs** | Direct, thorough | Long | "Configure the webhook URL" |
| **Support** | Empathetic, solution | Medium | "I understand the frustration" |
| **Legal** | Precise, formal | Long | "The Service is provided as-is" |

---

### **Brand Application Checklist**

**Digital:**
- [ ] Website (all pages)
- [ ] App (iOS, Android, Web)
- [ ] Email templates
- [ ] Social profiles (profile, cover, highlights)
- [ ] Ads (static, video, carousel)
- [ ] Pitch deck / Sales deck
- [ ] Documentation site
- [ ] Community (Discord, Slack, Forum)

**Physical:**
- [ ] Business cards
- [ ] Letterhead / Envelopes
- [ ] Swag (stickers, shirts, notebooks)
- [ ] Booth / Conference materials
- [ ] Packaging / Unboxing
- [ ] Office signage

**Governance:**
- [ ] Brand guidelines site (Notion/Figma/Zeroheight)
- [ ] Asset library (Figma/Drive/Brandfolder)
- [ ] Approval process for new uses
- [ ] Annual brand audit
- [ ] Team training / onboarding

*Want a specific brand element designed (logo concepts, color palette, typography pairings)?*"""

    async def _accessibility_audit(self, params: Dict, text: str) -> str:
        """Accessibility audit checklist."""
        return """**Accessibility Audit (WCAG 2.1 AA)**

**Quick Wins (Fix This Week):**
| Issue | Check | Fix |
|-------|-------|-----|
| **Color Contrast** | Text 4.5:1, UI 3:1 | Use Stark/Figma plugin, adjust tokens |
| **Alt Text** | All images have descriptive alt | Add meaningful descriptions |
| **Focus Visible** | Tab through - see focus ring | Add `:focus-visible` styles |
| **Form Labels** | Every input has `<label>` | Associate with `for`/`id` or wrap |
| **Heading Order** | h1 → h2 → h3 (no skipping) | Fix HTML structure |
| **Language** | `<html lang="en">` + translations | Add lang attributes |
| **Skip Link** | "Skip to main content" | Add as first focusable element |

---

### **WCAG 2.1 AA Checklist**

**Perceivable:**
- [ ] **1.1.1** Non-text content has text alternatives
- [ ] **1.2.1** Audio-only/Video-only have alternatives
- [ ] **1.2.2** Captions for prerecorded video
- [ ] **1.2.3** Audio description or media alternative
- [ ] **1.2.4** Captions for live video
- [ ] **1.2.5** Audio description for prerecorded video
- [ ] **1.3.1** Info/relationships programmatically determinable
- [ ] **1.3.2** Meaningful sequence
- [ ] **1.3.3** Not solely sensory characteristics
- [ ] **1.3.4** Orientation not restricted
- [ ] **1.3.5** Input purpose identified
- [ ] **1.4.1** Color not only visual means
- [ ] **1.4.2** Audio control (pause/stop/volume)
- [ ] **1.4.3** Contrast 4.5:1 (3:1 large text)
- [ ] **1.4.4** Resize text 200% no horizontal scroll
- [ ] **1.4.5** Images of text avoided
- [ ] **1.4.10** Reflow (320px width)
- [ ] **1.4.11** Non-text contrast 3:1
- [ ] **1.4.12** Text spacing override
- [ ] **1.4.13** Hover/focus content dismissible

**Operable:**
- [ ] **2.1.1** Keyboard accessible
- [ ] **2.1.2** No keyboard trap
- [ ] **2.1.4** Character key shortcuts
- [ ] **2.2.1** Timing adjustable
- [ ] **2.2.2** Pause, stop, hide moving content
- [ ] **2.3.1** Three flashes or below threshold
- [ ] **2.4.1** Bypass blocks (skip links)
- [ ] **2.4.2** Page titled
- [ ] **2.4.3** Focus order logical
- [ ] **2.4.4** Link purpose in context
- [ ] **2.4.5** Multiple ways to find pages
- [ ] **2.4.6** Headings/labels descriptive
- [ ] **2.4.7** Focus visible
- [ ] **2.5.1** Pointer gestures
- [ ] **2.5.2** Pointer cancellation
- [ ] **2.5.3** Label in name
- [ ] **2.5.4** Motion actuation
- [ ] **2.5.5** Target size 44×44 CSS pixels
- [ ] **2.5.6** Concurrent input mechanisms

**Understandable:**
- [ ] **3.1.1** Language of page
- [ ] **3.1.2** Language of parts
- [ ] **3.2.1** On focus no context change
- [ ] **3.2.2** On input no context change
- [ ] **3.2.3** Consistent navigation
- [ ] **3.2.4** Consistent identification
- [ ] **3.3.1** Error identification
- [ ] **3.3.2** Labels or instructions
- [ ] **3.3.3** Error suggestion
- [ ] **3.3.4** Error prevention (legal/financial)

**Robust:**
- [ ] **4.1.1** Parsing (valid HTML)
- [ ] **4.1.2** Name, role, value (ARIA)
- [ ] **4.1.3** Status messages (live regions)

---

### **Testing Tools & Methods**

**Automated (Catch ~30-50%):**
| Tool | Type | Integration |
|------|------|-------------|
| **axe-core** | Engine | CLI, CI, Playwright, Cypress |
| **Lighthouse** | Audit | Chrome DevTools, CI |
| **WAVE** | Browser ext | Manual, API |
| **Storybook a11y** | Components | Storybook addon |
| **eslint-plugin-jsx-a11y** | Lint | Pre-commit, CI |

**Manual (Required for compliance):**
1. **Keyboard-only navigation** (Tab, Shift+Tab, Enter, Space, Arrows, Esc)
2. **Screen reader testing** (NVDA/JAWS/VoiceOver)
3. **Zoom 200% + 400%** (content reflows, no horizontal scroll)
4. **High contrast mode** (Windows/OSX)
5. **Reduced motion** (OS setting)
6. **Voice control** (Dragon, built-in)

**Testing Checklist per Component:**
| Component | Keyboard | Screen Reader | Focus | Contrast | States |
|-----------|----------|---------------|-------|----------|--------|
| Button | ✓ Enter/Space | ✓ Role+Name | ✓ Ring | ✓ 4.5:1 | ✓ All |
| Link | ✓ Enter | ✓ Role+Name+Href | ✓ Ring | ✓ 4.5:1 | ✓ All |
| Input | ✓ Tab | ✓ Label+Error | ✓ Ring | ✓ 4.5:1 | ✓ All |
| Select | ✓ Arrows | ✓ Options | ✓ Ring | ✓ 4.5:1 | ✓ All |
| Modal | ✓ Trap+Esc | ✓ Labelled | ✓ Return | ✓ 4.5:1 | ✓ All |
| Table | ✓ Arrows | ✓ Headers+Scope | ✓ Cell | ✓ 4.5:1 | ✓ Sort |
| Tooltip | ✓ Hover+Focus | ✓ Describedby | ✓ Trigger | ✓ 4.5:1 | ✓ Show |

---

### **ARIA Patterns (Common)**

**Button:**
```html
<button aria-pressed="false">Toggle</button>
<button aria-expanded="false" aria-controls="menu">Menu</button>
<button aria-label="Close dialog">×</button>
```

**Dialog/Modal:**
```html
<div role="dialog" aria-modal="true" aria-labelledby="title">
  <h2 id="title">Dialog Title</h2>
  <button aria-label="Close">×</button>
  <!-- content -->
</div>
```

**Live Region (Toast/Alert):**
```html
<div role="status" aria-live="polite" aria-atomic="true">
  Saved successfully
</div>
<div role="alert" aria-live="assertive">
  Error: Connection lost
</div>
```

**Tabs:**
```html
<div role="tablist">
  <button role="tab" aria-selected="true" aria-controls="panel1">Tab 1</button>
  <button role="tab" aria-selected="false" aria-controls="panel2">Tab 2</button>
</div>
<div role="tabpanel" id="panel1" aria-labelledby="tab1">Content 1</div>
<div role="tabpanel" id="panel2" aria-labelledby="tab2" hidden>Content 2</div>
```

---

### **CI/CD Integration**

```yaml
# .github/workflows/a11y.yml
name: Accessibility
on: [push, pull_request]
jobs:
  a11y:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: npm ci
      - run: npm run build
      - name: Run axe-core
        uses: microsoft/axe-action@v1
        with:
          urls: http://localhost:3000
      - name: Lighthouse CI
        run: npx lhci autorun
```

---

### **Accessibility Statement Page**
Required for public sites:
1. **Conformance level** (WCAG 2.1 AA)
2. **Known limitations** (honest disclosure)
3. **Testing methods** (tools + assistive tech)
4. **Contact** for accessibility issues
5. **Last updated** date
6. **Feedback mechanism** (email, form, phone)

*Want a specific component audited or ARIA pattern for a custom widget?*"""

    async def _prototyping(self, params: Dict, text: str) -> str:
        """Interactive prototyping."""
        return """**Interactive Prototyping Guide**

**Prototype Fidelity Spectrum:**
| Level | Tool | Use Case | Time | Share |
|-------|------|----------|------|-------|
| **Click-through** | Figma, Marvel, InVision | Flow validation | 30 min | Link |
| **Micro-interactions** | Principle, ProtoPie, Framer | Feel, timing | 1-2 hr | Link/App |
| **Functional (Code)** | React/Vue + Storybook, CodeSandbox | Dev handoff, testing | 4-8 hr | Repo |
| **Native** | Xcode/SwiftUI, Android Studio | Platform testing | 1-2 day | TestFlight |

---

### **Figma Prototyping (Most Common)**

**Connections:**
- **On Click/Tap** → Navigate to
- **On Drag** → Swipe gestures (carousel, drawer)
- **While Hovering** → Tooltip, dropdown
- **Key/Gamepad** → Keyboard shortcuts
- **After Delay** → Auto-advance, loading

**Animations:**
| Type | Easing | Duration | Use Case |
|------|--------|----------|----------|
| **Instant** | - | 0ms | Navigation, tabs |
| **Dissolve** | Ease out | 200ms | Modals, toasts |
| **Slide In** | Ease out | 300ms | Drawers, sheets, pages |
| **Push** | Ease in-out | 300ms | Page transitions |
| **Move In/Out** | Ease out | 250ms | Nested navigation |
| **Smart Animate** | Custom | 300-500ms | Morphing, complex |

**Smart Animate Requirements:**
- Same layer name across frames
- Same hierarchy position
- Properties that animate: position, size, rotation, opacity, fill, stroke, effects, corner radius

**Overflow Behaviors:**
- **Vertical Scrolling** → Long pages, lists
- **Horizontal Scrolling** → Carousels, tabs
- **Both** → Maps, infinite canvas
- **Fixed Position** → Headers, footers, FABs

---

### **Advanced Prototyping Patterns**

**1. Form Validation Flow:**
```
Frame 1: Empty form → Click Submit → Frame 2: Inline errors
Frame 2: Fill field → Blur → Frame 3: Error clears
Frame 3: All valid → Click Submit → Frame 4: Loading → Frame 5: Success
```

**2. Drag & Drop (Kanban):**
- Use "On Drag" trigger
- Smart Animate between columns
- Drop zones with "While Dragging" highlight

**3. Search with Debounce:**
- Input → "While Typing" → Delay 300ms → Results frame
- Use variables for query state

**4. Shopping Cart:**
- Variables: item count, total, items array
- "Add to cart" → Increment variable → Update badge
- Cart drawer → Read variables → Display list

**Figma Variables (New):**
```json
// Color modes
{ "light": { "bg": "#FFF" }, "dark": { "bg": "#111" } }

// Spacing
{ "xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32 }

// Boolean states
{ "isLoggedIn": false, "hasNotifications": true }

// String tokens
{ "userName": "John", "plan": "Pro" }
```

---

### **Framer (Code-Based Prototyping)**

**Why Framer:**
- Real React components
- Production-quality animations
- CMS integration
- Deploy to custom domain
- Team collaboration

**Basic Component:**
```tsx
// Button.tsx
import { motion, Variants } from "framer-motion";

const variants: Variants = {
  initial: { scale: 1 },
  hover: { scale: 1.02, transition: { duration: 0.15 } },
  tap: { scale: 0.98 },
};

export function Button({ children, onClick, variant = "primary" }) {
  return (
    <motion.button
      variants={variants}
      initial="initial"
      whileHover="hover"
      whileTap="tap"
      onClick={onClick}
      className={`btn btn-${variant}`}
    >
      {children}
    </motion.button>
  );
}
```

**Page Transitions:**
```tsx
// Layout.tsx
import { AnimatePresence } from "framer-motion";

const pageVariants = {
  initial: { opacity: 0, x: 20 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -20 },
};

export function PageTransition({ children }) {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={router.pathname}
        variants={pageVariants}
        initial="initial"
        animate="animate"
        exit="exit"
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
```

---

### **ProtoPie (Advanced Logic)**

**Unique Features:**
- Formulas (math, string, date)
- Conditions (if/else chains)
- Variables (persistent across scenes)
- Sensors (tilt, compass, microphone, camera)
- Hardware (Arduino, Bluetooth)
- Voice commands

**Example: Calculator Logic:**
```
Trigger: Tap "1"
Action: 
  - Formula: display = display + "1"
  - Text: displayLayer.text = display

Trigger: Tap "="
Action:
  - Formula: result = eval(display)
  - Text: displayLayer.text = result
  - Condition: if error → show "Error"
```

---

### **User Testing with Prototypes**

**Test Script Template:**
```
1. CONTEXT (2 min)
   "Imagine you're [persona], trying to [goal]"

2. TASKS (15-20 min each)
   Task 1: "Find and purchase [product]"
   Task 2: "Change your notification settings"
   Task 3: "Invite a team member"

3. OBSERVE (Don't guide)
   - Where do they click first?
   - Hesitation points?
   - Workarounds?
   - Verbalized thoughts?

4. METRICS
   - Success rate (%)
   - Time on task
   - Error count
   - Clicks to completion
   - SUS score (post-test)

5. DEBRIEF (5 min)
   "What was confusing?"
   "What worked well?"
   "What would you change?"
```

**Remote Testing Tools:**
- **Moderated:** Zoom + Figma prototype link
- **Unmoderated:** Maze, UsabilityHub, UserTesting, PlaybookUX
- **Analytics:** Hotjar, FullStory on prototype

---

### **Handoff to Development**

**Figma DevMode Checklist:**
- [ ] **Inspect** - All specs visible (spacing, color, type)
- **Assets** - Exported (SVG icons, WebP images, @2x/@3x)
- **Components** - Variants documented, mapped to code
- **Tokens** - CSS variables / Design tokens exported
- **Flows** - User flows documented with annotations
- **Responsive** - Breakpoints defined, layouts shown
- **States** - All interactive states designed
- **Accessibility** - ARIA labels, focus order noted

**Handoff Package:**
```
handoff/
├── figma-link.txt
├── flows/
│   ├── user-onboarding.png
│   ├── checkout-flow.png
│   └── settings-flow.png
├── components/
│   ├── Button.md (specs + code example)
│   ├── Input.md
│   └── Modal.md
├── tokens/
│   ├── colors.css
│   ├── spacing.css
│   └── typography.css
├── animations/
│   ├── page-transition.css
│   └── micro-interactions.css
└── accessibility/
    ├── focus-order.md
    └── aria-patterns.md
```

*Want a specific prototype built (checkout flow, onboarding, dashboard, mobile app)?*"""

    async def _design_help(self) -> str:
        return """**Design Skill Commands:**

**Landing Pages & Marketing:**
- "Design landing page for B2B SaaS - hero, features, pricing"
- "Hero section copy for AI coding assistant"
- "Pricing page layout with 3 tiers"
- "Above-fold optimization checklist"

**Dashboards & Data Viz:**
- "SaaS metrics dashboard layout"
- "Executive dashboard with KPIs"
- "E-commerce analytics dashboard"
- "Chart type for funnel visualization"

**Mobile Apps:**
- "Mobile app onboarding flow (4 screens)"
- "iOS vs Android navigation differences"
- "Bottom tab bar architecture"
- "Empty state designs for feed app"

**Design Systems:**
- "Design token architecture (primitive/semantic/component)"
- "Color system with dark mode + accessibility"
- "Typography scale with modular ratios"
- "Component library structure (atoms to pages)"

**Wireframes & Prototypes:**
- "Low-fi wireframe for checkout flow"
- "Mid-fi mockup for dashboard"
- "Figma prototyping: smart animate tabs"
- "User testing script for prototype"

**AI Generation:**
- "Prompt for product hero image"
- "Midjourney prompt for app illustrations"
- "Runway video prompt for product demo"
- "Brand-consistent image pipeline"

**Brand & Identity:**
- "Logo system (primary, secondary, icon, favicon)"
- "Color palette with WCAG AA pairs"
- "Typography pairings (display + body)"
- "Brand voice guidelines (3 attributes)"

**Accessibility:**
- "WCAG 2.1 AA audit checklist"
- "ARIA pattern for custom select"
- "Focus management for modal"
- "Color contrast testing tools"

*Provide context: product type, audience, platform, brand guidelines!*"""