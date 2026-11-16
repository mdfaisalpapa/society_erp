# Society ERP — Comprehensive Application Blueprint & Roadmap

---

## 1. Executive Summary & Architecture Overview

**Society ERP** is a full-featured, multi-tier residential society and apartment management platform built natively on the **Frappe / ERPNext Framework** (tailored for large Resident Welfare Associations such as Kendriya Vihar-C3 with 1,220+ flats).

The application is structured into four primary pillars:
1. **Domain & Data Core (ERPNext/Frappe Engine)**:
   - Houses all society master records, financial ledgers, facility operations, shift musters, asset maintenance, water/tanker logs, voting/elections, and compliance documents.
   - Leverages native Frappe permissions, workflows, document hooks, and scheduled background workers.
2. **Resident Web Portal & Mobile Mini-Apps (`/resident`)**:
   - Modern, responsive, mobile-first resident self-service portal.
   - Covers account dues, online payments, maintenance tickets, domestic staff directory, visitor passes, parking management, pet registration, community classifieds, notices, and board resolutions.
3. **Facility & Vendor Agency Portal (`/agency`, `/maintenance_job`)**:
   - Dedicated portal for facility management agencies, security supervisors, and maintenance contractors.
   - Manages facility shift musters, staff deployment across duty posts, AMC logs, chemical & water tanker monitoring, and technician job cards with photo proof.
4. **Decoupled Omnichannel Conversational Gateway (`universal_chatbot` Integration)**:
   - Headless integration with Telegram and WhatsApp Cloud API via `universal_chatbot`.
   - Pure data APIs with zero channel formatting in the core app.
   - Single Sign-On (SSO) tokenized gateway for instant bottom-sheet WebApp interactions.
   - Dual-channel identity verification (Phone + Email OTP gating).

```
+──────────────────────────────────────────────────────────────────────────────────────────+
|                                    TOUCHPOINTS & CLIENTS                                 |
|   Resident Portal (/resident)    Agency Portal (/agency)   Telegram Bot    WhatsApp API  |
+──────────────────────────────────────────────────────────────────────────────────────────+
                                              │
                                              ▼
+──────────────────────────────────────────────────────────────────────────────────────────+
| FRAPPE / ERPNEXT DOMAIN LAYER (society_erp)                                              |
|                                                                                          |
| ┌──────────────────────────────────────┐     ┌─────────────────────────────────────────┐ |
| │ Identity, Security & Verification    │     │ Accounting & Cost Apportionment         │ |
| │ • Channel Identity (Telegram/WhatsApp)│     │ • Dues & Customer Ledgers               │ |
| │ • Dual Verification (Phone/Email OTP)│     │ • Cost Center & ITC Validation          │ |
| │ • Signed 15-min SSO Generator        │     │ • Maintenance Billing Runs              │ |
| └──────────────────┬───────────────────┘     └───────────────────┬─────────────────────┘ |
|                    │                                             │                       |
| ┌──────────────────┴───────────────────┐     ┌───────────────────┴─────────────────────┐ |
| │ Resident Self-Service Operations     │     │ Facility & Vendor Operations            │ |
| │ • Vehicle Registry & Parking Bidding │     │ • Security & Facility Staff Rostering   │ |
| │ • Visitors & Passcodes (Guard API)   │     │ • Shift Musters & Duty Post Deployment  │ |
| │ • Maintenance Helpdesk & Dispatch    │     │ • Water Tankers, STP & Tank Cleaning    │ |
| │ • Domestic Staff & Attendance Logs   │     │ • AMC Logging & Invoice Reconciliation  │ |
| └──────────────────┬───────────────────┘     └───────────────────┬─────────────────────┘ |
|                    │                                             │                       |
| ┌──────────────────┴───────────────────┐     ┌───────────────────┴─────────────────────┐ |
| │ Democratic Governance & Community    │     │ Communications & Alerts                 │ |
| │ • Board Resolutions & Signatories    │     │ • Web Push Notifications (VAPID/Service │ |
| │ • Electorate Registers & Objections  │     │   Worker)                               │ |
| │ • Cryptographic / Multi-Provider Polls│    │ • Official Notices & Broadcasts         │ |
| │ • Classifieds & Emergency Directory  │     │ • Automated QRT Maintenance Digest      │ |
| └──────────────────────────────────────┘     └─────────────────────────────────────────┘ |
+──────────────────────────────────────────────────────────────────────────────────────────+
```

---

## 2. Comprehensive Module & Feature Breakdown

### 2.1 Resident Management & Identity Verification
- **DocTypes**: `Owners`, `Tenants`, `Family Members`, `Channel Identity`, `Authorized Bot Device`.
- **Key Capabilities**:
  - Distinct records and rights for Flat Owners and Tenants, linked to standard Frappe `Customer` and `User` records.
  - Multi-flat ownership and tenancy management.
  - Family member registry linked to flats.
  - **Dual Verification System**: Mobile number verification (WhatsApp ID / Telegram Contact Share) and Email OTP verification.
  - **In-portal Self-Service Mobile Update**: Allows verified residents to update their contact numbers via email OTP validation and bot verification links.
  - **SSO Generation**: High-security, single-use, 15-minute signed HMAC portal tokens for Telegram WebApps and WhatsApp CTA links.

### 2.2 Financial Management & Society Dues
- **DocTypes & Scripts**: `Maintenance Billing Run`, `Cost Apportionment Template`, `Cost Apportionment Target`, `accounting/cost_center_validation.py`, `accounting/ineligible_itc.py`.
- **Key Capabilities**:
  - Maintenance charge calculation and automated batch billing run generation.
  - Direct integration with ERPNext `Sales Invoice` and customer general ledger balances.
  - Real-time resident balance calculation (dues, credits, and unsettled invoices).
  - Indian GST compliance hooks: automated Cost Center validation and reversal/handling of Ineligible Input Tax Credit (ITC).
  - Web portal dues view with downloadable breakdown and payment integration hooks.

### 2.3 Parking Allocation & Rental Exchange
- **DocTypes**: `Parking Slot`, `Parking Allocation`, `Parking Rental Offer`, `Parking Rental Bid`.
- **Key Capabilities**:
  - Physical parking slot registry categorized by block, basement, open, and covered spaces.
  - Primary parking allocation mapping to flats and resident vehicles.
  - **Internal Society Parking Exchange**: Residents can post vacant slots for rent (`Parking Rental Offer`) and other residents can place bids (`Parking Rental Bid`).
  - Web portal interface to browse, bid, and manage rental agreements.

### 2.4 Vehicles & Gate Access Control
- **DocTypes**: `Resident Vehicle`, `Resident Vehicle Make`, `Resident Vehicle Model`, `Visitor Log`, `Worker Pass`.
- **Key Capabilities**:
  - Vehicle registration tracking (RC number, parking tag, vehicle type, make, and model).
  - Fast-approval visitor management: residents can pre-approve guests and generate 4-digit temporary passcodes.
  - Security Guard Gate Verification API (`society_erp.api.guard.verify_entry_code`) to validate visitor passcodes in real time.
  - Contractor and temporary worker gate passes with validity timeframes.

### 2.5 Helpdesk & Maintenance Ticketing
- **DocTypes**: `Maintenance Ticket`, `Maintenance Block Details`, `Housekeeping Work Log`.
- **Key Capabilities**:
  - Issue ticketing categorised by trade (Plumbing, Electrical, Carpentry, Masonry, Housekeeping).
  - Ticket allocation to internal Quick Response Teams (QRT) or external vendors.
  - Resident ticket status tracking with before/after photo attachment.
  - Service dispatcher and daily automated QRT digest tasks (`society_erp/tasks/qrt_digest.py`).
  - Web interface `/maintenance_job` for technician dispatch, status update, and signature capture.

### 2.6 Domestic Staff & Attendance
- **DocTypes**: `Domestic Staff`, `Staff Flat Link`, `Staff Review`, `Staff Attendance Log`.
- **Key Capabilities**:
  - Society-wide registry of verified domestic helpers, maids, cooks, drivers, and gardeners.
  - Linking staff to multiple flats.
  - Daily entry/exit attendance logging.
  - Resident reviews, ratings, and shared domestic staff directory.

### 2.7 Facility Management, AMC & Shift Roster
- **DocTypes**: `Facility Agency`, `Facility Contract`, `Facility Contract Quota`, `Facility Shift`, `Facility Duty Post`, `Facility Shift Muster`, `Facility Staff`, `Facility Staff Attendance`, `Facility AMC Log`, `Facility Invoice Reconciliation`.
- **Key Capabilities**:
  - Vendor contract management detailing manpower quotas (Guards, Supervisors, Housekeepers).
  - 12-hour and 8-hour shift definitions with automated duty post deployments.
  - Daily shift muster recording actual deployments vs contractual quotas.
  - Automated agency invoice reconciliation against recorded staff attendance.
  - Asset AMC maintenance logging and compliance tracking.
  - Comprehensive Agency Web Portal (`/agency`) with live supervisor dashboards.

### 2.8 Utilities & Environmental Monitoring
- **DocTypes**: `Block Water Log`, `Water Tanker Log`, `Tank Cleaning Log`, `STP Chemical Log`.
- **Key Capabilities**:
  - Daily water supply tracking, borewell operation, and municipal supply metrics.
  - Water tanker delivery logs with capacity, vendor, invoice, and dip-stick validation.
  - Sewage Treatment Plant (STP) chemical dosing, test parameters, and log registers.
  - Underground/overhead water tank cleaning cycles and statutory hygiene schedules.

### 2.9 Governance, Democratic Voting & Elections
- **DocTypes & Modules**: `Voting Poll`, `Voting Option`, `Voting Ballot`, `Voting Eligibility`, `Voting Participation`, `Electorate Publication`, `Electorate Objection`, `Provisional Electorate Member`, `Board Resolution`, `Resolution Signatory`, `voting/`.
- **Key Capabilities**:
  - Full statutory election workflow: voter list publication, claims and objections period, final voter list freezing.
  - Secret ballot voting with eligibility rules (one vote per flat, owner voting rights, dues clearance criteria).
  - Pluggable voting consensus providers (`society_erp/voting/provider.py`) with cryptographic ballot verification.
  - Official Board Resolutions registry with committee member digital sign-off.

### 2.10 Community & Communications
- **DocTypes**: `Society Notice`, `Resident Classified`, `Resident Pets`, `Emergency Contact`, `Facility Booking`, `Push Subscription`.
- **Key Capabilities**:
  - Digital circulars and notices pinned to resident dashboards.
  - Community classifieds marketplace (buy/sell, items, services).
  - Society pet registry tracking vaccination dates and breed information.
  - Community clubhouse and amenity booking engine (`Facility Booking`).
  - Emergency contact directory (police, fire, ambulance, lift rescue, plumbers, electricians).
  - Web Push notifications using standard VAPID Web Push protocol (`society_erp/push_notifications/`).

---

## 3. Implementation Status: Completed vs. Pending Work

### 3.1 Completed Work

#### Omnichannel Gateway & Bot Migration (from `society_migration_blueprint.md`)
- [x] **Headless JSON Architecture**: Extracted all business logic out of legacy Flask `society_bot` into pure `@frappe.whitelist()` APIs under `society_erp/api/`.
- [x] **Identity Resolution & Dual Verification**: `Channel Identity` table and `society_erp.api.identity.resolve_chat_user` supporting Telegram and WhatsApp users.
- [x] **OTP Email Verification**: Automated 6-digit OTP delivery, secure verification, and immediate DB commit for instant menu activation.
- [x] **Passwordless WebApp SSO**: 15-minute cryptographically signed portal URLs (`society_erp.api.sso.generate_portal_link`).
- [x] **Universal Chatbot Master Flow**: Configured `kvc3_main_flow` supporting 12+ interactive cards with looping back-navigation (`[🔙 Back to Main Menu]`).
- [x] **WhatsApp Cloud API Integration**: Production-ready WhatsApp formatting supporting Quick Reply buttons (up to 3), Interactive Lists (4–10 items), and CTA URL buttons.
- [x] **Self-Service Mobile Number Change on Portal**: Resident portal `/resident/profile` and verification screen provisioned with email-OTP-authorized mobile number modification and 1-click bot verification link.
- [x] **Whois Chat User API**: `society_erp.api.identity.whois_chat_user` supporting Telegram reply queries, flat searches, and staff device lookups.

#### Core ERP & Residential Modules
- [x] **Flat Master & Tenancy Engine**: Complete lifecycle of Owners, Tenants, and Family linkages.
- [x] **Financial Dues & Ledger Integration**: Real-time sales invoice balance queries, cost center validations, and maintenance billing run framework.
- [x] **Parking Management & Internal Exchange**: Slot allocations, rental offers, and rental bids.
- [x] **Vehicle Registry & Guard Passcode API**: Vehicle lookups and gate passcode verification API for security personnel.
- [x] **Maintenance Ticketing & Job Cards**: Ticket logging, photo capture, status tracking, and web technician job cards.
- [x] **Domestic Staff & Attendance Tracking**: Directory, flat linkages, reviews, and daily attendance logs.
- [x] **Facility & Agency Management**: Contracts, duty posts, shift musters, attendance reconciliation, and dedicated `/agency` portal.
- [x] **Water & Utility Auditing**: Tanker logs, block water logs, STP chemical dosage, and tank cleaning logs.
- [x] **Democratic Voting & Electorate System**: Electoral rolls, voter objections, ballot casting, and consensus calculation algorithms.
- [x] **Web Push Notification Infrastructure**: VAPID keys, service worker, and subscription storage.

---

### 3.2 Pending & Ongoing Work

| Area | Feature / Task | Priority | Status | Details |
| :--- | :--- | :---: | :---: | :--- |
| **Cutover** | Production Telegram Webhook Switch | **High** | Ready for Cutover | Point production Telegram bot (`@kvc_iii`) webhook to `universal_chatbot` endpoint (`handle_incoming`). |
| **Decommission** | Legacy `society_bot` Sunsetting | **High** | Pending Cutover | Stop legacy Flask supervisor process, remove config, archive `apps/society-bot` codebase. |
| **Payment Gateway** | Live Payment Gateway Integration | **Medium** | Pending Implementation | Integrate Razorpay / PayU / UPI payment gateway on the Resident Portal `/resident/dues` for instant online dues settlement and automatic `Payment Entry` creation. |
| **Access Control** | ANPR / RFID Boom Barrier Integration | **Medium** | Backlog | Connect gate boom barriers via webhook or MQTT using vehicle RFID tags / number plates stored in `Resident Vehicle`. |
| **Amenities** | Online Facility Booking Payment & Slots | **Medium** | In Progress | Connect clubhouse/hall facility booking slots to online payment and automated booking calendar conflict resolution. |
| **Accounting** | Automated Utility Invoicing | **Low** | Backlog | Auto-generate monthly electricity/water sub-meter invoices based on `Block Water Log` or sub-meter inputs. |
| **Mobile App** | PWA Offline Caching & App Store TWA | **Low** | Backlog | Package `/resident` and `/agency` as Trusted Web Activities (TWA) or full Progressive Web Apps (PWA) with offline caching. |

---

## 4. API & Integration Reference Matrix

| Endpoint | HTTP / RPC Path | Purpose |
| :--- | :--- | :--- |
| **Chat Identity** | `society_erp.api.identity.resolve_chat_user` | Resolves channel user to flat, profile, verification & committee status. |
| **Chat Whois** | `society_erp.api.identity.whois_chat_user` | Admin / committee query for flat, resident, and staff lookup. |
| **Service Dispatcher**| `society_erp.api.service_dispatcher.handle_service_request` | Central dispatcher for conversational chat actions and OTP verification. |
| **Portal SSO** | `society_erp.api.sso.generate_portal_link` | Issues signed 15-minute SSO links for seamless WebApp authorization. |
| **Dues & Ledger** | `society_erp.api.dues.get_flat_dues` | Fetches ledger balance and submitted outstanding invoices for a flat. |
| **Vehicles** | `society_erp.vehicle_portal.get_vehicles` | Lists registered 2-wheelers and 4-wheelers for resident's flat. |
| **Parking Slots** | `society_erp.api.parking.get_my_parking_slots` | Returns allotted slots and active exchange bids/offers. |
| **Tenants** | `society_erp.tenant_portal.get_tenants` | Fetches active and upcoming lease records for an owner. |
| **Family** | `society_erp.api.resident_family.get_family_members` | Lists linked family members. |
| **Domestic Staff** | `society_erp.api.domestic_staff.get_my_staff` | Returns verified staff assigned to the flat and attendance status. |
| **Visitors** | `society_erp.api.visitor.get_recent_visitors` | Returns recent visitor history and active entry passcodes. |
| **Pre-approve Visitor**| `society_erp.api.visitor.preapprove_visitor` | Issues 4-digit temporary gate entry passcode for visitors. |
| **Guard Gate Pass** | `society_erp.api.guard.verify_entry_code` | Validates gate entry code entered at security post. |
| **Helpdesk Tickets**| `society_erp.api.maintenance_portal.get_tickets` | Fetches resident tickets and work status. |
| **Committee Tickets**| `society_erp.api.maintenance_portal.get_committee_ticket_summary`| Returns aggregated breakdown of open society maintenance issues. |
| **Notices** | `society_erp.api.notices.get_active_notices` | Fetches active published society circulars and announcements. |
| **Resolutions** | `society_erp.api.resolutions.get_resolutions` | Returns list of approved and signed Board Resolutions. |
| **Push Notify** | `society_erp.push_notifications.api.save_subscription` | Registers browser VAPID push subscriptions. |

---

## 5. Security & Governance Policies
1. **Zero Secret Exposure**: All WhatsApp and Telegram API keys, VAPID credentials, and webhook tokens are stored in private site config / encrypted Single DocTypes.
2. **Strict Resident Data Isolation**: All resident queries enforce flat ownership or tenancy verification in Python methods using Frappe's session user or verified channel identity.
3. **Audit Trail**: Sensitive actions (electorate objections, committee member access, visitor entry validations, mobile number changes) write immutable audit logs in MariaDB.
4. **Idempotent Background Jobs**: Scheduled tasks such as maintenance digests and muster checks run through scheduled hooks without duplicating alerts.
