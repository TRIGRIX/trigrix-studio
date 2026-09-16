from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from trigrix_studio.nodes import NODE_REGISTRY
from trigrix_studio.i18n import template_text
from trigrix_studio.project.io import ProjectIO
from trigrix_studio.project.models import (
    BotCommand, BotProject, BotSettings, CRMIntegration, DictionaryDefinition, DictionaryRecord,
    Edge, EnvironmentBinding, ExportSettings, FlowDefinition, Node, Position,
    ProjectMetadata, RecipientDefinition, VariableDefinition,
)


@dataclass(frozen=True, slots=True)
class TemplateBlueprint:
    category: str
    title: str
    description: str
    services: tuple[str, ...]
    details_prompt: str = "Briefly describe the task, timing and expected result."


def _b(category: str, title: str, description: str, services: str, prompt: str = "Briefly describe the task, timing and expected result.") -> TemplateBlueprint:
    return TemplateBlueprint(category, title, description, tuple(part.strip() for part in services.split("|")), prompt)


# Catalog is based on recurring business scenarios: lead qualifications
# booking, support, registration, ordering and routing of appeal.
INDUSTRY_TEMPLATES: dict[str, TemplateBlueprint] = {
    # Creative and digital studios
    "web-studio": _b('Creativity and digital', "Web studio - application for the project", "Selection of web services and collection of brief", "landing|Corporate website|Online shop|Web application|UX/UI design|Frontend development|Backend and API|Integration with CRM|CMS and content|Site Audit and Acceleration|Technical SEO|Support and development|Site availability"),
    "video-production": _b('Creativity and digital', "Video production", "Briefing for video production", "Commercial|Corporate film|Interview|Image video|Social media content|Filming of the event|Live broadcast|Installation and post-production|Color correction|Sound and voiceover", "Describe the plot, format, timekeeping, accommodation sites, terms and budget range."),
    "motion-design": _b('Creativity and digital', "Motion Design Studio", "Brief on animation and graphics", "2D animation|3D animation|Explainer video|Logo animation|Titles and screensavers|Infographic|CGI for advertising|Screen content|Social media templates", "Specify style, timekeeping, format, references and deadline."),
    "visualization-studio": _b('Creativity and digital', "Visualization Studio", "Application for 3D visualization", "Architectural exterior|Interior|Subject visualization|Commercial real estate|Flight animation|Virtual tour|Planning|Render post-processing", "Describe the object, the number of angles, the required detail and available source."),
    "branding-studio": _b('Creativity and digital', "Branding studio", "Brief on brand and identity", "Brand strategy|naming|Logo.|Corporate identity|brandbook|Packaging|Rebranding|Communication platform"),
    "graphic-design": _b('Creativity and digital', "Graphic Design Studio", "Ordering design materials", "Polygraphy|Presentation|Catalog|Outdoor advertising|Social media design|Infographic|Illustration|The layout"),
    "product-design": _b('Creativity and digital', "Product design", "Briefing on a digital product", "Study|UX audit|Prototype|UI design|Design system|Mobile application|SaaS interface|usability test"),
    "marketing-agency": _b('Creativity and digital', "Marketing agency", "Qualification of the marketing application", "Strategy|Contextual advertising|Targeted advertising|SMM|Content marketing|Analytics|Email marketing|Lidogeneration"),
    "seo-agency": _b('Creativity and digital', "SEO Agency", "Application for Search Engine Promotion", "SEO audit|Promotion of services|Shop promotion|Technical optimization|Content strategy|Local SEO|Lifting of sanctions"),
    "photo-studio": _b('Creativity and digital', "Photo studio", "Selection and booking of shooting", "Subject photography|Publicity shooting|Portrait|Content for the marketplace|Interior|Reporting|Photo processing"),
    "audio-production": _b('Creativity and digital', "Audio production", "Sound and voice ordering", "Voiceover|podcast|Sound design|A commercial jingle|Music.|Mixing and mastering|Localization"),
    "game-art-studio": _b('Creativity and digital', "Game Art Studio", "Brief on game art", "Concept art.|2D characters|3D characters|encirclement|UI games|Animation|Technical art|Trailer"),

    # Sales. service
    "lead-qualification": _b('Sales. service', "Incoming lead qualifications", "Gathering needs and contact", "Purchase|Consultation|Demonstration|Partnerships"),
    "sales-consultation": _b('Sales. service', "Sales department consultation", "Routing a request for sale", "New order|Cost calculation|Selection of a solution|Re-purchase"),
    "support-ticket": _b('Sales. service', "Support services", "Registration of appeals of support", "Mistake|Question of use|Payment|Access.|Proposal", "Describe the problem, playback steps, and attach important details."),
    "customer-feedback": _b('Sales. service', "Feedback and evaluation", "Revocation collection and routing", "Review|Complaint|Gratitude.|Proposal|Quality assessment"),
    "appointment-booking": _b('Sales. service', "Enrollment for service", "Collection of data for booking", "Primary recording|Rerecording|Reschedule|Cancellation|Clarification of free time", "Specify the desired date, time and convenient method of confirmation."),
    "callback-request": _b('Sales. service', "Ordering a call back", "Contact and convenient call time", "Consultation|Calculation.|Support|Partnerships", "Specify the question, time zone and convenient time to call."),
    "partner-program": _b('Sales. service', "Partnership programme", "Potential partner questionnaire", "Agency cooperation|Integration|Joint project|Deliveries|Referral programme"),
    "wholesale-request": _b('Sales. service', "Wholesale application", "Qualifications of wholesale buyer", "Price list|Trial batch|Regular delivery|STM|Distribution", "Specify the product category, volume, region and desired delivery date."),

    # E- Commerce and goods
    "online-store": _b("E-commerce", "Online shop", "Selection of goods and assistance with order", "Selection of goods|Order status|Delivery|Payment|Return|Guarantee"),
    "marketplace-seller": _b("E-commerce", "Marketplace salesman", "Requests from buyers and suppliers", "Question of goods|Supply|Return|Guarantee|Cooperation|Card content"),
    "fashion-store": _b("E-commerce", "Clothing store", "Selection of goods and size", "Women's clothing|Men's clothing|Children's clothing|Size selection|Presence|Return"),
    "furniture-store": _b("E-commerce", "Furniture shop", "Selection of furniture and calculation", "Soft furniture|Office furniture|Kitchen|Custom furniture|Delivery and assembly|Design project"),
    "electronics-store": _b("E-commerce", "Electronics store", "Selection of equipment and support", "Smartphones|Computers|Household appliances|Accessories|Guarantee|Trade-in"),
    "flower-shop": _b("E-commerce", "Flower shop", "Ordering bouquet and delivery", "Ready bouquet|Individual bouquet|Wedding floristics|Corporate order|Delivery|Processing"),
    "food-delivery": _b("E-commerce", "Delivery of food", "Order and delivery questions", "Place an order|Order status|Change the order|Delivery problem|Corporate nutrition"),

    # Real estate and construction
    "real-estate": _b('Real estate', "Real estate agency", "Selection of the object and qualification of the client", "Buy an apartment|Rent an apartment|Sell the facility|Commercial real estate|Country real estate|A mortgage."),
    "new-development": _b('Real estate', "New developments", "Selection of an apartment in a residential complex", "Studio|1-room|2-room|3+ rooms|Commercial premises|parking", "Specify the area, area, budget, method of payment and time of purchase."),
    "construction-company": _b('Real estate', "Construction company", "Calculation of the construction project", "Turnkey house|Reconstruction|Foundation|Engineering networks|Finishing|Technical supervision"),
    "interior-design": _b('Real estate', "Interior Design Studio", "Briefing on room design", "Apartment.|Home|Office|Restaurant|Shop|Copyright supervision", "Specify the type and area of the room, city, style, composition of the project and terms."),
    "renovation": _b('Real estate', "Repair of premises", "Calculation of repairs", "Cosmetic repair|Major repairs|New construction|Office|sunuzel|Separate work"),
    "property-management": _b('Real estate', "Management company", "Receiving applications from residents", "Accident|Plumbing|Electrician.|Cleaning|Passage|Accruals|General treatment", "Specify the address, apartment, problem and convenient access time."),

    # Auto and transport
    "car-dealer": _b('Auto and transport', "Car dealership", "Vehicle selection and recording", "New car|Used car|Trade-in|Credit|Test drive.|Service"),
    "car-service": _b('Auto and transport', "Autoservice", "Record for diagnosis and repair", "Diagnostics|That|Engine repair|Walking|Electrician.|Tire fitting|Body repairs", "Specify the brand, model, year, symptoms and desired date."),
    "car-rental": _b('Auto and transport', "Car rental", "Selection and reservation of the vehicle", "Economy|Comfort.|Business|crossover|minivan|Long-term leases", "Specify the city, dates, age of the driver and additional options."),
    "logistics": _b('Auto and transport', "The logistics company", "Calculation of carriage", "Carriage by road|Air delivery|Shipping|Collection cargo|Courier delivery|Customs", "Specify the route, weight, dimensions, type of cargo and desired terms."),
    "moving-service": _b('Auto and transport', "Relocation service", "Relocation calculation", "Apartment move|Office move|Trucks.|Packaging|Storage|Transportation of furniture"),

    # Education and activities
    "online-school": _b('Education', "Online school", "Selection of the curriculum", "Profession|Short course|Advanced training|Corporate training|Free lesson", "Specify the purpose of training, current level and convenient schedule."),
    "language-school": _b('Education', "Language school", "Purpose definition and recording", "English|Chinese|German|French|Russian as a foreigner|Corporate activities", "Specify language, level, purpose, format and schedule."),
    "training-center": _b('Education', "Training centre", "Enrollment in the programme", "Full-time education|Online learning|Certification|Retraining|Advanced training"),
    "tutor": _b('Education', "Tutor", "Student questionnaire", "School programme|Examinations|Olympics|University|Conversational practice", "Specify the subject, class or level, purpose and convenient schedule."),
    "event-agency": _b('Activities', "Event agency", "Briefing for the event", "Corporate|Conference|Presentation|Private event|Online event|Technical production", "Specify the format, city, date, number of guests and budget range."),
    "conference-registration": _b('Activities', "Registration for the conference", "Registration of participant and matters", "Member|Speaker.|Partner|Press|Volunteer|Group registration"),
    "wedding-agency": _b('Activities', "Wedding agency", "Primary wedding brief", "Turnkey organization|Coordination|décor|Playground|Photos and videos|Exit registration", "Specify the city, date, number of guests, style and budget range."),

    # Hospitality and travel
    "hotel": _b('Travel and HoReCa', "Hotel", "Reservation and guest service", "Book a room.|Group accommodation|Conference room|Transfer|Change reservations|Guest service"),
    "travel-agency": _b('Travel and HoReCa', "Travel agency", "Travel selection", "Beach holiday|excursion|cruise|ski tour|Business trip|Visa and insurance", "Indicate countries, dates, number of tourists, city of departure and budget."),
    "restaurant": _b('Travel and HoReCa', "Restaurant", "Reservations and guest addresses", "Book the table|banquet|Delivery|Menu and allergens|Vacancy|Review", "Specify the date, time, number of guests and wishes."),
    "catering": _b('Travel and HoReCa', "catering", "Calculation of field services", "furchette|banquet|Coffee break|Corporate nutrition|bar|Rental of equipment", "Specify the date, venue, number of guests, format and budget."),

    # Health and beauty – only administrative scenarios, without medical advice
    "clinic-booking": _b('Health and beauty', "Clinic - recording", "Administrative records without medical advice", "Primary reception|Repeat.|Diagnostics|Tests.|Documents|Postponement of the record", "Specify the specialist or service and the desired time. Do not send medical secrets to an open chat."),
    "dental-clinic": _b('Health and beauty', "Dentistry - a record", "Recording and organizational matters", "Consultation|Hygiene|Treatment|orthodontics|Implantation|Children's reception"),
    "beauty-salon": _b('Health and beauty', "Beauty salon", "Master selection and recording", "Haircut.|Staining|Manicure|Eyebrows and eyelashes|makeup|Gone."),
    "fitness-club": _b('Health and beauty', "Fitness club", "Subscription and recording", "Subscription|Group sessions|Personal trainer|Children's programmes|Trial training|Freeze."),
    "wellness-spa": _b('Health and beauty', "SPA and wellness", "Reservation of procedure", "SPA program|Massage|Gone.|Couple|Certificate|Programme for two"),

    # B2B, IT and production
    "it-integrator": _b('B2B and IT', "IT integrator", "Qualification of the corporate request", "Infrastructure|Cloud.|Cybersecurity|Corporate SO|Integration|Technical support"),
    "saas-demo": _b('B2B and IT', "SaaS - Demonstration Request", "Qualification and demo entry", "Demonstration|Trial access|Tariffs|Integration|Migration|Enterprise"),
    "software-outsourcing": _b('B2B and IT', "Customized software development", "Primary technical brief", "Web system|Mobile application|Backend/API|Integration|MVP|Dedicated team|Support"),
    "automation-agency": _b('B2B and IT', "Automation of business", "Process search for automation", "CRM|Documentation|RPA|AI automation|Analytics|Integrations|Chatbots"),
    "cybersecurity": _b('B2B and IT', "Cybersecurity", "Application for audit or service", "Security audit|pentest|Infrastructure protection|Monitoring|Training|Response to the incident"),
    "equipment-supplier": _b('B2B and IT', "Equipment supplier", "Selection and commercial offer", "Selection of equipment|Request for KP|Project delivery|Service|Spare parts.|leasing"),
    "manufacturing": _b('B2B and IT', "Production company", "Manufacture request", "Serial production|Contractual proceedings|Prototype|Calculation of detail|Supply of materials|Quality control", "Specify the product, material, volume, tolerances, drawings and term."),
    "printing-house": _b('B2B and IT', "Printing", "Polygraphy calculation", "Business cards.|Booklets|catalogues|Packaging|Large-format printing|Souvenir products", "Specify the format, circulation, material, finish, availability of layout and term."),

    # HR, communities and community projects
    "recruitment": _b('HR and communities', "Staff selection", "Questionnaire of employer or candidate", "Find an employee|Reply|Career counselling|Outsourcing staff|Mass selection"),
    "job-application": _b('HR and communities', "Response to the vacancy", "Candidate's primary questionnaire", "Development|Design|Marketing|Sales.|Operations|Other specialization", "Specify the experience, city, work format, expectations and reference to the resume."),
    "employee-onboarding": _b('HR and communities', "Staff member onboarding", "Organizational applications of the beginner", "Documents|Access permissions|Equipment|Meet the team|Training|Question of HR"),
    "volunteer-registration": _b('HR and communities', "Registration of volunteers", "Project participant questionnaire", "Help at the event|Remote assistance|Media|Logistics|fundraising|Professional assistance"),
    "nonprofit-help": _b('HR and communities', "NGO appeal", "Routing assistance and participation", "Need help.|Become a volunteer|Donation|Partnerships|Information request"),
    "community-moderation": _b('HR and communities', "Community support", "Entries and moderation", "Introduction|Problem with access|Complaint|Proposal|Partnerships|Event"),
    "media-editorial": _b('HR and communities', "Editorial and media", "Reception of materials and requests", "Propose a topic|Send material|Commentary for the media|Advertising|Partnerships|Correction"),
    "survey-research": _b('HR and communities', "Survey and study", "Registration of respondent", "Take a survey|Interview|Focus group|User testing|Get results"),
}


BUILTIN_TEMPLATES: dict[str, tuple[str, str]] = {
    "empty": ('Empty bot', 'Clean project with block /start'),
    "simple-menu": ("Simple menu", 'Start Message and Two-Point Menu'),
    "lead-quiz": ("Query/application", 'Name., phone and administrator notification'),
    "multichannel-lead": ("Multichannel application", 'Structured lead, Email, CRM, Firebase and administrative card'),
    **{key: (value.title, value.description) for key, value in INDUSTRY_TEMPLATES.items()},
}

TEMPLATE_CATEGORIES = {
    "empty": 'Basic', "simple-menu": 'Basic', "lead-quiz": 'Basic', "multichannel-lead": 'Basic',
    **{key: value.category for key, value in INDUSTRY_TEMPLATES.items()},
}


def _node(node_id: str, type_: str, title: str, x: float, y: float, settings: dict | None = None, group: str = "") -> Node:
    definition = NODE_REGISTRY.get(type_); defaults = definition.default_settings() if definition else {}; defaults.update(settings or {})
    return Node(id=node_id, type=type_, title=title, position=Position(x=x, y=y), settings=defaults, group=group)


def _edge(source: str, target: str, port: str = "next", label: str = "") -> Edge:
    return Edge(id=f"e_{source}_{port}_{target}", source=source, source_port=port, target=target, label=label)


def _base(name: str, description: str, template: str) -> BotProject:
    return BotProject(
        metadata=ProjectMetadata(name=name, description=description, template=template),
        bot=BotSettings(display_name="Your bot name", about="Company assistant", description=description, commands=[BotCommand(command="start", description="Main menu")]),
        environment=[
            EnvironmentBinding(name="BOT_TOKEN", description="Telegram bot token", kind="secret"),
            EnvironmentBinding(name="WEBHOOK_SECRET", description="Webhook verification secret", kind="secret", platforms=["cloudflare"]),
        ],
        export=ExportSettings(cloudflare_worker_name=template, docker_service_name=template),
    )


def _localize_project(project: BotProject, locale: str) -> BotProject:
    translate = lambda value: template_text(value, locale) if isinstance(value, str) else value
    project.metadata.name = translate(project.metadata.name)
    project.metadata.description = translate(project.metadata.description)
    project.bot.display_name = translate(project.bot.display_name)
    project.bot.about = translate(project.bot.about)
    project.bot.description = translate(project.bot.description)
    for command in project.bot.commands:
        command.description = translate(command.description)
    for binding in project.environment:
        binding.description = translate(binding.description)
    for dictionary in project.dictionaries:
        dictionary.title = translate(dictionary.title)
        for record in dictionary.records:
            record.title = translate(record.title)
    for recipient in project.recipients:
        recipient.title = translate(recipient.title)
    for flow in project.flows:
        flow.title = translate(flow.title)
    for node in project.nodes:
        node.title = translate(node.title)
        node.group = translate(node.group)
        for key in ("text", "description", "title", "template", "invalid_message"):
            if isinstance(node.settings.get(key), str):
                node.settings[key] = translate(node.settings[key])
        for button in node.settings.get("buttons", []):
            if isinstance(button, dict) and isinstance(button.get("text"), str):
                button["text"] = translate(button["text"])
    for edge in project.edges:
        edge.label = translate(edge.label)
    project.localization.default_locale = locale
    project.localization.fallback_locale = locale
    return project


def create_template(template_id: str, locale: str | None = None) -> BotProject:
    builders = {"empty": _empty, "simple-menu": _simple_menu, "lead-quiz": _lead_quiz, "multichannel-lead": _multichannel_lead}
    if template_id in builders: project = builders[template_id]()
    elif template_id in INDUSTRY_TEMPLATES: project = _industry_template(template_id, INDUSTRY_TEMPLATES[template_id])
    else: raise KeyError(f"Unknown pattern:{template_id}")
    project.metadata.project_id = uuid4().hex[:12]; project.metadata.created_at = project.metadata.modified_at
    result = deepcopy(project)
    return _localize_project(result, locale) if locale else result


def _empty() -> BotProject:
    project = _base("New project", "Empty multichannel project", "empty")
    project.nodes = [_node("start", "command_trigger", "/start", 80, 120, {"command": "start"}), _node("finish", "finish", "First response", 450, 120, {"text": "Configure the bot’s first response."})]
    project.edges = [_edge("start", "finish")]
    project.flows = [FlowDefinition(id="main", title="Main scenario", start_node_id="start")]
    return project


def _simple_menu() -> BotProject:
    project = _base("Simple menu", "Bot with a simple menu", "simple-menu")
    project.nodes = [
        _node("start", "command_trigger", "/start", 60, 160, {"command": "start"}),
        _node("menu", "menu", "Main menu", 390, 160, {"text": "Select the section:", "buttons": [{"id": "about", "text": "Company.", "type": "transition", "url": ""}, {"id": "contacts", "text": "Contacts", "type": "transition", "url": ""}]}),
        _node("about", "finish", "Company.", 780, 80, {"text": "Add information about the company.", "show_main_menu": True}),
        _node("contacts", "finish", "Contacts", 780, 250, {"text": "Add communication methods.", "show_main_menu": True}),
    ]
    project.edges = [_edge("start", "menu"), _edge("menu", "about", "about"), _edge("menu", "contacts", "contacts")]
    project.flows = [FlowDefinition(id="main", title="Main menu", start_node_id="start")]
    return project


def _lead_quiz() -> BotProject:
    project = _base("Query/application", "Collection and forwarding of applications", "lead-quiz")
    project.environment.append(EnvironmentBinding(name="ADMIN_CHAT_ID", description="Chat ID administrator")); project.recipients = [RecipientDefinition(id="admin", title="Administrator", chat_id_env="ADMIN_CHAT_ID")]
    project.variables = [VariableDefinition(name="name", max_length=80), VariableDefinition(name="phone", max_length=32), VariableDefinition(name="request_id", max_length=24)]
    project.nodes = [
        _node("start", "command_trigger", "/start", 50, 140, {"command": "start"}),
        _node("ask_name", "question", "Name.", 390, 80, {"text": "What's your name?", "variable": "name", "max_length": 80}),
        _node("ask_phone", "question", "Telephone.", 730, 80, {"text": "Specify the phone:", "variable": "phone", "answer_type": "phone", "max_length": 32}),
        _node("request_id", "request_id", "Application number", 1070, 80, {"prefix": "LEAD", "variable": "request_id"}),
        _node("notify", "card", "Application form", 1410, 80, {"recipient": "admin", "title": "New application", "text": "ID: {{ request_id }}\nName: {{ name }}\nPhone: {{ phone }}\nTelegram: @{{ user.username }}"}),
        _node("finish", "finish", "Thank you.", 1750, 80, {"text": "Thank you! Application No.  {{ request_id }}   has been sent."}),
    ]
    project.edges = [_edge("start", "ask_name"), _edge("ask_name", "ask_phone"), _edge("ask_phone", "request_id"), _edge("request_id", "notify"), _edge("notify", "finish")]
    project.flows = [FlowDefinition(id="lead", title="Collection of applications", start_node_id="start")]
    return project


def _multichannel_lead() -> BotProject:
    project = _base("Multichannel application", "Neutral international scenario of collection and delivery of leads", "multichannel-lead")
    project.environment.append(EnvironmentBinding(name="ADMIN_CHAT_ID", description="Telegram Chat ID administrator"))
    project.recipients = [RecipientDefinition(id="admin", title="Administrator", chat_id_env="ADMIN_CHAT_ID")]
    project.crm_integrations = [CRMIntegration(id="crm_main", provider="hubspot", title="HubSpot", enabled=False, auth_env="HUBSPOT_TOKEN")]
    project.variables = [
        VariableDefinition(name="lead_name", max_length=100), VariableDefinition(name="lead_phone", max_length=40),
        VariableDefinition(name="lead_email", max_length=160), VariableDefinition(name="lead_country", max_length=80),
        VariableDefinition(name="answer_details", max_length=1000), VariableDefinition(name="request_id", max_length=32),
        VariableDefinition(name="lead", type="object"),
    ]
    project.nodes = [
        _node("start", "command_trigger", "/start", 40, 140, {"command": "start"}, "Start"),
        _node("name", "collect_lead_field", "Name", 360, 80, {"text": "What is your name?", "field": "name", "variable": "lead_name", "max_length": 100}, "Lead"),
        _node("phone", "collect_lead_field", "Phone", 700, 80, {"text": "Enter your phone number.", "field": "phone", "answer_type": "phone", "variable": "lead_phone", "max_length": 40}, "Lead"),
        _node("email", "collect_lead_field", "Email", 1040, 80, {"text": "Enter your email address.", "field": "email", "answer_type": "email", "variable": "lead_email", "max_length": 160}, "Lead"),
        _node("country", "collect_lead_field", "Country", 1380, 80, {"text": "Country or region", "field": "country", "variable": "lead_country", "max_length": 80}, "Lead"),
        _node("details", "collect_lead_field", "Request", 1720, 80, {"text": "Describe your request.", "field": "free_answer", "variable": "answer_details", "max_length": 1000}, "Lead"),
        _node("request_id", "request_id", "Lead ID", 2060, 80, {"prefix": "LEAD", "variable": "request_id"}, "Delivery"),
        _node("complete", "complete_lead", "Complete lead", 2400, 80, {}, "Delivery"),
        _node("firebase", "save_lead", "Save to Firebase", 2740, 80, {"continue_on_error": True}, "Delivery"),
        _node("email_notify", "notify_email", "Notify Email", 3080, 80, {"continue_on_error": True}, "Delivery"),
        _node("crm", "push_crm", "Push to CRM", 3420, 80, {"crm_id": "crm_main", "continue_on_error": True}, "Delivery"),
        _node("admin", "send_admin_summary", "Admin summary", 3760, 80, {"recipient": "admin", "template": "ID: {{ lead.lead_id }}\nName: {{ lead.name }}\nPhone: {{ lead.phone }}\nEmail: {{ lead.email }}\nCountry: {{ lead.country }}"}, "Delivery"),
        _node("export", "export_leads", "Admin export", 4100, 80, {"recipient": "admin", "format": "xlsx"}, "Delivery"),
        _node("finish", "finish", "Completed", 4440, 80, {"text": "Thank you. Your request {{ request_id }} has been received."}, "Finish"),
    ]
    project.edges = [_edge(a, b) for a, b in zip(("start", "name", "phone", "email", "country", "details", "request_id", "complete", "firebase", "email_notify", "crm", "admin", "export"), ("name", "phone", "email", "country", "details", "request_id", "complete", "firebase", "email_notify", "crm", "admin", "export", "finish"), strict=True)]
    project.flows = [FlowDefinition(id="lead", title="Multichannel lead", start_node_id="start")]
    return project


def _industry_template(template_id: str, blueprint: TemplateBlueprint) -> BotProject:
    project = _base(blueprint.title, blueprint.description, template_id)
    project.environment.append(EnvironmentBinding(name="ADMIN_CHAT_ID", description="Chat ID for new applications"))
    project.recipients = [RecipientDefinition(id="requests", title="New appeals", chat_id_env="ADMIN_CHAT_ID")]
    project.variables = [
        VariableDefinition(name="service", type="dictionary_reference"), VariableDefinition(name="client_name", max_length=100),
        VariableDefinition(name="client_contact", max_length=120), VariableDefinition(name="details", max_length=1000), VariableDefinition(name="request_id", max_length=24),
    ]
    project.dictionaries = [DictionaryDefinition(name="SERVICES", title="Services and destinations", records=[DictionaryRecord(id=f"{index:02}", title=title) for index, title in enumerate(blueprint.services, 1)])]
    project.nodes = [
        _node("start", "command_trigger", "/start", 40, 180, {"command": "start", "description": "Main menu"}, "Start"),
        _node("main", "menu", "Main menu", 390, 160, {"text": "Hello there! How can we help?", "buttons": [
            {"id": "request", "text": "Leave the application", "type": "transition", "url": ""}, {"id": "services", "text": "Choosing a favor", "type": "transition", "url": ""}, {"id": "faq", "text": "How the work goes", "type": "transition", "url": ""},
        ]}, "Main menu"),
        _node("services", "dictionary_select", "Offering", 780, 80, {"text": "Choose a service or direction:", "dictionary": "SERVICES", "variable": "service", "columns": 1}, "Application"),
        _node("ask_name", "question", "Name.", 1170, 80, {"text": "How do I address you?", "variable": "client_name", "max_length": 100}, "Application"),
        _node("ask_contact", "question", "Contact", 1510, 80, {"text": "Specify the phone, email or convenient method of communication.", "variable": "client_contact", "max_length": 120}, "Application"),
        _node("ask_details", "question", "Description of the task", 1850, 80, {"text": blueprint.details_prompt, "variable": "details", "max_length": 1000}, "Application"),
        _node("request_id", "request_id", "Number of treatment", 2190, 80, {"prefix": "REQ", "random_length": 6, "variable": "request_id"}, "Application"),
        _node("notify", "card", "Request summary", 2530, 80, {"recipient": "requests", "title": "NEW REQUEST", "text": 'ID: {{ request_id }}\nService: {{ service.title }}\nName: {{ client_name }}\nContact: {{ client_contact }}\nRequest: {{ details }}\nTelegram: @{{ user.username }}\nTelegram ID: {{ user.id }}'}, "Application"),
        _node("finish", "finish", "Application accepted", 2870, 80, {"text": "Thank you! Address   {{ request_id }}  has been forwarded to the team.", "show_main_menu": True}, "Application"),
        _node("faq", "finish", "How the work goes", 780, 560, {"text": "We will clarify the task, offer the appropriate format, agree on the cost and timing, then contact you.", "show_main_menu": True}, "Information"),
    ]
    project.edges = [
        _edge("start", "main"), _edge("main", "services", "request", "Application"), _edge("main", "services", "services", "Services"), _edge("main", "faq", "faq", "Information"),
        _edge("services", "ask_name"), _edge("ask_name", "ask_contact"), _edge("ask_contact", "ask_details"), _edge("ask_details", "request_id"), _edge("request_id", "notify"), _edge("notify", "finish"),
    ]
    project.flows = [FlowDefinition(id="main", title="Reception of appeal", start_node_id="start")]
    return project


def ensure_template_files(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for template_id in BUILTIN_TEMPLATES:
        project = create_template(template_id)
        current = root / f"{template_id}.trigrixproj"
        legacy = root / f"{template_id}.tgbotproj"
        if not current.exists():
            ProjectIO.save(project, current)
        if not legacy.exists():
            ProjectIO.save(project, legacy)
