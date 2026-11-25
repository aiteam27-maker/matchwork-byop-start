"""Demo seed data for Gigwise, matching the frontend's built-in demo.

Dates are relative to "now", so the demo always looks fresh.
build_rows() returns {table_name: [rows]} in insert order.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.matching import category_of

HERE = Path(__file__).parent
DEMO_CLIENT_ID = "c_pulse"


def build_rows(now: datetime | None = None) -> Dict[str, List[Dict[str, Any]]]:
    now = now or datetime.now(timezone.utc)

    def ago(days: float = 0, hours: float = 0) -> str:
        return (now - timedelta(days=days, hours=hours)).isoformat()

    def day_in(days: int) -> str:
        return (date.today() + timedelta(days=days)).isoformat()

    freelancers = json.loads((HERE / "freelancers.json").read_text())

    clients = [
        {"id": DEMO_CLIENT_ID, "name": "Pulse Fit", "rating": 4.9, "hires": 5, "is_demo_user": True},
        {"id": "c_leaf", "name": "Leaf & Co.", "rating": 4.8, "hires": 12},
        {"id": "c_helphub", "name": "HelpHub", "rating": 4.9, "hires": 5},
        {"id": "c_crumb", "name": "Crumb Bakery", "rating": 5.0, "hires": 2},
        {"id": "c_fitmetrics", "name": "FitMetrics", "rating": 4.7, "hires": 8},
        {"id": "c_lotus", "name": "Lotus Yoga", "rating": 4.9, "hires": 3},
        {"id": "c_prepbox", "name": "PrepBox", "rating": 4.6, "hires": 20},
    ]

    def proj(pid, client, title, desc, skills, *, type="fixed", budget=None, rate_min=None, rate_max=None,
             hours, level, duration, deadline, status="open", hired=None, created, questions=(), extra=0):
        if type == "hourly":
            budget = rate_max * hours
        return {
            "id": pid, "client_id": client, "title": title, "description": desc, "skills": list(skills),
            "skills_auto": False, "type": type, "budget": budget, "rate_min": rate_min, "rate_max": rate_max,
            "hours": hours, "level": level, "duration": duration, "deadline": deadline,
            "questions": list(questions), "category": category_of(list(skills)), "status": status,
            "hired_freelancer_id": hired, "extra_proposals": extra, "created_at": created,
        }

    projects = [
        proj("p0", DEMO_CLIENT_ID, "Logo refresh for Pulse Fit", "Refresh our logo and colours ahead of the app launch.",
             ["Branding", "Logo Design", "Figma"], budget=800, hours=20, level="Intermediate",
             duration="Less than 1 month", deadline=day_in(-20), status="ended", hired="f13", created=ago(60)),
        proj("p8", DEMO_CLIENT_ID, "Workout guide content for our app",
             "Eight beginner workout guides written for our app and blog. SEO-friendly, with a keyword plan.",
             ["Copywriting", "Content Strategy", "SEO"], budget=1500, hours=40, level="Intermediate",
             duration="Less than 1 month", deadline=day_in(14), status="hired", hired="f10", created=ago(12)),
        proj("p1", DEMO_CLIENT_ID, "Marketing site for our coaching startup",
             "We need a fast marketing website with a landing page, pricing page and blog. Modern design and good SEO copy.",
             ["React", "UI Design", "SEO", "Copywriting"], budget=3000, hours=60, level="Intermediate",
             duration="1 to 3 months", deadline=day_in(30), created=ago(3),
             questions=["Share a link to a marketing site you have built."]),
        proj("p2", "c_leaf", "Shopify store for organic tea brand",
             "Build a Shopify store with custom product pages, checkout and on-page SEO.",
             ["Shopify", "SEO", "UI Design"], budget=2500, hours=60, level="Intermediate",
             duration="Less than 1 month", deadline=day_in(28), created=ago(2), extra=6,
             questions=["Share a Shopify store you have built."]),
        proj("p3", "c_helphub", "RAG chatbot for help center",
             "AI chatbot that answers customer questions from our help articles. Python and an LLM, with a small evaluation set.",
             ["Python", "LLM", "NLP", "LangChain"], type="hourly", rate_min=50, rate_max=75, hours=70, level="Expert",
             duration="1 to 3 months", deadline=day_in(35), created=ago(hours=5), extra=3,
             questions=["Describe an AI or RAG project you have shipped.", "How would you measure answer quality?"]),
        proj("p4", "c_crumb", "Brand kit for a neighbourhood bakery",
             "New logo and brand kit, plus menu and Instagram templates.",
             ["Branding", "Logo Design", "Figma"], budget=1200, hours=30, level="Entry",
             duration="Less than 1 month", deadline=day_in(21), created=ago(1), extra=9),
        proj("p5", "c_fitmetrics", "Workout analytics dashboard",
             "Web dashboard showing member workout stats for gym owners. React front end, Node API and PostgreSQL.",
             ["React", "Node.js", "PostgreSQL"], type="hourly", rate_min=35, rate_max=50, hours=80,
             level="Intermediate", duration="1 to 3 months", deadline=day_in(40), created=ago(hours=9), extra=4),
        proj("p6", "c_lotus", "Flutter app for yoga studio bookings",
             "Mobile app where members book classes, pay for passes and get reminders. Clean, calm UI.",
             ["Flutter", "Firebase", "UI Design", "Stripe"], budget=5000, hours=110, level="Intermediate",
             duration="1 to 3 months", deadline=day_in(50), created=ago(hours=2), extra=2,
             questions=["Which apps have you published to the App Store or Play Store?"]),
        proj("p7", "c_prepbox", "SEO blog posts for meal-prep startup",
             "8 blog posts a month on healthy cooking, written for SEO, plus a keyword plan.",
             ["Copywriting", "SEO", "Blogging"], type="hourly", rate_min=25, rate_max=40, hours=30, level="Entry",
             duration="3 to 6 months", deadline=day_in(30), created=ago(4), extra=12),
    ]

    proposals = [
        {"id": "q0", "project_id": "p0", "freelancer_id": "f13", "status": "accepted", "bid": 800, "days": 14,
         "cover_letter": "Happy to refresh your logo. I will send three concepts in week one.", "created_at": ago(58)},
        {"id": "q3", "project_id": "p8", "freelancer_id": "f10", "status": "accepted", "bid": 1500, "days": 18,
         "cover_letter": "I write workout and nutrition content for fitness brands. I can deliver all eight guides with a keyword plan.",
         "links": ["hannahwrites.example.com/fitness"], "created_at": ago(11)},
        {"id": "q1", "project_id": "p1", "freelancer_id": "f02", "status": "submitted", "bid": 3200, "days": 21,
         "cover_letter": "Hi! I build fast React marketing sites. I can deliver the landing, pricing and blog pages with a CMS so your team can post easily.",
         "answers": ["danielk.example.com/clinic is a React marketing site with a blog and online booking."],
         "links": ["danielk.example.com"], "created_at": ago(2)},
        {"id": "q2", "project_id": "p1", "freelancer_id": "f10", "status": "shortlisted", "bid": 1800, "days": 14,
         "cover_letter": "Hello! I write SEO copy for fitness brands and can pair with your developer on landing and blog content.",
         "answers": ["I focus on copy rather than code. My fitness blog program tripled organic traffic in six months."],
         "created_at": ago(1)},
    ]
    for q in proposals:
        q.setdefault("answers", [])
        q.setdefault("links", [])

    contracts = [
        {"id": "c0", "project_id": "p0", "freelancer_id": "f13", "type": "fixed", "status": "ended",
         "started_at": ago(55), "ended_at": ago(24)},
        {"id": "c1", "project_id": "p8", "freelancer_id": "f10", "type": "fixed", "status": "active",
         "started_at": ago(10)},
    ]
    milestones = [
        {"contract_id": "c0", "position": 1, "title": "Logo concepts", "amount": 300, "due_date": day_in(-40), "status": "approved"},
        {"contract_id": "c0", "position": 2, "title": "Final logo and colour palette", "amount": 500, "due_date": day_in(-25), "status": "approved"},
        {"contract_id": "c1", "position": 1, "title": "Outline and keyword plan", "amount": 300, "due_date": day_in(-5), "status": "approved"},
        {"contract_id": "c1", "position": 2, "title": "First 4 workout guides", "amount": 600, "due_date": day_in(3), "status": "submitted",
         "note": "All four guides are in the shared doc and ready for your review.", "link": "docs.example.com/workout-guides-1"},
        {"contract_id": "c1", "position": 3, "title": "Final 4 guides and edits", "amount": 600, "due_date": day_in(14), "status": "pending"},
    ]
    reviews = [
        {"contract_id": "c0", "direction": "client_to_freelancer", "rating": 5,
         "body": "Omar turned a vague brief into a logo our whole team loves. Fast and easy to work with.", "created_at": ago(24)},
        {"contract_id": "c0", "direction": "freelancer_to_client", "rating": 5,
         "body": "Clear brief, quick feedback and a pleasure to work with.", "created_at": ago(24)},
    ]

    threads = [
        {"id": "t_p0_f13", "project_id": "p0", "freelancer_id": "f13"},
        {"id": "t_p8_f10", "project_id": "p8", "freelancer_id": "f10"},
        {"id": "t_p1_f02", "project_id": "p1", "freelancer_id": "f02"},
        {"id": "t_p1_f10", "project_id": "p1", "freelancer_id": "f10"},
    ]
    for t in threads:
        t["client_read_at"] = t["freelancer_read_at"] = now.isoformat()
    messages = [
        {"thread_id": "t_p0_f13", "sender": "system", "body": "Contract ended. Both sides left feedback.", "created_at": ago(24)},
        {"thread_id": "t_p8_f10", "sender": "system", "body": "Pulse Fit hired Hannah W. Contract started.", "created_at": ago(10)},
        {"thread_id": "t_p8_f10", "sender": "client", "body": "Welcome aboard, Hannah! Looking forward to the outline.", "created_at": ago(10, -1)},
        {"thread_id": "t_p8_f10", "sender": "freelancer", "body": "Thanks! Outline and keyword plan coming this week.", "created_at": ago(10, -2)},
        {"thread_id": "t_p8_f10", "sender": "system", "body": "Hannah W. submitted “First 4 workout guides” for review", "created_at": ago(hours=3)},
        {"thread_id": "t_p1_f02", "sender": "system", "body": "Daniel K. submitted a proposal: $3,200 · 21 days", "created_at": ago(2)},
        {"thread_id": "t_p1_f10", "sender": "system", "body": "Hannah W. submitted a proposal: $1,800 · 14 days", "created_at": ago(1)},
    ]
    notifications = [
        {"recipient_type": "client", "recipient_id": DEMO_CLIENT_ID,
         "body": "Hannah W. submitted “First 4 workout guides” for your review", "link": "#/contract/c1",
         "created_at": ago(hours=3)},
    ]

    return {
        "clients": clients,
        "freelancers": freelancers,
        "projects": projects,
        "proposals": proposals,
        "contracts": contracts,
        "milestones": milestones,
        "reviews": reviews,
        "threads": threads,
        "messages": messages,
        "notifications": notifications,
    }
