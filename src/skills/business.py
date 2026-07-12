"""Business Automation & Marketing Skill for JARVIS."""
from typing import Any, Dict, List
from datetime import datetime
from src.skills.registry import Skill
from src.config import config


class BusinessSkill(Skill):
    """Business automation, marketing, content generation, and workflow optimization."""

    name = "business"
    description = "Business strategy, marketing, automation, content creation, workflows"
    triggers = ["business", "marketing", "automation", "workflow", "content", "campaign", 
                "lead", "funnel", "conversion", "seo", "social media", "email marketing",
                "crm", "sales", "strategy", "growth", "kpi", "analytics", "dashboard"]

    # Business frameworks
    FRAMEWORKS = {
        "aarrr": ["Acquisition", "Activation", "Retention", "Referral", "Revenue"],
        "pirate_metrics": ["Acquisition", "Activation", "Retention", "Referral", "Revenue"],
        "jobs_to_be_done": ["Functional Job", "Emotional Job", "Social Job"],
        "value_prop_canvas": ["Customer Profile", "Value Map", "Fit"],
        "business_model_canvas": ["Key Partners", "Key Activities", "Key Resources", "Value Props", 
                                  "Customer Relationships", "Channels", "Customer Segments", 
                                  "Cost Structure", "Revenue Streams"],
        "lean_canvas": ["Problem", "Solution", "Unique Value Prop", "Unfair Advantage", 
                        "Customer Segments", "Key Metrics", "Channels", "Cost Structure", "Revenue Streams"],
        "swot": ["Strengths", "Weaknesses", "Opportunities", "Threats"],
        "pestle": ["Political", "Economic", "Social", "Technological", "Legal", "Environmental"],
        "porter_five": ["Supplier Power", "Buyer Power", "Competitive Rivalry", 
                        "Threat of Substitution", "Threat of New Entry"],
        "okr": ["Objective", "Key Results (3-5 per objective)"],
        "kpi_tree": ["North Star Metric", "Leading Indicators", "Lagging Indicators"],
    }

    MARKETING_CHANNELS = {
        "paid": ["Google Ads", "Meta Ads", "LinkedIn Ads", "Twitter Ads", "TikTok Ads", 
                 "YouTube Ads", "Programmatic", "Native", "Influencer"],
        "owned": ["Website/SEO", "Blog/Content", "Email/Newsletter", "App", "Community", 
                  "Webinars", "Podcast", "Documentation", "Help Center"],
        "earned": ["PR/Media", "Reviews/Testimonials", "Social Shares", "Word of Mouth", 
                   "Referrals", "Case Studies", "Awards", "Speaking"],
    }

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        text = context.get("text", "").lower() if context else ""
        
        if "strategy" in text or "plan" in text:
            return await self._business_strategy(params, text)
        elif "marketing" in text or "campaign" in text:
            return await self._marketing_plan(params, text)
        elif "automation" in text or "workflow" in text or "zapier" in text or "make.com" in text:
            return await self._automation_design(params, text)
        elif "content" in text or "copy" in text or "blog" in text or "social" in text:
            return await self._content_strategy(params, text)
        elif "lead" in text or "funnel" in text or "conversion" in text:
            return await self._funnel_optimization(params, text)
        elif "seo" in text:
            return await self._seo_strategy(params, text)
        elif "analytics" in text or "dashboard" in text or "kpi" in text:
            return await self._analytics_setup(params, text)
        elif "crm" in text or "sales" in text or "pipeline" in text:
            return await self._crm_pipeline(params, text)
        elif "growth" in text or "experiment" in text or "a/b" in text:
            return await self._growth_experiments(params, text)
        elif "framework" in text:
            return await self._show_framework(params.get("framework", ""))
        else:
            return await self._business_help()

    async def _business_strategy(self, params: Dict, text: str) -> str:
        """Generate business strategy using frameworks."""
        stage = params.get("stage", "startup")  # startup, growth, mature, turnaround
        model = params.get("model", "saas")  # saas, ecommerce, marketplace, service, b2b
        
        return f"""**Business Strategy: {model.upper()} - {stage.title()} Stage**

**1. Lean Canvas (One-Page Plan)**
| Problem | Solution | Unique Value Prop |
|---------|----------|-------------------|
| [Top 3 problems] | [Top 3 solutions] | [Clear, compelling UVP] |

| Unfair Advantage | Customer Segments | Key Metrics |
|------------------|-------------------|-------------|
| [Can't be copied/bought] | [Early adopters] | [North Star + 3-5 KPIs] |

| Channels | Cost Structure | Revenue Streams |
|----------|----------------|-----------------|
| [Path to customers] | [Fixed + Variable costs] | [Pricing model, LTV] |

**2. Strategic Priorities ({stage.title()} Stage):**
{self._get_stage_priorities(stage)}

**3. Go-to-Market Strategy:**
- **Target:** [ICP with firmographics/technographics]
- **Positioning:** [Category, differentiation, proof]
- **Pricing:** [Model, tiers, packaging]
- **Launch:** [Phases, channels, timeline]

**4. 90-Day Action Plan:**
| Month | Focus | Key Initiatives | Success Metrics |
|-------|-------|-----------------|-----------------|
| 1 | Foundation | [Setup, research, MVP] | [Leading indicators] |
| 2 | Traction | [Launch, iterate, optimize] | [Activation, retention] |
| 3 | Scale | [Growth loops, hiring, funding] | [Revenue, CAC:LTV] |

**5. Risk Assessment (Pre-mortem):**
- **Technical:** [Risks & mitigations]
- **Market:** [Risks & mitigations]
- **Financial:** [Risks & mitigations]
- **Team:** [Risks & mitigations]

*Want me to dive deeper into any section or apply a specific framework?*"""

    def _get_stage_priorities(self, stage: str) -> str:
        priorities = {
            "startup": """- **Problem-Solution Fit:** Validate problem exists & solution works
- **MVP:** Build minimum viable product for early adopters
- **First Customers:** Get 10-100 paying customers manually
- **Feedback Loops:** Establish rapid iteration cycles
- **Unit Economics:** Prove CAC < LTV at small scale""",
            "growth": """- **Product-Market Fit:** Strong retention, organic growth
- **Scalable Acquisition:** Paid channels with predictable CAC
- **Team Building:** Hire for growth (sales, marketing, CS)
- **Process Documentation:** SOPs, playbooks, systems
- **Series A Prep:** Metrics, narrative, data room""",
            "mature": """- **Market Leadership:** Defend position, expand TAM
- **Operational Excellence:** Margins, efficiency, quality
- **Innovation:** New products, adjacent markets
- **Capital Allocation:** Buybacks, dividends, M&A
- **Succession:** Leadership pipeline, governance""",
            "turnaround": """- **Cash Preservation:** Extend runway, cut burn
- **Core Focus:** Kill non-core, double down on winners
- **Team Reset:** Right people, right seats, culture fix
- **Quick Wins:** Revenue immediately, credibility
- **Restructuring:** Debt, cap table, operations""",
        }
        return priorities.get(stage, priorities["startup"])

    async def _marketing_plan(self, params: Dict, text: str) -> str:
        """Comprehensive marketing plan."""
        budget = params.get("budget", "unknown")
        timeline = params.get("timeline", "90 days")
        goals = params.get("goals", ["awareness", "leads", "revenue"])
        
        return f"""**Marketing Plan: {timeline} | Budget: {budget}**

**Goals:** {', '.join(goals).title()}

**Channel Strategy (Budget Allocation):**
| Channel | % Budget | Priority | KPI | Owner |
|---------|----------|----------|-----|-------|
| Content/SEO | 25% | High | Organic traffic, rankings | Content |
| Paid Search | 20% | High | CAC, ROAS | Growth |
| Paid Social | 20% | High | CAC, CPL | Growth |
| Email/Retention | 15% | Med | LTV, churn | Marketing |
| Partnerships | 10% | Med | Referral revenue | BD |
| Events/PR | 10% | Low | Brand mentions, leads | Marketing |

**Campaign Calendar ({timeline}):**
| Week | Theme | Channels | Content | Offer/CTA |
|------|-------|----------|---------|-----------|
| 1-2 | Launch/Announce | All | Hero content, demo | Free trial/Demo |
| 3-4 | Education | Blog, Email, Social | Guides, webinars | Lead magnet |
| 5-6 | Social Proof | All | Case studies, reviews | Consultation |
| 7-8 | Objection Handling | Email, Retargeting | FAQ, comparisons | Discount/Urgent |
| 9-10 | Expansion | Partnerships, Referral | Co-marketing | Referral bonus |
| 11-12 | Optimization | All | A/B tests, data | Best performers |

**Content Pillars (Weekly Cadence):**
1. **Educational** (Tue) - How-to, tutorials, frameworks
2. **Product** (Thu) - Features, updates, use cases
3. **Social Proof** (Sat) - Customer stories, metrics
4. **Thought Leadership** (Mon) - Industry insights, trends

**Lead Generation Funnel:**
```
Visitor → Lead Magnet → Email Sequence → Demo/Trial → Customer
   ↓          ↓            ↓            ↓           ↓
  SEO/Ads   Landing      Nurture      Sales      Onboard
  Content   Page         Sequence     Process     Success
```

**Key Metrics Dashboard:**
- **Top of Funnel:** Traffic, Impressions, Reach
- **Middle:** Leads, MQLs, SQLs, Conversion Rates
- **Bottom:** Opportunities, Pipeline, Revenue, CAC, LTV
- **Retention:** Churn, NPS, Expansion Revenue

*Want a specific channel deep-dive (SEO, Paid, Email, Content)?*"""

    async def _automation_design(self, params: Dict, text: str) -> str:
        """Business process automation design."""
        return """**Business Automation Architecture**

**Automation Levels:**
| Level | Description | Tools | ROI |
|-------|-------------|-------|-----|
| 1. **Scripts** | Custom Python/JS for repetitive tasks | Python, Node, Cron | High |
| 2. **No-Code** | Visual workflow builders | Zapier, Make, n8n | High |
| 3. **RPA** | UI automation for legacy apps | UiPath, Power Automate | Med |
| 4. **AI Agents** | LLM-powered decision making | LangChain, AutoGPT, Custom | Very High |
| 5. **Platform** | Custom integration platform | Internal API, Webhooks | Highest |

**High-Impact Automation Opportunities:**

**Marketing & Sales:**
- Lead enrichment → CRM (Clearbit + HubSpot)
- Form submission → Slack + Email + CRM
- Webinar registrant → Sequence + Calendar
- Deal stage change → Notifications + Tasks
- Contract sent → DocuSign → Folder → CRM

**Operations:**
- Invoice received → Extract data → Accounting → Approve
- Expense receipt → Categorize → Reimburse → Report
- Support ticket → Categorize → Route → Auto-reply
- Employee onboarding → Accounts → Access → Welcome
- Inventory low → Reorder → PO → Track

**Data & Analytics:**
- Daily: DB → Warehouse → Dashboard → Slack
- Weekly: Metrics → Analysis → Insights → Notion
- Monthly: Cohort analysis → Report → Leadership
- Real-time: Events → Stream → Alert → PagerDuty

**AI-Powered Automations (Next Level):**
- **Content:** Blog outline → Draft → Edit → Publish → Distribute
- **Support:** Ticket → Classify → Draft response → Human review → Send
- **Sales:** Call recording → Summary → CRM update → Next steps
- **Code:** PR → Review → Test → Deploy → Monitor
- **Research:** Topic → Search → Summarize → Report → Share

**Implementation Stack (Recommended):**
```
Orchestration: n8n (self-hosted) or Make.com
Integration: Zapier (easy), Tray.io (enterprise)
AI: LangChain + OpenAI/Anthropic + Vector DB
Data: Airbyte/Fivetran → Snowflake/BigQuery → Metabase
Monitoring: Datadog/Grafana + PagerDuty
Docs: Notion + GitBook
```

**Quick Wins (Start This Week):**
1. **Zapier:** New lead → Slack + CRM + Email sequence
2. **Make.com:** Blog RSS → Social posts → Buffer/Later
3. **n8n:** Daily DB query → CSV → Email → Drive
4. **Python:** Competitor price check → Alert → Sheet

**Governance:**
- Automation inventory (catalog all)
- Owner assignment (who maintains)
- Testing protocol (staging → prod)
- Rollback procedures
- Cost tracking (per automation/month)"""

    async def _content_strategy(self, params: Dict, text: str) -> str:
        """Content marketing strategy."""
        return """**Content Marketing Engine**

**Content Pillars (Choose 3-5):**
1. **Educational** - How-to, tutorials, courses, certifications
2. **Product-Led** - Features, templates, use cases, comparisons
3. **Thought Leadership** - Trends, predictions, frameworks, opinions
4. **Social Proof** - Case studies, testimonials, metrics, interviews
5. **Community** - User stories, AMAs, challenges, showcases
6. **SEO-Driven** - Keywords, clusters, glossary, resources

**Content Formats by Funnel Stage:**
| Stage | Formats | Frequency | Distribution |
|-------|---------|-----------|--------------|
| **TOFU** | Blog, Video, Infographic, Podcast | 3-5/week | SEO, Social, Newsletter |
| **MOFU** | Webinar, Guide, Template, Course | 1-2/week | Email, Retargeting, Partners |
| **BOFU** | Demo, Trial, Case Study, ROI Calc | 2-4/month | Sales, Direct, Events |

**Production Workflow:**
```
Ideation → Research → Outline → Draft → Review → Design → Publish → Distribute → Repurpose
   ↓         ↓          ↓        ↓       ↓       ↓        ↓          ↓           ↓
  AI/Team  AI/Team    AI/Team  AI/Team Human   AI/Design  Auto       Multi-      Multi-
  Tools    Tools      Tools    Tools   Edit    Tools      Schedule    Channel     Format
```

**Repurposing Matrix (1 piece → 10+ assets):**
| Original | → | Derived Assets |
|----------|---|----------------|
| **Blog Post** | → | LinkedIn carousel, Twitter thread, Newsletter section, Video script, Podcast notes, Infographic, Slide deck, FAQ entry, Email sequence, Quote graphics |
| **Webinar** | → | Blog recap, Short clips (Reels/TikTok), Transcript → Blog, Slide deck, Podcast episode, Quote cards, FAQ, Lead magnet PDF |
| **Case Study** | → | One-pager, Slide deck, Video testimonial, Tweet thread, LinkedIn post, Email story, Sales deck insert, Press release |

**SEO Content Clusters:**
```
Pillar Page (3000+ words)
    ├── Cluster Article 1 (1500 words)
    ├── Cluster Article 2 (1500 words)
    ├── Cluster Article 3 (1500 words)
    ├── Cluster Article 4 (1500 words)
    └── Resource Page (Tools, Templates, Glossary)
```

**Content Calendar Template (Monthly):**
| Date | Title | Format | Pillar | Keyword | Stage | Owner | Status |
|------|-------|--------|--------|---------|-------|-------|--------|
| 1st | [Title] | Blog | Educational | [KW] | TOFU | Writer | Draft |
| 3rd | [Title] | Video | Product | [KW] | MOFU | Designer | Scheduled |
| 5th | [Title] | Case Study | Social Proof | [KW] | BOFU | PM | Review |

**AI Content Stack:**
- **Ideation:** ChatGPT/Claude + SEO tools (Ahrefs, SEMrush)
- **Research:** Perplexity, Consensus, Elicit
- **Writing:** Claude (long-form), GPT-4 (structured), Custom prompts
- **Editing:** Grammarly, Hemingway, Human review
- **Design:** Canva API, Figma, Midjourney/DALL-E for images
- **Video:** Descript, HeyGen, Synthesia, Runway
- **Distribution:** Buffer, Later, Hootsuite, Custom n8n

**Quality Checklist (Every Piece):**
- [ ] Target keyword in title, H1, first 100 words
- [ ] Search intent matched (informational/commercial/transactional)
- [ ] Internal links (3-5), External links (2-3 authoritative)
- [ ] Meta title <60 chars, Meta description <155 chars
- [ ] Images: alt text, compressed, WebP
- [ ] Readability: Grade 8-10, short paragraphs, bullets
- [ ] CTA relevant to funnel stage
- [ ] Schema markup (Article, FAQ, HowTo)
- [ ] Social preview cards (OG, Twitter)"""

    async def _funnel_optimization(self, params: Dict, text: str) -> str:
        """Conversion funnel optimization."""
        return """**Conversion Funnel Optimization Framework**

**Funnel Stages & Metrics:**
```
VISITOR (100%)
    ↓  [Conversion Rate: 2-5%]
LEAD (MQL) 
    ↓  [MQL→SQL: 20-30%]
QUALIFIED (SQL)
    ↓  [SQL→Opp: 30-50%]
OPPORTUNITY
    ↓  [Close Rate: 20-30%]
CUSTOMER
    ↓  [Expansion: 10-30%]
ADVOCATE
```

**Diagnostic: Where's the Leak?**
| Stage | Benchmark | Your Rate | Gap | Priority |
|-------|-----------|-----------|-----|----------|
| Visitor → Lead | 2-5% | [?] | [?] | [High/Med/Low] |
| Lead → MQL | 30-50% | [?] | [?] | [High/Med/Low] |
| MQL → SQL | 20-30% | [?] | [?] | [High/Med/Low] |
| SQL → Opp | 30-50% | [?] | [?] | [High/Med/Low] |
| Opp → Close | 20-30% | [?] | [?] | [High/Med/Low] |

**Optimization by Stage:**

**1. Visitor → Lead (TOFU)**
- **Landing Page:** Headline test, Form length, Social proof, Video
- **Lead Magnet:** Relevance, Format (PDF vs Tool vs Course), Delivery speed
- **Traffic Quality:** Source audit, Intent match, Negative keywords
- **Speed:** Page load <3s, Form submit <1s, Mobile UX

**2. Lead → MQL (MOFU - Nurture)**
- **Email Sequence:** 5-7 emails over 14 days
  - Email 1: Deliver magnet + Welcome
  - Email 2: Education + Pain point
  - Email 3: Case study + Social proof
  - Email 4: Objection handling + FAQ
  - Email 5: Soft pitch + Demo/Trial CTA
  - Email 6: Urgency + Bonus
  - Email 7: Last chance + Direct contact
- **Lead Scoring:** Demographic (25%) + Behavioral (75%)
- **Retargeting:** Site visitors, Email openers, Content consumers

**3. MQL → SQL (Sales Handoff)**
- **SLA:** Marketing → Sales within 5 minutes
- **Qualification:** BANT/MEDDIC/CHAMP framework
- **Discovery Call Prep:** Research template, Questions, Demo customization
- **Disqualify Fast:** No budget, no authority, no need, no timeline

**4. SQL → Opportunity (Discovery → Demo)**
- **Discovery Framework:** Situation → Pain → Impact → Critical Event → Decision
- **Demo:** Customized, Outcome-focused, Interactive, 20-30 min max
- **Proposal:** ROI calculator, Implementation plan, References, Timeline
- **Stakeholder Map:** Champion, Economic Buyer, Technical, Legal, End Users

**5. Opportunity → Close (Negotiation)**
- **Pricing:** Anchoring, Tiers, Concessions trade log
- **Contract:** Redlines SLA, Legal review parallel, E-signature
- **Security/Compliance:** SOC2, DPA, Questionnaire library
- **Champion Enablement:** Business case, Battle cards, Talk tracks

**A/B Test Ideas (Prioritized by ICE Score):**
| Test | Impact | Confidence | Ease | ICE | Stage |
|------|--------|------------|------|-----|-------|
| Headline: Benefit vs Feature | High | High | Easy | 9 | TOFU |
| Form: 3 fields vs 5 fields | High | High | Easy | 9 | TOFU |
| CTA: "Get Demo" vs "Start Free" | Med | High | Easy | 8 | TOFU |
| Email: Plain text vs HTML | Med | Med | Easy | 7 | MOFU |
| Demo: 30min vs 60min | High | Med | Med | 7 | SQL |
| Pricing: Annual discount % | High | Med | Med | 7 | Close |
| Proposal: Video vs PDF | Med | Low | Med | 6 | Close |

**Tools Stack:**
- **Analytics:** GA4, Mixpanel, Amplitude, Heap
- **Heatmaps:** Hotjar, Microsoft Clarity, FullStory
- **A/B Testing:** VWO, Optimizely, Google Optimize (free)
- **Forms:** Typeform, Tally, HubSpot Forms
- **Email:** Customer.io, Klaviyo, Braze, HubSpot
- **Chat:** Intercom, Drift, Tidio, Crisp
- **Recording:** Gong, Chorus, Avoma"""

    async def _seo_strategy(self, params: Dict, text: str) -> str:
        """SEO strategy and technical setup."""
        return """**SEO Growth Strategy**

**Three Pillars:**
| Pillar | Focus | Timeline | Investment |
|--------|-------|----------|------------|
| **Technical** | Crawlability, Speed, Indexing | Month 1-2 | Dev time |
| **Content** | Keywords, Clusters, Authority | Month 2-12+ | Ongoing |
| **Authority** | Links, Brand, Trust | Month 3-12+ | PR/Outreach |

**Technical Foundation (Week 1-4):**
```
☐ Google Search Console + Bing Webmaster
☐ GA4 + Enhanced Ecommerce
☐ XML Sitemap (auto-generated)
☐ Robots.txt (allow all, disallow admin)
☐ Canonical tags on all pages
☐ Hreflang (if multi-language)
☐ Schema markup: Organization, Website, Article, FAQ, Product, Breadcrumb
☐ Core Web Vitals: LCP <2.5s, FID <100ms, CLS <0.1
☐ Mobile-first indexing ready
☐ HTTPS everywhere, HSTS
☐ 301 redirects for all migrations
☐ 404 page with search + popular links
☐ Log file analysis (Botify/Screaming Frog)
☐ International targeting (if applicable)
```

**Keyword Strategy:**
| Type | Volume | Difficulty | Intent | Pages |
|------|--------|------------|--------|-------|
| **Head Terms** | 10k+ | High | Broad | Pillar pages |
| **Body** | 1k-10k | Med | Specific | Cluster articles |
| **Long-tail** | 100-1k | Low | Very specific | Blog posts, FAQs |
| **Zero-volume** | <100 | Very Low | Hyper-specific | Programmatic |

**Content Cluster Model:**
```
PILLAR: "Complete Guide to [Topic]" (3000+ words)
│
├── CLUSTER 1: "How to [Subtopic A]" (1500 words) → links to pillar
├── CLUSTER 2: "[Subtopic B] Best Practices" (1500 words) → links to pillar
├── CLUSTER 3: "[Subtopic C] Tools & Templates" (2000 words) → links to pillar
├── CLUSTER 4: "[Subtopic D] Case Studies" (2000 words) → links to pillar
├── CLUSTER 5: "[Subtopic E] FAQ" (Schema FAQ) → links to pillar
└── RESOURCE HUB: Tools, Templates, Glossary, Calculators
```

**Link Building (Month 3+):**
| Tactic | Difficulty | Scale | Quality | Examples |
|--------|------------|-------|---------|----------|
| **Digital PR** | Med | High | High | Data studies, Surveys, Expert roundups |
| **Guest Posting** | Low | Med | Med | Industry blogs, Partner sites |
| **Resource Links** | Low | Med | High | "Best X tools" lists, Directories |
| **Broken Link** | Low | Low | Med | Find 404s, Suggest replacement |
| **Unlinked Mentions** | Low | Low | High | Brand monitoring → Request link |
| **Partnerships** | Med | Low | High | Co-marketing, Integrations |
| **Free Tools** | High | High | High | Calculators, Graders, Generators |

**Programmatic SEO (Scale):**
```
Template Page × Data Set = 1,000+ Pages
Examples:
- "[City] [Service] Cost Calculator" × 500 cities
- "[Tool] vs [Tool] Comparison" × 100 combos
- "[Job Title] Salary in [City]" × 500 cities × 50 roles
- "[Problem] Solution for [Industry]" × 50 industries
```

**Measurement Dashboard:**
| Metric | Tool | Frequency | Target |
|--------|------|-----------|--------|
| Organic Traffic | GA4/GSC | Weekly | +20% QoQ |
| Keyword Rankings | Ahrefs/SEMrush | Weekly | Top 3 for 50+ keywords |
| Organic CTR | GSC | Weekly | >3% for branded, >1% non-branded |
| Indexed Pages | GSC | Weekly | 95%+ of submitted |
| Core Web Vitals | PageSpeed/CrUX | Monthly | All Green |
| Backlinks (referring domains) | Ahrefs | Monthly | +10% MoM |
| Domain Rating | Ahrefs | Monthly | +5 points/quarter |
| Organic Conversions | GA4 | Weekly | Track by landing page |

**Quick Wins (Week 1):**
1. Fix 404s with traffic/backlinks → 301 to relevant page
2. Add FAQ schema to top 10 pages
3. Optimize title tags for CTR (add year, benefit, number)
4. Compress images >100KB → WebP
5. Internal link orphan pages from top content
6. Submit updated sitemap
7. Claim/optimize Google Business Profile
8. Set up GSC alerts for coverage issues"""

    async def _analytics_setup(self, params: Dict, text: str) -> str:
        """Analytics and dashboard setup."""
        return """**Analytics & Dashboard Architecture**

**Modern Data Stack:**
```
SOURCES → INGESTION → WAREHOUSE → TRANSFORM → BI → ACTION
   ↓           ↓           ↓          ↓         ↓       ↓
App/DB    Airbyte/    Snowflake/   dbt/       Metabase/  Reverse
Events    Fivetran    BigQuery     SQLMesh    Superset/  ETL
Web       Stitch      Redshift     SQL        Looker/    (Census/
Ads       Kafka       Postgres     Material.  Tableau/   Hightouch)
CRM       Custom                        Views      PowerBI   Zapier)
Email                                                             
```

**North Star Metric Framework:**
```
Company North Star: [One metric that captures core value]
    │
    ├── Input Metrics (Leading - you can influence directly)
    │   ├── Acquisition: [Signups, Trials, Demos]
    │   ├── Activation: [Aha moments, Setup completion]
    │   ├── Retention: [DAU/MAU, Feature adoption]
    │   ├── Referral: [Invites sent, Conversion rate]
    │   └── Revenue: [MRR, ARPU, Expansion]
    │
    └── Output Metrics (Lagging - result of inputs)
        ├── ARR/MRR Growth
        ├── Net Revenue Retention
        ├── CAC Payback Period
        └── LTV:CAC Ratio
```

**Dashboard Hierarchy:**

**1. Executive (Daily/Weekly):**
- North Star + 4-5 KPIs
- Revenue: MRR, ARR, Growth %, NRR
- Customers: Total, New, Churned, Net New
- Efficiency: CAC, LTV, CAC:LTV, Payback
- Cash: Runway, Burn, Net Cash Flow

**2. Department (Daily):**
| Dept | Primary Metrics | Secondary |
|------|-----------------|-----------|
| **Marketing** | MQLs, CAC, ROAS, Pipeline | Traffic, Leads, CPL by channel |
| **Sales** | Pipeline, Close Rate, Cycle | Activities, SQLs, Avg Deal |
| **Product** | DAU/MAU, Retention, Adoption | Feature usage, NPS, Churn reasons |
| **CS** | NPS, CSAT, Response Time | Expansion, Renewal, Health Score |
| **Eng** | Deploy freq, Lead time, MTTR | Bugs, Uptime, Tech Debt |

**3. Operational (Real-time):**
- Website: Traffic, Conversions, Errors
- API: Latency, Error rate, Throughput
- Database: Connections, Slow queries, Locks
- Infrastructure: CPU, Memory, Disk, Cost

**Key Dashboards to Build:**

**Marketing Dashboard:**
```
┌─────────────────────────────────────────────────────────────┐
│  CHANNEL PERFORMANCE (Last 30 days)                        │
├─────────┬────────┬───────┬──────┬──────┬──────┬────────────┤
│ Channel │ Spend  │ Leads │ CPL  │ MQLs │ SQLs │ CAC (est)  │
├─────────┼────────┼───────┼──────┼──────┼──────┼────────────┤
│ Google  │ $15k   │ 450   │ $33  │ 180  │ 45   │ $333       │
│ Meta    │ $10k   │ 300   │ $33  │ 90   │ 18   │ $555       │
│ LinkedIn│ $8k    │ 120   │ $67  │ 60   │ 15   │ $533       │
│ Organic │ $0     │ 200   │ $0   │ 100  │ 25   │ $0         │
│ Email   │ $2k    │ 80    │ $25  │ 40   │ 10   │ $200       │
├─────────┼────────┼───────┼──────┼──────┼──────┼────────────┤
│ TOTAL   │ $35k   │ 1150  │ $30  │ 470  │ 113  │ $310       │
└─────────┴────────┴───────┴──────┴──────┴──────┴────────────┘
```

**Cohort Retention Dashboard:**
```
┌──────────────────────────────────────────────────────────────┐
│  USER RETENTION COHORTS (Monthly)                            │
├────────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬────┤
│ Cohort │ Size │ M1   │ M2   │ M3   │ M4   │ M5   │ M6   │ M12│
├────────┼──────┼──────┼──────┼──────┼──────┼──────┼──────┼────┤
│ Jan 24 │ 500  │ 85%  │ 72%  │ 65%  │ 60%  │ 58%  │ 55%  │ 48%│
│ Feb 24 │ 520  │ 87%  │ 75%  │ 68%  │ 62%  │ 59%  │ 57%  │ -  │
│ Mar 24 │ 580  │ 84%  │ 70%  │ 63%  │ 59%  │ 56%  │ -    │ -  │
│ Apr 24 │ 610  │ 88%  │ 76%  │ 69%  │ 64%  │ -    │ -    │ -  │
│ May 24 │ 650  │ 86%  │ 73%  │ 66%  │ -    │ -    │ -    │ -  │
│ Jun 24 │ 700  │ 89%  │ 77%  │ -    │ -    │ -    │ -    │ -  │
└────────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┴────┘
```

**Implementation Checklist:**
- [ ] Define North Star + 10-15 KPIs
- [ ] Set up data warehouse (BigQuery free tier)
- [ ] Configure ingestion (Airbyte Cloud free)
- [ ] Build dbt models for core entities
- [ ] Create 3 dashboards (Exec, Dept, Ops)
- [ ] Set up alerts (Slack/PagerDuty)
- [ ] Document definitions (Data Dictionary)
- [ ] Schedule weekly/monthly reviews
- [ ] Assign data owners per domain

**Tools by Budget:**
| Budget | Ingestion | Warehouse | Transform | BI | Alerting |
|--------|-----------|-----------|-----------|-----|----------|
| **Free** | Airbyte OSS | BigQuery | dbt Core | Metabase | Grafana |
| **$500/mo** | Fivetran | BigQuery | dbt Cloud | Metabase | PagerDuty |
| **$2k/mo** | Fivetran | Snowflake | dbt Cloud | Looker | PagerDuty |
| **$10k+/mo** | Segment | Snowflake | dbt + Coalesce | Tableau | Datadog |"""

    async def _crm_pipeline(self, params: Dict, text: str) -> str:
        """CRM and sales pipeline design."""
        return """**CRM & Sales Pipeline Architecture**

**Pipeline Stages (B2B SaaS Example):**
| Stage | Definition | Entry Criteria | Exit Criteria | Probability | SLA |
|-------|------------|----------------|---------------|-------------|-----|
| **1. Prospect** | Identified fit | ICP match, Contact info | Reply/Meeting booked | 5% | 5 days |
| **2. Qualified** | Pain + Budget + Authority | Discovery call done | Demo scheduled | 15% | 3 days |
| **3. Demo** | Solution presented | Demo completed | Proposal sent | 30% | 5 days |
| **4. Proposal** | Commercial terms sent | Proposal delivered | Negotiation started | 50% | 7 days |
| **5. Negotiation** | Terms discussed | Redlines received | Verbal commit | 70% | 10 days |
| **6. Contract** | Legal review | Contract sent | Signed | 90% | 5 days |
| **7. Closed Won** | Signed + Payment | Payment received | Onboarding started | 100% | - |
| **Closed Lost** | Any reason | Disqualified | Reason documented | 0% | - |

**Required Fields per Stage:**
| Stage | Required Fields | Auto-Populate |
|-------|-----------------|---------------|
| All | Contact, Company, Owner, Source, Created Date | From form/enrichment |
| Qualified | Pain Points, Budget, Authority, Timeline, Competitor | Discovery notes |
| Demo | Demo Recording, Features Shown, Objections, Next Steps | Gong/Chorus |
| Proposal | Quote Amount, Terms, Expiry, Decision Makers | CPQ/PandaDoc |
| Negotiation | Redline Log, Concessions, Champion Status | Manual |
| Contract | Contract Link, Legal Contacts, Start Date | DocuSign/Ironclad |

**Lead Scoring Model:**
```
DEMOGRAPHIC (25 points max):
├── Company Size: 1-10 (5), 11-50 (10), 51-200 (15), 200+ (25)
├── Industry: Target (15), Adjacent (10), Other (5)
├── Role: Decision Maker (15), Influencer (10), User (5)
├── Tech Stack: Compatible (10), Neutral (5), Competitor (0)
└── Location: Primary (5), Secondary (3), Other (0)

BEHAVIORAL (75 points max):
├── Website: Pricing page (10), Docs (10), Blog (5), Careers (-5)
├── Email: Opened 3+ (10), Clicked (15), Replied (25)
├── Content: Downloaded guide (10), Webinar attended (15), Tool used (20)
├── Product: Free trial started (25), Feature used (15), Invite sent (10)
├── Events: Demo requested (30), Chat started (15), Meeting booked (25)
└── Negative: Unsubscribed (-20), Bounced (-10), Spam (-50)

THRESHOLDS:
- MQL: 50+ points
- SQL: 75+ points + Qualified by SDR
- PQL (Product Qualified): Trial + 2+ key actions
```

**CRM Hygiene Rules:**
- [ ] Every contact has: Email, Phone, Company, Owner, Source, Lead Status
- [ ] Every deal has: Amount, Close Date, Stage, Next Step, Competitor
- [ ] No stale deals >30 days without activity → Auto-move to nurture
- [ ] Duplicate check: Weekly dedupe (email, domain, name+company)
- [ ] Data enrichment: Clearbit/Apollo on create + quarterly refresh
- [ ] Required fields enforced at stage gates

**Sales Activity Cadence (Per Deal):**
| Stage | Activities/Week | Types |
|-------|-----------------|-------|
| Prospect | 5-7 | Call, Email, LinkedIn, Video |
| Qualified | 3-5 | Call, Email, Resource share |
| Demo | 2-3 | Demo, Follow-up, Stakeholder map |
| Proposal | 2-3 | Call, Email, Case study |
| Negotiation | 3-5 | Call, Email, Concession log |
| Contract | 2-3 | Legal coord, Signature chase |

**Forecasting Methodology:**
```
Commit (90%+): Deals in Contract stage + verbal
Best Case (70%): Commit + Negotiation with champion
Pipeline (30%): Best Case + Proposal + Demo qualified
Upside (10%): Pipeline + Early stage with high fit
```

**Key Reports:**
1. **Pipeline Waterfall** - Stage conversion rates, velocity
2. **Rep Scorecard** - Activity, Pipeline, Win Rate, Avg Deal
3. **Source ROI** - Leads, MQLs, SQLs, Revenue by source
4. **Cohort Analysis** - Win rates by entry month/quarter
5. **Slippage Report** - Deals pushing close date
6. **Competitive Wins/Losses** - By competitor, reason

**Automation Rules:**
- Lead created → Assign owner (round-robin/territory) → Enrich → Notify
- MQL threshold hit → Create deal in Qualified → Assign SDR → Sequence
- Demo completed → Move to Demo stage → Create Proposal task
- Proposal sent → 3-day follow-up task → 7-day expiry alert
- Contract signed → Move to Closed Won → Trigger onboarding → Notify CS
- No activity 14 days → Alert owner → Auto-nurture sequence

**Tools Comparison:**
| CRM | Best For | Price | Strengths |
|-----|----------|-------|-----------|
| **HubSpot** | SMB, Inbound | Free-$3.6k/mo | All-in-one, Easy, Free tier |
| **Salesforce** | Enterprise, Complex | $25-300/user | Customization, Ecosystem, Scale |
| **Pipedrive** | Sales-led, Visual | $15-99/user | Pipeline view, Simple, Affordable |
| **Close** | High-velocity, Calling | $29-149/user | Built-in calling, Automation |
| **Attio** | Modern, Flexible | $15-50/user | Notion-like, API-first, Real-time |
| **Folk** | Relationship-led | $18-36/user | Network view, Enrichment, Light |"""

    async def _growth_experiments(self, params: Dict, text: str) -> str:
        """Growth experimentation framework."""
        return """**Growth Experimentation System**

**Experiment Process (Build-Measure-Learn):**
```
1. IDEATE → 2. PRIORITIZE → 3. DESIGN → 4. BUILD → 5. LAUNCH → 6. ANALYZE → 7. DECIDE → REPEAT
```

**ICE Prioritization Framework:**
| Experiment | Impact (1-10) | Confidence (1-10) | Ease (1-10) | ICE Score | Rank |
|------------|---------------|-------------------|-------------|-----------|------|
| [Test idea] | [ ] | [ ] | [ ] | [ ] | [ ] |

**Experiment Template:**
```markdown
## Experiment: [Name]

### Hypothesis
**If we** [change X] **then** [metric Y] **will** [increase/decrease by Z%]
**Because** [psychological/behavioral reasoning]

### Metrics
- **Primary:** [Single metric that determines success]
- **Secondary:** [Guardrail metrics - don't let these drop]
- **Counter:** [Opposite behavior to watch]

### Design
- **Variants:** Control (A) vs Treatment (B) [+ C, D if multivariate]
- **Traffic Split:** 50/50 (or 90/10 for risky)
- **Audience:** [Segment - new users, mobile, specific page, etc.]
- **Duration:** [Minimum days + sample size calculator]
- **Sample Size:** [Use calculator: baseline rate, MDE, power=80%, sig=95%]

### Implementation
- **Tools:** [VWO, Optimizely, GA Experiments, Custom]
- **Code/Config:** [Link to PR, feature flag, config]
- **QA Checklist:** [Cross-browser, mobile, analytics firing]

### Launch Checklist
- [ ] Hypothesis documented
- [ ] Sample size calculated
- [ ] Analytics events verified
- [ ] QA passed (staging)
- [ ] Rollback plan ready
- [ ] Stakeholders notified
- [ ] Launch scheduled

### Analysis Plan
- **Statistical Test:** [t-test, chi-square, Bayesian]
- **Significance:** [95% confidence, p<0.05]
- **Practical Significance:** [MDE - Minimum Detectable Effect]
- **Segmentation:** [Check: device, source, geo, new/returning]
- **Long-term:** [Check after 1, 2, 4 weeks for novelty effects]

### Decision Rules
- **Ship:** Primary metric +stat sig + practical sig, no guardrail harm
- **Iterate:** Promising but underpowered or segment-specific win
- **Kill:** No effect, negative, or guardrail violation
- **Investigate:** Unexpected results, bugs, seasonality
```

**Experiment Categories & Ideas:**

**Acquisition (Top of Funnel):**
| Area | Experiments |
|------|-------------|
| **Landing Page** | Headline (benefit vs feature), Hero image (illustration vs photo vs video), Form length, Social proof type, CTA copy/color |
| **Paid Ads** | Hook (pain vs gain), Format (image vs video vs carousel), Audience (broad vs lookalike vs interest), Offer (trial vs demo vs guide) |
| **SEO** | Title tag (number vs question vs how-to), Meta description (CTR focus), Content depth, Schema type, Internal linking |
| **Referral** | Incentive (cash vs credit vs swag), Timing (immediate vs delay), Double-sided vs single, Sharing mechanism |

**Activation (First Value):**
| Area | Experiments |
|------|-------------|
| **Onboarding** | Steps (fewer vs more guided), Empty state (template vs blank), Tooltips (progressive vs all), Checklist vs free-form |
| **First Session** | Time to value (reduce), Feature discovery (highlight vs hide), Sample data (real vs demo), Success message |
| **Email/In-App** | Welcome timing, Sequence length, Channel mix, Personalization level |

**Retention (Ongoing Value):**
| Area | Experiments |
|------|-------------|
| **Engagement** | Notification timing/frequency, Content recommendations, Gamification (streaks, badges), Social features |
| **Re-activation** | Win-back email sequence, Incentive type, Channel (email vs push vs SMS), Timing (7d vs 30d vs 90d) |
| **Expansion** | Upgrade prompts (usage vs time vs feature), Trial extension, Annual discount, Team invite flow |

**Revenue (Monetization):**
| Area | Experiments |
|------|-------------|
| **Pricing** | Price points, Packaging (features vs usage vs seats), Annual discount %, Trial length, Freemium limits |
| **Checkout** | Steps (1 vs 2 vs 3), Fields, Payment methods, Trust signals, Guest vs account |
| **Upsell** | Timing (in-app vs email), Trigger (usage vs time), Offer (discount vs features), Urgency |

**Statistical Rigor Checklist:**
- [ ] Sample size calculated BEFORE launch
- [ ] Random assignment verified (SRM check)
- [ ] No peeking (sequential testing if needed)
- [ ] Guardrail metrics monitored
- [ ] Segment analysis pre-planned
- [ ] Documentation complete for knowledge base
- [ ] Results shared regardless of outcome

**Experiment Velocity Target:**
| Stage | Experiments/Month | Win Rate | Learning Rate |
|-------|-------------------|----------|---------------|
| **Early** | 2-4 | 10-20% | High |
| **Growth** | 8-15 | 20-30% | High |
| **Scale** | 20-50 | 25-35% | Med |
| **Mature** | 50+ | 30-40% | Med |

**Tools Stack:**
- **Ideation:** Notion, Airtable, Jira Product Discovery
- **Prioritization:** ICE sheet, Reforge template
- **A/B Testing:** VWO, Optimizely, Statsig, GrowthBook, GA4
- **Feature Flags:** LaunchDarkly, Unleash, Flipper, Custom
- **Analytics:** Mixpanel, Amplitude, Heap, PostHog
- **Qualitative:** Hotjar, FullStory, UserTesting, Sprig
- **Documentation:** Notion, Confluence, GitBook"""

    async def _show_framework(self, framework: str) -> str:
        """Display business framework."""
        frameworks = {
            "aarrr": """**AARRR (Pirate Metrics) - Dave McClure**
| Stage | Question | Key Metrics | Tactics |
|-------|----------|-------------|---------|
| **Acquisition** | How do users find us? | Visitors, CAC by channel, Source mix | SEO, Paid, Referral, Content, PR |
| **Activation** | Do they get value fast? | Activation rate, Time to value, Setup % | Onboarding, Templates, Tours, Checklists |
| **Retention** | Do they come back? | DAU/MAU, N-day retention, Churn | Habit loops, Notifications, Email, Value |
| **Referral** | Do they tell others? | Viral coefficient, Referral rate, NPS | Incentives, Sharing, Social proof, Affiliate |
| **Revenue** | Do they pay? | MRR, ARPU, LTV, Payback, NRR | Pricing, Upsell, Expansion, Renewal |""",
            "lean_canvas": """**Lean Canvas - Ash Maurya**
| Problem | Solution | Unique Value Prop | Unfair Advantage | Customer Segments |
|---------|----------|-------------------|------------------|-------------------|
| Top 3 problems | Top 3 features | Clear, compelling | Can't copy/buy | Early adopters |

| Key Metrics | Channels | Cost Structure | Revenue Streams |
|-------------|----------|----------------|-----------------|
| North Star + 3-5 | Path to customers | Fixed + Variable | Pricing, LTV |""",
            "jobs_to_be_done": """**Jobs To Be Done - Clayton Christensen**
**Job Statement:** "When [situation], I want to [motivation], so I can [outcome]."

**Three Job Types:**
1. **Functional** - Practical task completion
2. **Emotional** - How user wants to feel
3. **Social** - How user wants to be perceived

**Forces of Progress:**
- **Push** - Pain of current solution
- **Pull** - Attraction of new solution
- **Anxiety** - Fears about new solution
- **Habit** - Comfort with current way""",
            "business_model_canvas": """**Business Model Canvas - Alexander Osterwalder**
| Key Partners | Key Activities | Value Propositions | Relationships | Segments |
|--------------|----------------|--------------|---------------|----------|
| Suppliers, Alliances | Production, Marketing | Products/Services | Personal, Automated | Mass, Niche, Multi-sided |

| Key Resources | Channels |
|---------------|----------|
| Physical, IP, Human, Financial | Awareness, Evaluation, Purchase, Delivery, After-sales |

| Cost Structure | Revenue Streams |
|----------------|-----------------|
| Fixed, Variable, Economies | Asset sale, Usage fee, Subscription, Licensing, Brokerage, Advertising |""",
            "okr": """**OKRs - Objectives & Key Results (Andy Grove/John Doerr)**

**Formula:** I will [Objective] as measured by [Key Results]

**Characteristics:**
- **Objectives:** Qualitative, ambitious, time-bound, inspirational
- **Key Results:** Quantitative, measurable, 3-5 per objective, leading indicators

**Example:**
> **O:** Become the market leader in [category]
> **KR1:** Grow ARR from $2M → $5M
> **KR2:** Achieve NRR > 120%
> **KR3:** Reduce CAC payback from 12 → 6 months
> **KR4:** Launch in 3 new verticals with $500k+ pipeline each

**Cadence:**
- **Annual:** Company OKRs (3-5)
- **Quarterly:** Team OKRs (3-5 per team)
- **Weekly:** Check-ins (confidence scoring)
- **Grading:** 0.0-1.0 (0.7 = success, 1.0 = sandbagged)""",
        }
        return frameworks.get(framework.lower(), f"Framework '{framework}' not found. Available: {', '.join(frameworks.keys())}")

    async def _business_help(self) -> str:
        return """**Business Skill Commands:**

**Strategy & Planning:**
- "Business strategy for B2B SaaS startup"
- "Lean canvas for AI productivity tool"
- "OKRs for Q1: grow ARR 3x"
- "Porter's five forces for CRM market"

**Marketing:**
- "90-day marketing plan for Series A startup"
- "Content pillars for developer tool"
- "SEO strategy for vertical SaaS"
- "Channel mix for $50k/mo budget"

**Automation:**
- "Automation opportunities for marketing team"
- "n8n workflow: lead → enrich → CRM → Slack"
- "AI agent for support ticket triage"
- "Data pipeline: PostgreSQL → BigQuery → Metabase"

**Funnel & Conversion:**
- "Funnel diagnostic: visitor to customer"
- "Landing page optimization checklist"
- "Email nurture sequence for trial users"
- "Pricing page A/B test ideas"

**Analytics:**
- "North Star metric for marketplace"
- "Executive dashboard metrics"
- "Cohort retention analysis setup"
- "Marketing attribution model"

**CRM & Sales:**
- "B2B sales pipeline stages"
- "Lead scoring model for enterprise"
- "Sales forecast methodology"
- "Rep scorecard template"

**Growth Experiments:**
- "Experiment template for onboarding"
- "ICE prioritization for 10 ideas"
- "A/B test: headline benefit vs feature"
- "Sample size calculator for 5% lift"

**Frameworks (type "framework [name]"):**
- aarrr, lean_canvas, jobs_to_be_done, business_model_canvas, okr, swot, pestle, porter_five, kpi_tree

*Provide context: business model, stage, target market, current metrics!*"""