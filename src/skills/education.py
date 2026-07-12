"""Education & Curriculum Skill for JARVIS - Kindergarten through University."""
from typing import Any, Dict, List
from src.skills.registry import Skill


class EducationSkill(Skill):
    """Education, curriculum planning, and learning management."""

    name = "education"
    description = "Curriculum design, lesson plans, educational content for all levels"
    triggers = ["curriculum", "lesson plan", "teach", "education", "school", "kindergarten", 
                "homeschool", "syllabus", "learning objectives", "assessment", "rubric"]

    # Common Core / State Standards references
    STANDARDS = {
        "common_core": {
            "math": ["CCSS.MATH.CONTENT.K.CC.A.1", "CCSS.MATH.CONTENT.1.OA.A.1", ...],
            "ela": ["CCSS.ELA-LITERACY.RF.K.1", "CCSS.ELA-LITERACY.RL.1.1", ...],
        },
        "ngss": ["K-PS2-1", "K-LS1-1", "K-ESS2-1", ...],
        "c3": ["D2.His.1.K-2", "D2.Geo.1.K-2", ...],
    }

    GRADE_LEVELS = {
        "prek": "Pre-Kindergarten (Ages 3-4)",
        "k": "Kindergarten (Ages 5-6)",
        "1": "1st Grade (Ages 6-7)",
        "2": "2nd Grade (Ages 7-8)",
        "3": "3rd Grade (Ages 8-9)",
        "4": "4th Grade (Ages 9-10)",
        "5": "5th Grade (Ages 10-11)",
        "6": "6th Grade (Ages 11-12)",
        "7": "7th Grade (Ages 12-13)",
        "8": "8th Grade (Ages 13-14)",
        "9": "9th Grade (Ages 14-15)",
        "10": "10th Grade (Ages 15-16)",
        "11": "11th Grade (Ages 16-17)",
        "12": "12th Grade (Ages 17-18)",
    }

    SUBJECTS = {
        "ela": "English Language Arts",
        "math": "Mathematics",
        "science": "Science",
        "social_studies": "Social Studies",
        "art": "Visual Arts",
        "music": "Music",
        "pe": "Physical Education",
        "health": "Health Education",
        "tech": "Technology/Computer Science",
        "sel": "Social-Emotional Learning",
        "world_lang": "World Languages",
    }

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        text = context.get("text", "").lower() if context else ""
        
        if "curriculum" in text or "syllabus" in text:
            return await self._generate_curriculum(params, text)
        elif "lesson plan" in text or "lesson" in text:
            return await self._generate_lesson_plan(params, text)
        elif "assessment" in text or "rubric" in text or "test" in text:
            return await self._create_assessment(params, text)
        elif "kindergarten" in text or "pre-k" in text or "prek" in text:
            return await self._early_childhood_content(params, text)
        elif "homeschool" in text:
            return await self._homeschool_plan(params, text)
        elif "scope" in text and "sequence" in text:
            return await self._scope_sequence(params, text)
        elif "iep" in text or "504" in text or "accommodation" in text:
            return await self._special_education(params, text)
        else:
            return await self._education_help()

    async def _generate_curriculum(self, params: Dict, text: str) -> str:
        """Generate full curriculum map."""
        grade = self._extract_grade(text)
        subject = self._extract_subject(text)
        duration = params.get("duration", "year")
        
        return f"""**Curriculum Map: {self.SUBJECTS.get(subject, subject).title()} - {self.GRADE_LEVELS.get(grade, grade).title()}**

**Duration:** {duration.title()} ({self._get_weeks(duration)} weeks)

**Unit Overview:**
1. **Unit 1: Foundations** (Weeks 1-4)
   - Standards: {self._get_standards(subject, grade, 1)}
   - Essential Questions: [Big ideas]
   - Key Vocabulary: [Terms]
   - Assessments: Diagnostic, Formative

2. **Unit 2: Core Concepts** (Weeks 5-12)
   - Standards: {self._get_standards(subject, grade, 2)}
   - Essential Questions: [...]
   - Key Vocabulary: [...]
   - Assessments: Quizzes, Projects

3. **Unit 3: Application & Extension** (Weeks 13-24)
   - Standards: {self._get_standards(subject, grade, 3)}
   - Essential Questions: [...]
   - Key Vocabulary: [...]
   - Assessments: Performance Tasks

4. **Unit 4: Mastery & Review** (Weeks 25-36)
   - Standards: {self._get_standards(subject, grade, 4)}
   - Essential Questions: [...]
   - Assessments: Summative, Portfolio

**Pacing Guide:** [Detailed week-by-week breakdown]
**Resources:** Textbooks, Digital Tools, Manipulatives, Literature
**Differentiation:** Tier 1/2/3 interventions, Extensions
**Parent Communication:** Monthly newsletters, Conferences

*Want me to expand any unit with daily lesson plans?*"""

    async def _generate_lesson_plan(self, params: Dict, text: str) -> str:
        """Generate detailed lesson plan."""
        grade = self._extract_grade(text)
        subject = self._extract_subject(text)
        topic = params.get("topic", self._extract_topic(text))
        duration = params.get("duration", "45-60 minutes")
        
        return f"""**Lesson Plan: {topic}**
**Grade:** {self.GRADE_LEVELS.get(grade, grade)}
**Subject:** {self.SUBJECTS.get(subject, subject)}
**Duration:** {duration}
**Standards:** {self._get_standards(subject, grade, 1)}

---
### **Learning Objectives** (SWBAT)
- Students will be able to [specific, measurable objective 1]
- Students will be able to [specific, measurable objective 2]
- Students will be able to [specific, measurable objective 3]

### **Essential Question**
[Big question driving the lesson]

### **Vocabulary**
Tier 1: [Common words] | Tier 2: [Academic words] | Tier 3: [Content-specific]

### **Materials & Resources**
- Teacher: [Slides, manipulatives, texts]
- Students: [Worksheets, devices, notebooks]
- Technology: [Apps, websites, tools]

### **Lesson Sequence** ({duration})
| Time | Phase | Teacher Actions | Student Actions | Assessment |
|------|-------|-----------------|-----------------|------------|
| 5 min | **Hook/Activator** | [Engage prior knowledge] | [Think-pair-share, quick write] | Observation |
| 10 min | **Mini-Lesson** | [Model, demonstrate, explain] | [Listen, take notes, ask questions] | Check for understanding |
| 15 min | **Guided Practice** | [Scaffold, prompt, feedback] | [Practice with support] | Formative - exit ticket |
| 15 min | **Independent Practice** | [Circulate, confer] | [Apply independently] | Work sample |
| 5 min | **Closure** | [Summarize, connect] | [Reflect, preview next] | Exit ticket |

### **Differentiation**
- **ELL:** Sentence frames, visuals, bilingual glossary
- **IEP/504:** [Specific accommodations]
- **Extension:** [Challenge activities]
- **Tier 2:** [Small group reteach]

### **Assessment**
- **Formative:** [Exit ticket, whiteboard, observation]
- **Summative:** [Quiz, project, writing piece]
- **Rubric:** [4-point scale with criteria]

### **Homework/Extension**
[Practice, reading, family connection]

*Want a specific grade/subject/topic? Provide details!*"""

    async def _early_childhood_content(self, params: Dict, text: str) -> str:
        """Pre-K/Kindergarten specific content."""
        return """**Early Childhood Education (Pre-K/K) Framework**

**Developmental Domains:**
1. **Approaches to Learning** - Curiosity, persistence, creativity
2. **Social-Emotional** - Self-awareness, relationships, self-regulation
3. **Language & Literacy** - Listening, speaking, emergent reading/writing
4. **Cognition** - Math, science, social studies, logic
5. **Physical Development** - Gross/fine motor, health/safety

**Kindergarten Year-at-a-Glance:**
| Month | Literacy Focus | Math Focus | Theme/Unit |
|-------|---------------|------------|------------|
| Aug/Sep | Names, letters, sounds | Counting 0-10, shapes | All About Me / School |
| Oct | Letter-sound correspondence | Numbers 0-20, patterns | Fall / Community Helpers |
| Nov | CVC words, sight words | Addition concepts | Thanksgiving / Gratitude |
| Dec | Emergent reading | Subtraction concepts | Holidays Around World |
| Jan | Reading strategies | Teen numbers | Winter / Animals |
| Feb | Writing sentences | Measurement | Friendship / Dental Health |
| Mar | Fluency practice | 2D/3D shapes | Spring / Plants |
| Apr | Comprehension | Addition/subtraction fluency | Earth / Recycling |
| May | Independent reading/writing | Review & extend | Summer / Transition |

**Daily Schedule (Full-Day K):**
- 8:00-8:30 Arrival/Morning Work
- 8:30-9:00 Morning Meeting (SEL, Calendar)
- 9:00-10:30 Literacy Block (Phonics, Reading, Writing)
- 10:30-11:00 Recess
- 11:00-11:45 Math Block
- 11:45-12:30 Lunch/Recess
- 12:30-1:00 Quiet Time/Rest
- 1:00-1:45 Science/Social Studies/Art (rotating)
- 1:45-2:15 Centers/Play-Based Learning
- 2:15-2:30 Closing Circle/Dismissal

**Assessment:** Teaching Strategies GOLD, DIBELS, Running Records, Portfolios

**Family Engagement:** Weekly newsletters, Seesaw/ClassDojo, Conferences 2x/year"""

    async def _homeschool_plan(self, params: Dict, text: str) -> str:
        """Homeschool curriculum planning."""
        return """**Homeschool Curriculum Planner**

**Legal Requirements (Check Your State):**
- Notice of Intent / Letter of Intent
- Attendance Records (180 days typical)
- Portfolio / Work Samples
- Annual Assessment (testing/portfolio review)
- Immunization Records / Exemptions

**Curriculum Styles:**
| Approach | Best For | Examples |
|----------|----------|----------|
| Traditional/Textbook | Structure, college prep | Abeka, BJU, Saxon |
| Classical | Critical thinking, language | Memoria Press, Veritas |
| Charlotte Mason | Living books, nature | Ambleside, Simply CM |
| Unit Studies | Integration, interest-led | Gather Round, UnitStudy.com |
| Unschooling | Self-directed | Interest-based |
| Eclectic | Mix & match | Custom blend |

**Sample 1st Grade Schedule (4 days/week):**
- **Mon/Wed:** Math (30min), LA (45min), Science (30min), Read-aloud (15min)
- **Tue/Thu:** Math (30min), LA (45min), History (30min), Art/Music (30min)
- **Fri:** Field trip, Nature study, Projects, Review, Co-op

**Record Keeping:**
- **Planner:** Weekly lesson plans, daily logs
- **Portfolio:** Work samples, photos, projects
- **Transcripts:** Courses, grades, credits (HS)
- **Testing:** Standardized (annual), Curriculum-based (ongoing)

**Resources:**
- **Free:** Khan Academy, CK-12, Easy Peasy, Ambleside Online
- **Low Cost:** The Good & The Beautiful, Master Books
- **Complete:** Time4Learning, Oak Meadow, BookShark
- **Co-ops:** Local homeschool groups, online (Outschool)

**High School Credits (Typical):**
- English: 4 credits | Math: 3-4 | Science: 3-4 | History: 3-4
- Foreign Language: 2 | PE: 1 | Health: 0.5 | Electives: 4-6
- **Total: 22-26 credits**

*What grade level(s) and approach interests you?*"""

    async def _special_education(self, params: Dict, text: str) -> str:
        """IEP/504 accommodations and modifications."""
        return """**Special Education: IEP & 504 Quick Reference**

**IEP vs 504 Plan:**
| Feature | IEP (IDEA) | 504 Plan (Rehab Act) |
|---------|-----------|---------------------|
| Eligibility | 13 disability categories | Any disability limiting major life activity |
| Services | Specialized instruction + related services | Accommodations only |
| Review | Annual + triennial re-eval | Annual (best practice) |
| Team | Required: Parent, Gen Ed, Sp Ed, Admin, Student (if 14+) | Flexible |

**Common Accommodations (Presentation):**
- Audiobooks / Text-to-speech
- Large print / High contrast materials
- Preferential seating
- Visual schedules / Graphic organizers
- Chunked instructions (1-2 steps at a time)
- Copies of notes / Teacher notes
- Reduced visual clutter

**Common Accommodations (Response):**
- Oral responses / Scribe
- Speech-to-text / Word processor
- Extended time (1.5x, 2x)
- Reduced answer choices
- Reference sheets / Formula cards
- Calculator / Math manipulatives

**Common Accommodations (Setting):**
- Separate testing location
- Small group instruction
- Noise-canceling headphones
- Movement breaks / Sensory tools
- Flexible seating

**Common Accommodations (Timing/Scheduling):**
- Extended time on assignments/tests
- Frequent breaks
- Chunked assignments
- Priority scheduling (hard subjects AM)
- Reduced homework load

**Modifications (Change WHAT is taught):**
- Reduced complexity / Grade-level adjustment
- Alternative curriculum
- Pass/fail grading
- Shortened assignments (fewer problems)
- Alternative assessments (portfolio, oral)

**Sample IEP Goal (SMART):**
> By [date], [student] will [specific skill] with [accuracy]% across [trials] consecutive trials as measured by [assessment].

**Progress Monitoring:**
- Curriculum-Based Measures (CBM) weekly/biweekly
- DIBELS, AIMSweb, easyCBM, STAR
- Teacher-made probes
- Observation data sheets

**Transition Planning (Age 14+):**
- Post-secondary goals: Education, Employment, Independent Living
- Coordinated activities: Instruction, Community experiences, Daily living skills
- Agency linkages: Vocational Rehab, College Disability Services

*Need specific accommodations for a disability area (ADHD, Dyslexia, ASD, etc.)?*"""

    async def _scope_sequence(self, params: Dict, text: str) -> str:
        """Scope and sequence document."""
        return """**Scope & Sequence Template**

**Purpose:** Vertical alignment document showing WHAT is taught WHEN across grade levels.

**Structure:**
```
Subject: Mathematics
Grade Band: K-5

| Domain/Strand | K | 1 | 2 | 3 | 4 | 5 |
|---------------|---|---|---|---|---|---|
| Counting & Cardinality | ✓ |   |   |   |   |   |
| Operations & Algebraic Thinking | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Number & Operations in Base 10 |   | ✓ | ✓ | ✓ | ✓ | ✓ |
| Number & Operations - Fractions |   |   |   | ✓ | ✓ | ✓ |
| Measurement & Data | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Geometry | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
```

**For Each Grade/Unit:**
1. **Standard Code** (CCSS, NGSS, State)
2. **Concept/Topic Name**
3. **Time Allocation** (weeks/days)
4. **Key Vocabulary**
5. **Prerequisite Skills**
6. **Assessment Points**
7. **Resources/Materials**

**Vertical Alignment Check:**
- [ ] No gaps between grades
- [ ] No unnecessary repetition
- [ ] Prerequisites taught before needed
- [ ] Cognitive complexity increases
- [ ] Vocabulary builds systematically

**Digital Tools:**
- Atlas Curriculum Mapping
- Chalk/Planboard
- Google Sheets (free)
- Notion/Airtable
- Common Curriculum"""

    async def _create_assessment(self, params: Dict, text: str) -> str:
        """Create assessments and rubrics."""
        assessment_type = "formative" if "formative" in text else "summative" if "summative" in text else "rubric"
        
        if "rubric" in text:
            return """**4-Point Analytic Rubric Template**

| Criteria | 4 - Exceeds | 3 - Meets | 2 - Approaching | 1 - Below |
|----------|-------------|-----------|-----------------|-----------|
| **Content Knowledge** | Deep understanding, connections | Accurate understanding | Partial understanding | Minimal understanding |
| **Skill Application** | Flexible, strategic use | Proficient application | Inconsistent application | Unable to apply |
| **Communication** | Clear, precise, sophisticated | Clear and organized | Somewhat clear | Unclear, disorganized |
| **Critical Thinking** | Insightful analysis, synthesis | Logical reasoning | Basic reasoning | Limited reasoning |

**Holistic Rubric (Single Score):**
- **4:** Exemplary - exceeds all criteria
- **3:** Proficient - meets all criteria  
- **2:** Developing - meets some criteria
- **1:** Beginning - meets few/no criteria

**Checklist Rubric (Yes/Not Yet):**
- [ ] Includes all required elements
- [ ] Accurate information
- [ ] Clear organization
- [ ] Proper conventions
- [ ] Evidence of revision

**Assessment Types by Purpose:**
| Type | Purpose | Examples | Timing |
|------|---------|----------|--------|
| **Diagnostic** | Pre-assessment | Pre-test, KWL, Survey | Before unit |
| **Formative** | Monitor learning | Exit tickets, Quizzes, Observations | During instruction |
| **Summative** | Evaluate mastery | Tests, Projects, Essays | End of unit |
| **Benchmark** | Track progress | Interim assessments, MAP | Quarterly |
| **Performance** | Authentic application | Portfolios, Presentations, Labs | End of unit/year |

**Quality Assessment Checklist:**
- [ ] Aligned to standards/objectives
- [ ] Clear criteria (rubric/checklist)
- [ ] Variety of item types
- [ ] Accessible (UDL)
- [ ] Reliable & valid
- [ ] Timely feedback planned"""

        return f"""**{assessment_type.title()} Assessment Ideas**

**Quick Formative (2-5 min):**
- Exit Ticket: 3-2-1 (3 learned, 2 questions, 1 connection)
- Thumbs Up/Down/Sideways
- Whiteboard Response
- Think-Pair-Share + Share Out
- Kahoot/Quizizz/Blooket
- One-Sentence Summary
- Muddiest Point

**Summative Options:**
- Traditional Test (MC, Short Answer, Essay)
- Project-Based Assessment (PBL)
- Performance Task (Real-world scenario)
- Portfolio (Curated work samples)
- Student-Led Conference
- Socratic Seminar
- Lab Report / Investigation

**Differentiation:**
- Choice Boards (9 options, pick 3 in a line)
- Tiered Assignments (Same objective, different complexity)
- Learning Contracts
- RAFT (Role, Audience, Format, Topic)"""

    async def _education_help(self) -> str:
        return """**Education Skill Commands:**

**Curriculum & Planning:**
- "Create curriculum map for 3rd grade math year-long"
- "Scope and sequence for K-5 science"
- "Unit plan for 7th grade ELA - argumentative writing"
- "Pacing guide for Algebra 1 semester"

**Lesson Plans:**
- "Lesson plan for Kindergarten phonics - short vowels"
- "5th grade science lesson - water cycle, 60 min"
- "High school history lesson - primary sources, WWII"

**Early Childhood:**
- "Kindergarten daily schedule"
- "Pre-K learning centers setup"
- "Developmental milestones for 4-year-olds"

**Assessment:**
- "Create rubric for 4th grade narrative writing"
- "Formative assessment ideas for middle school"
- "IEP goal for reading fluency 2nd grade"

**Special Education:**
- "504 accommodations for ADHD"
- "IEP modifications for dyslexia"
- "Progress monitoring tools for math"

**Homeschool:**
- "Homeschool curriculum for 1st grade eclectic"
- "High school transcript template"
- "State homeschool requirements for [state]"

**Standards Alignment:**
- "Common Core math standards for grade 4"
- "NGSS standards for middle school life science"
- "State standards crosswalk"

*Provide grade, subject, topic, and any specific requirements!*"""

    def _extract_grade(self, text: str) -> str:
        for grade in ["prek", "pre-k", "k", "kindergarten", "1", "2", "3", "4", "5", 
                      "6", "7", "8", "9", "10", "11", "12", "first", "second", "third",
                      "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth",
                      "eleventh", "twelfth"]:
            if grade in text:
                return grade.replace("first", "1").replace("second", "2").replace("third", "3") \
                           .replace("fourth", "4").replace("fifth", "5").replace("sixth", "6") \
                           .replace("seventh", "7").replace("eighth", "8").replace("ninth", "9") \
                           .replace("tenth", "10").replace("eleventh", "11").replace("twelfth", "12") \
                           .replace("pre-k", "prek").replace("kindergarten", "k")
        return "k"

    def _extract_subject(self, text: str) -> str:
        for subj in ["ela", "math", "science", "social", "art", "music", "pe", "health", 
                     "tech", "computer", "sel", "language", "reading", "writing", "history",
                     "geography", "civics", "economics", "biology", "chemistry", "physics",
                     "algebra", "geometry", "calculus", "statistics"]:
            if subj in text:
                return subj
        return "general"

    def _extract_topic(self, text: str) -> str:
        # Extract topic after common triggers
        for trigger in ["lesson on", "lesson about", "teach", "topic"]:
            if trigger in text:
                return text.split(trigger)[1].split(".")[0].strip()
        return "Topic"

    def _get_weeks(self, duration: str) -> int:
        return {"year": 36, "semester": 18, "quarter": 9, "unit": 4}.get(duration, 36)

    def _get_standards(self, subject: str, grade: str, unit: int) -> str:
        # Simplified - would map to actual standards
        return f"[{subject.upper()}.{grade.upper()}.Unit{unit}]"