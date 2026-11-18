# Clockwise: M4 User Testing Sessions

Five external testers (FGCU students, none on Team 10 or in our CEN 4930 section) used the deployed Clockwise app connected to **their own live Canvas accounts**. Sessions were recorded with an AI notetaker; quotes below come from those transcripts. Each tester gave one **overall rating (1–5)** at the end.

**Deviation from the M3 plan:** we planned scripted tasks (a) baseline, (b) explain a moved deadline, (c) "what's due next week?", (d) switch to urgent-only by chat, plus three separate ratings (Q1 understanding, Q2 trust, Q3 likelihood to keep using). In practice the sessions were open-ended: testers set up Clockwise with their real Canvas account and asked their own questions. Tasks (b) and (d) were not attempted, and one overall rating was collected instead of Q1–Q3. We report this as a limitation in the synthesis.

| # | Tester | Setup done | Own query answered | Wrong due date/time seen | Overall rating |
|---|---|---|---|---|---|
| 1 | Sophomore, Entrepreneurship | Yes | Yes (correct) | No | 4 |
| 2 | Senior, Entrepreneurship | Yes | Yes | Yes | 4 |
| 3 | Senior, Software Engineering | Yes | Yes | Yes | 4 |
| 4 | Senior, Software Engineering | Yes | Partly (one question refused) | No | 4 |
| 5 | Sophomore, Entrepreneurship | Yes (≈4 min) | Yes, but slow (≈2 min) | Yes | 3 |
| | | **5/5** | | **3/5** | **mean 3.8; 4/5 rated ≥4** |

---

## Session 1

- **Tester:** Sophomore, Entrepreneurship major. Runs his own business and already uses AI agents (Claude with a browser agent) day to day.
- **Date and format:** [TODO: date] · live, facilitator present · ≈3 min
- **Task given:** Connect Clockwise to your Canvas, ask it anything about your assignments, then react to the push-notification feature and say what you like, dislike and would improve.
- **What they did:**
  1. Completed setup (Canvas access token + PIN). Described it as "pretty easy… As long as you have all the steps, it should be pretty, pretty seamless."
  2. Asked Clockwise for his next assignment.
  3. Got an answer (a final report); the facilitator confirmed it was correct.
  4. Gave feedback on push notifications, the UI and features.
- **Where they got stuck:** No observed stuck point. The friction he named was the Canvas connection step itself: "if you make it, like, really, really, like, easy, like, friction-free to, like, just connect to your Canvas."
- **What surprised us:** Unprompted, he raised institutional adoption: "You could probably get the school to, like, start making it a thing." He also expects an agent that acts, not only informs: "I think an agent should be able to do anything for you now, as long as it's, like, on a computer."
- **Would they use it again?** Yes. On push notifications: "Yeah, for sure." More likely with a better UI ("maybe, like, improve the UI"), a frictionless Canvas connection, and a calendar view so it works "like your personal school advisor, almost."
- **Rating:** 4/5

## Session 2

- **Tester:** Senior, Entrepreneurship major, balancing coursework with a startup validation project.
- **Date and format:** [TODO: date] · live, facilitator present · ≈3.5 min
- **Task given:** Connect Clockwise, ask it anything about your assignments, then say what you like, dislike and would improve.
- **What they did:**
  1. Completed setup: "Pretty seamless process. Took a little long, but, like, I mean, that's no big deal."
  2. Read the assignment list: "it shows, like, you know, my assignments that are due at certain times, which is very cool to see."
  3. Asked how to manage his time between homework and his validation project.
  4. Clockwise answered with a plan ordered by due date ("Start with practice final project due November 21st… then tackle the term sheet evaluation quiz due November 24th") plus suggested time blocks.
- **Where they got stuck:** No navigation problem. He noticed wrong due times: "The only thing that's a little bit inaccurate is just, like, the times of when it's due."
- **What surprised us:** He used Clockwise as a planner, not a deadline lookup, and the agent answered a time-management question even though its guardrail scopes it to Canvas deadlines.
- **Would they use it again?** "Yeah." More likely with better responses ("some of the ways it responds") and a time-blocking feature: "time block your whole schedule."
- **Rating:** 4/5

## Session 3

- **Tester:** Senior, Software Engineering major.
- **Date and format:** [TODO: date] · live, facilitator present
- **Task given:** Connect Clockwise, ask it about your week, then give feedback.
- **What they did:**
  1. Completed setup: "I thought it was very easy, because all you need is, like, just the access key, and that's basically it. You just make a PIN."
  2. Asked: "What do I have to do this week?"
  3. Questioned whether an assignment was due Wednesday or Thursday; the facilitator confirmed Clockwise showed the wrong day (it was due Wednesday).
  4. Asked Clockwise to rank his week's assignments by importance; it returned project M4, then the presentation, then the final-review submission. He reacted positively.
- **Where they got stuck:** The wrong due day. He guessed the agent was reading Canvas's "available until" date instead of the due date. (Root cause was actually the timezone bug; see synthesis.) He also found the chat box too low on the screen and suggested making it bigger or raising it, "just a minor change."
- **What surprised us:** He wanted prioritization more than reminders, and the agent handled ranking well.
- **Would they use it again?** Yes; said push notifications would be useful. Recommendation: fact-check due times and dates. Liked the simplicity; dislikes interfaces with "so much stuff."
- **Rating:** 4/5

## Session 4

- **Tester:** Senior, Software Engineering major; has written code and looked at the project's GitHub repo.
- **Date and format:** [TODO: date] · live, facilitator present
- **Task given:** Connect Clockwise, ask it questions, think aloud, then give feedback.
- **What they did:**
  1. Completed setup. First reaction to the UI: "super simple" and "ChatGPT-esque."
  2. Asked how long his assignments this week might take. Clockwise refused with its guardrail message (it can only help with Canvas assignments).
  3. Explained he wanted that answer to decide the order to do his work, weighing time needed and points within each class.
  4. Discussed scheduling, calendars and notifications.
- **Where they got stuck:** (1) The refusal of a legitimate coursework-planning question. (2) While waiting for an answer the screen dimmed and he thought the app had broken; he suggested movement or flashing instead of dimming.
- **What surprised us:** Open source increased trust: seeing the code made it feel "more trustworthy and secure" because "there's nothing hidden anywhere." He would ignore Clockwise alerts that just repeat Canvas notifications.
- **Would they use it again?** Yes, conditionally. In closing he said he thought it worked and that he liked it a lot. More likely if he could schedule assignment work into Outlook or another calendar, use it on his phone in natural language, and get notifications that are customizable and different from Canvas's own.
- **Rating:** 4/5

## Session 5

- **Tester:** Sophomore, Entrepreneurship major; says he is already on top of his assignments.
- **Date and format:** [TODO: date] · live, facilitator present
- **Task given:** Connect Clockwise, ask it questions, then give feedback.
- **What they did:**
  1. Completed setup; found the interface "very straightforward."
  2. Asked: "What is my next to-do assignment?"
  3. Clockwise said it was due at 7:45 that night; he corrected it: "It's actually due at 2:45."
  4. Waited through slow responses: about four minutes to connect Canvas and about two minutes to answer; after a refresh it was still loading 1.5 minutes later.
- **Where they got stuck:** Response speed and the wrong due time.
- **What surprised us:** He would not use it, despite liking the design: "Probably not, to be honest." He already gets Canvas notifications and sees the value mainly for students in harder or more demanding classes.
- **Would they use it again?** No. He disliked "how long it took to do a task and that it gave him wrong information"; speed was the one improvement he asked for.
- **Rating:** 3/5
