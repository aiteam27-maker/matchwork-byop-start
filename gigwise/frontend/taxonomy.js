/* Gigwise skill catalog: categories > specialties > skills (like Upwork's job-post flow).
   One source of truth: the frontend loads this file directly, and the backend reads the same file
   (gigwise/backend/app/matching.py). Keep it valid JSON after the "=" sign.
   - aliases: other spellings that map to a catalog skill (e.g. "ReactJS" -> "React")
   - noDetect: skills too generic to auto-detect from free text (e.g. "Go", "Excel") */
window.GW_TAXONOMY = {
 "version": 1,
 "categories": [
  {"name": "Web Development", "specialties": [
   {"name": "Front-end development", "skills": ["JavaScript", "TypeScript", "React", "Next.js", "Vue.js", "Angular", "Svelte", "HTML", "CSS", "Tailwind CSS", "Responsive Design", "Web Performance"]},
   {"name": "Back-end development", "skills": ["Node.js", "Express.js", "Python", "Django", "Flask", "FastAPI", "PHP", "Laravel", "Ruby on Rails", "Java", "Spring Boot", "Go", "C#", ".NET", "REST API", "GraphQL", "WebSockets"]},
   {"name": "Databases", "skills": ["PostgreSQL", "MySQL", "MongoDB", "Redis", "Supabase", "Firebase", "SQLite", "Prisma", "Database Design"]},
   {"name": "CMS & no-code", "skills": ["WordPress", "Webflow", "Wix", "Squarespace", "Bubble", "Framer", "Elementor", "Landing Pages"]}
  ]},
  {"name": "Mobile Development", "specialties": [
   {"name": "Cross-platform apps", "skills": ["Flutter", "Dart", "React Native", "Expo", "Ionic"]},
   {"name": "iOS development", "skills": ["Swift", "SwiftUI", "iOS", "Objective-C", "HealthKit", "App Store Optimization"]},
   {"name": "Android development", "skills": ["Kotlin", "Android", "Jetpack Compose", "Java"]},
   {"name": "App features", "skills": ["Push Notifications", "In-App Purchases", "Mobile UI Design", "Maps Integration", "Offline Sync", "Firebase"]}
  ]},
  {"name": "AI & Machine Learning", "specialties": [
   {"name": "LLM & chatbot development", "skills": ["LLM", "Prompt Engineering", "LangChain", "LlamaIndex", "RAG", "Chatbot Development", "AI Agents", "Vector Databases", "Embeddings", "Fine-tuning", "Claude API", "OpenAI API"]},
   {"name": "Machine learning", "skills": ["Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "scikit-learn", "Computer Vision", "NLP", "Recommendation Systems", "MLOps", "Python"]},
   {"name": "AI integration", "skills": ["AI Integration", "AI Automation", "Speech Recognition", "Text-to-Speech", "Image Generation"]}
  ]},
  {"name": "Data Science & Analytics", "specialties": [
   {"name": "Data analysis", "skills": ["Data Analysis", "SQL", "Excel", "Google Sheets", "Statistics", "Python", "R", "Pandas"]},
   {"name": "Data visualization", "skills": ["Data Visualization", "Tableau", "Power BI", "Looker Studio", "Dashboards"]},
   {"name": "Data engineering", "skills": ["ETL", "Data Pipelines", "Apache Spark", "Airflow", "BigQuery", "Snowflake", "dbt", "Web Scraping"]}
  ]},
  {"name": "Design & Creative", "specialties": [
   {"name": "UI/UX design", "skills": ["UI Design", "UX Research", "Figma", "Prototyping", "Wireframing", "Design Systems", "User Testing", "Adobe XD", "Sketch", "Mobile UI Design"]},
   {"name": "Brand & graphic design", "skills": ["Branding", "Logo Design", "Graphic Design", "Illustration", "Adobe Illustrator", "Adobe Photoshop", "Canva", "Typography", "Packaging Design"]},
   {"name": "Video & motion", "skills": ["Video Editing", "Motion Graphics", "Adobe Premiere Pro", "After Effects", "Animation", "3D Modeling", "Blender"]}
  ]},
  {"name": "Writing & Translation", "specialties": [
   {"name": "Content writing", "skills": ["Copywriting", "Content Writing", "Blogging", "SEO Writing", "Technical Writing", "Ghostwriting", "Proofreading", "Editing"]},
   {"name": "Content strategy", "skills": ["Content Strategy", "Scriptwriting", "Email Copywriting", "UX Writing"]},
   {"name": "Translation", "skills": ["Translation", "Localization", "Spanish", "French", "German", "Hindi", "Arabic"]}
  ]},
  {"name": "Sales & Marketing", "specialties": [
   {"name": "Digital marketing", "skills": ["SEO", "SEM", "Google Ads", "Facebook Ads", "Social Media Marketing", "Email Marketing", "Marketing Strategy", "Growth Marketing", "Influencer Marketing"]},
   {"name": "Marketing analytics", "skills": ["Google Analytics", "Conversion Rate Optimization", "A/B Testing", "HubSpot", "Mailchimp"]},
   {"name": "Sales & lead generation", "skills": ["Lead Generation", "Sales Funnels", "CRM", "Cold Outreach", "Appointment Setting"]}
  ]},
  {"name": "E-commerce", "specialties": [
   {"name": "Online stores", "skills": ["Shopify", "Liquid", "WooCommerce", "Magento", "BigCommerce", "Amazon Seller Central", "Etsy"]},
   {"name": "Payments", "skills": ["Stripe", "PayPal", "Razorpay", "Payment Integration", "Subscriptions"]},
   {"name": "Store operations", "skills": ["Product Listings", "Dropshipping", "Inventory Management"]}
  ]},
  {"name": "IT & DevOps", "specialties": [
   {"name": "Cloud & DevOps", "skills": ["AWS", "Google Cloud", "Azure", "Docker", "Kubernetes", "CI/CD", "Terraform", "Linux", "GitHub Actions", "Nginx"]},
   {"name": "Security", "skills": ["Cybersecurity", "Penetration Testing", "Network Security", "Authentication", "OAuth"]},
   {"name": "QA & testing", "skills": ["QA Testing", "Automated Testing", "Selenium", "Cypress", "Playwright", "Unit Testing"]}
  ]},
  {"name": "Admin & Support", "specialties": [
   {"name": "Virtual assistance", "skills": ["Virtual Assistance", "Data Entry", "Calendar Management", "Research"]},
   {"name": "Customer support", "skills": ["Customer Support", "Zendesk", "Live Chat Support", "Help Center Writing"]},
   {"name": "Project management", "skills": ["Project Management", "Agile", "Scrum", "Jira", "Notion"]}
  ]},
  {"name": "Finance & Accounting", "specialties": [
   {"name": "Accounting", "skills": ["Bookkeeping", "Accounting", "QuickBooks", "Xero", "Tax Preparation"]},
   {"name": "Financial analysis", "skills": ["Financial Modeling", "Financial Analysis", "Fundraising", "Pitch Decks"]}
  ]},
  {"name": "Legal", "specialties": [
   {"name": "Business law", "skills": ["Contract Drafting", "Legal Research", "Intellectual Property", "Compliance", "Privacy Policy", "GDPR"]}
  ]}
 ],
 "aliases": {
  "ReactJS": "React", "React.js": "React", "NodeJS": "Node.js", "Node": "Node.js", "NextJS": "Next.js", "Next": "Next.js",
  "VueJS": "Vue.js", "Vue": "Vue.js", "JS": "JavaScript", "TS": "TypeScript", "Postgres": "PostgreSQL", "Mongo": "MongoDB",
  "UI": "UI Design", "UI/UX": "UI Design", "UX": "UX Research", "ML": "Machine Learning", "AI chatbot": "Chatbot Development",
  "GPT": "LLM", "Large Language Models": "LLM", "Chatbot": "Chatbot Development", "Golang": "Go", "Rails": "Ruby on Rails",
  "Tailwind": "Tailwind CSS", "Photoshop": "Adobe Photoshop", "Illustrator": "Adobe Illustrator", "Premiere Pro": "Adobe Premiere Pro",
  "K8s": "Kubernetes", "GCP": "Google Cloud", "Amazon Web Services": "AWS", "Sklearn": "scikit-learn", "Content Marketing": "Content Strategy",
  "Blog Writing": "Blogging", "Logo": "Logo Design", "Brand Identity": "Branding", "Woo": "WooCommerce", "Power Bi": "Power BI"
 },
 "noDetect": ["Go", "R", "C#", "Java", "Excel", "Editing", "Animation", "Translation", "Research", "Compliance", "Authentication",
  "Subscriptions", "Dashboards", "Statistics", "Typography", "Sketch", "Expo", "Ionic", "Prisma", "Bubble", "Framer", "Wix",
  "CSS", "HTML", "Spanish", "French", "German", "Hindi", "Arabic", "Agile", "Scrum", "Notion", "Accounting", "Fundraising",
  "Android", "iOS", "Embeddings", "Etsy", "Linux", "CRM", "Landing Pages"]
};
