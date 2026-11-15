# Enterprise Architectural Blueprint: Omnichannel Migration & Sunsetting of `society_bot`

---

## 1. Executive Summary & Strategic Context

### 1.1 Objective
To decommission the bespoke standalone Python/Flask application (**`society_bot`** / **`kvciii_bot`**), transitioning all conversational interactions for our 1,220-flat Resident Welfare Association (RWA) connected to our ERPNext site (`kvc3.local`) into a decoupled two-tier architecture:

1. **`society_erp` (Domain Core & Data Engine)**:
   - Contains all residential domain models (`Owners`, `Tenants`, `Family Members`, `Customer`, `Resident Vehicle`, `Maintenance Ticket`, `Staff Attendance Log`, `Visitor Log`, `Work Permit`, `Notice`, `Board Resolution`, etc.).
   - Serves as the single source of truth for business rules, authorization, file ingestion, and transaction pipelines.
   - Operates strictly as a headless provider of clean, pure JSON data via `@frappe.whitelist()` endpoints.
   - Generates signed single-use SSO tokens for seamless authenticated WebApp bottom-sheet interactions.
   - **Zero conversational formatting, markdown rendering, or channel-specific logic exists in this app.**

2. **`universal_chatbot` (Domain-Agnostic Conversational Gateway)**:
   - Decoupled omnichannel gateway interfacing with Telegram Bot API, WhatsApp Cloud API, and Web Chat widgets.
   - Manages conversational graph execution (`FlowExecutor`), state tracking in MariaDB (`Conversation State`), variable interpolation, and channel adapter rendering.
   - Supports native rich interactive elements including Telegram WebApps / Mini Apps (`web_app_url`).
   - **Zero society concepts (flats, dues, vehicles, owners) exist in this app.** It connects to `society_erp` strictly through configured `Chatbot Integration` and `Integration Action` DocTypes.

```
+──────────────────────────────────────────────────────────────────────────────────────────+
|                                  MESSAGING CHANNELS                                      |
|                 Telegram Messenger                       WhatsApp Cloud API              |
+──────────────────────────────────────────────────────────────────────────────────────────+
                                          │
                                          ▼ (Inbound HTTPS Webhooks)
+──────────────────────────────────────────────────────────────────────────────────────────+
| UNIVERSAL CHATBOT GATEWAY                                                                |
|                                                                                          |
|  ┌─────────────────────────────────────┐         ┌─────────────────────────────────────┐ |
|  │ TelegramChannelAdapter              │         │ WhatsAppChannelAdapter              │ |
|  │ - Normalizes chat_id & callback_data│         │ - Normalizes phone & interactive id │ |
|  │ - Renders WebApp bottom-sheet button│         │ - Renders URL / Quick Reply buttons │ |
|  └──────────────────┬──────────────────┘         └──────────────────┬──────────────────┘ |
|                     └─────────────────────────┬─────────────────────┘                    |
|                                               ▼                                          |
|  ┌─────────────────────────────────────────────────────────────────────────────────────┐ |
|  │ Flow Engine & State Machine (FlowExecutor)                                          │ |
|  │ - Conversation State DocType: Persistent variables, checkpoints, active session     │ |
|  │ - Visual Node Graph: MultipleChoiceNode, ConditionNode, CallActionNode              │ |
|  │ - Recursive Dict Dot-Notation Evaluator (e.g. {{auth_res.unpacked.data...}})        │ |
|  └────────────────────────────────────────────┬────────────────────────────────────────┘ |
|                                               ▼                                          |
|  ┌─────────────────────────────────────────────────────────────────────────────────────┐ |
|  │ Outbound Connector Framework (FrappeRestConnector)                                   │ |
|  │ - Uses Integration Credential (Token api_key:api_secret)                            │ |
|  │ - Maps Integration Action parameters & unpacks JSON responses                       │ |
|  └────────────────────────────────────────────┬────────────────────────────────────────┘ |
+───────────────────────────────────────────────┼──────────────────────────────────────────+
                                                │ HTTP POST / RPC: /api/method/...
                                                ▼
+──────────────────────────────────────────────────────────────────────────────────────────+
| FRAPPE / ERPNEXT (society_erp on kvc3.local)                                             |
|                                                                                          |
|  ┌─────────────────────────────────────────────────────────────────────────────────────┐ |
|  │ Identity Bridge & Single Sign-On (SSO) Layer                                        │ |
|  │ - Channel Identity DocType: Resolves (channel, channel_user_id) -> resident_email   │ |
|  │ - society_erp.api.identity.resolve_chat_user: Whitelisted auth verification         │ |
|  │ - society_erp.api.sso.generate_portal_link: 15-minute signed token for WebApps      │ |
|  └────────────────────────────────────────────┬────────────────────────────────────────┘ |
|                                               │                                          |
|  ┌────────────────────────────────────────────┴────────────────────────────────────────┐ |
|  │ Headless Pure Data APIs (@portal_api & whitelisted JSON RPCs)                       │ |
|  │  ├── society_erp.api.dues.get_flat_dues(for_user)                                    │ |
|  │  ├── society_erp.vehicle_portal.get_vehicles(for_user)                              │ |
|  │  ├── society_erp.tenant_portal.get_tenants(for_user)                                │ |
|  │  ├── society_erp.api.visitor.get_recent_visitors(for_user)                          │ |
|  │  ├── society_erp.api.visitor.preapprove_visitor(for_user, visitor_name, ...)        │ |
|  │  ├── society_erp.api.parking.get_my_parking_slots(for_user)                         │ |
|  │  ├── society_erp.api.work_permit.get_work_permits(for_user)                         │ |
|  │  ├── society_erp.api.domestic_staff.get_my_staff(for_user)                          │ |
|  │  ├── society_erp.api.resident_family.get_family_members(for_user)                   │ |
|  │  ├── society_erp.api.maintenance_portal.get_tickets(for_user)                       │ |
|  │  ├── society_erp.api.maintenance_portal.get_committee_ticket_summary(for_user)      │ |
|  │  ├── society_erp.api.notices.get_active_notices()                                  │ |
|  │  ├── society_erp.api.resolutions.get_resolutions(limit)                             │ |
|  │  ├── society_erp.api.guard.verify_entry_code(passcode)                              │ |
|  │  └── society_erp.api.file.attach_channel_file(...)                                  │ |
|  └────────────────────────────────────────────┬────────────────────────────────────────┘ |
|                                               │                                          |
|  ┌────────────────────────────────────────────┴────────────────────────────────────────┐ |
|  │ Domain Models & MariaDB Tables                                                      │ |
|  │ Owners, Tenants, Customer, Resident Vehicle, Maintenance Ticket, Staff, Permits     │ |
|  └─────────────────────────────────────────────────────────────────────────────────────┘ |
+──────────────────────────────────────────────────────────────────────────────────────────+
```

---

## 2. Project Status & Progress Tracking

```
Overall Migration Completion: [==================================================> ] 98%
```

| Phase | Milestone / Component | Status | Verification & Deliverables |
| :--- | :--- | :---: | :--- |
| **Phase 1** | Identity Foundation & Channel Mapping | **COMPLETED** | `Channel Identity` DocType operational; `society_erp.api.identity.resolve_chat_user` returning verified resident profile, flat, and committee status (`is_committee_member`). |
| **Phase 2** | Backend Modular Data APIs | **COMPLETED** | 14 dedicated domain endpoints implemented in `society_erp/api/` covering Dues, Vehicles, Parking, Tenants, Family, Helpdesk, Staff, Notices, Resolutions, Work Permits, Visitors, and Guard Passcodes. |
| **Phase 3** | Secure Passwordless SSO for WebApps | **COMPLETED** | `society_erp.api.sso.generate_portal_link` creates one-time 15-minute HMAC tokens; `authenticate_sso` logs in resident session seamlessly within Telegram WebApp bottom-sheet and WhatsApp CTA browser links. |
| **Phase 4** | Universal Chatbot Engine Enhancements | **COMPLETED** | Added `web_app_url` support to `MultipleChoiceNode`, Telegram adapter, and WhatsApp adapter; fallback option key resolution (`unpacked.options` vs `unpacked.data.options`); dynamic context auto-injection (`channel`, `channel_user_id`, `phone_number`). |
| **Phase 5** | Integration Actions & Flow Deployment | **COMPLETED** | 14 `Integration Action` records registered; master resident flow (`kvc3_main_flow`) deployed with 12 interactive cards, looping back-navigation, and instant WebApp forms for mutations. |
| **Phase 6** | Telegram Channel Live E2E Validation | **COMPLETED** | Verified on `@kvc3_py_bot` via webhook; authentication, menu navigation, sub-menus, detail lookups, and `[🔙 Back to Main Menu]` transitions operational. |
| **Phase 7** | WhatsApp Cloud API Live Activation & Gating | **COMPLETED** | Meta WhatsApp Cloud API connected in production (`DEP-00001` / `1428481243686640`); channel adapter reformats rich menus into native interactive lists (`Select Option`) and CTA URL cards. Dual-verification gating (Mobile + Email) and in-chat OTP verification operational. |
| **Phase 8** | Web Portal Change-Mobile Self-Service | **PENDING** | On the Web Resident Portal, allow residents whose email is verified to request updating their registered mobile number by sending an automated WhatsApp/Telegram OTP verification code to the new mobile number. |
| **Phase 9** | Production Webhook Cutover & Sunsetting | **PENDING** | Repoint production Telegram bot (`@kvc_iii`) webhook to `universal_chatbot`, stop legacy supervisor daemon `society_bot`, and archive `apps/society-bot`. |

---

## 3. Dual-Channel Verification & Authentication Flow

### 3.1 Gated Access Rule
To protect resident data, society services are strictly gated behind verified identity on both communication channels:
1. **Mobile Verification**:
   - On **WhatsApp**: Mobile number is automatically authenticated from the verified sender WhatsApp ID (`external_user_id`).
   - On **Telegram**: Verified via 1-click native Telegram Contact Sharing button (`request_contact: True`).
2. **Email Verification**:
   - Until email is verified, all service tiles and menu options remain locked (`verification_pending = True`).
   - The resident is greeted with their flat number and masked email (e.g. `mdfa***@gmail.com`).
   - The resident replies with their full email.
     - If matching the registered record, a 6-digit OTP is generated and emailed to the address.
     - If mismatching, a `✏️ Change Email` button is provided allowing an in-band update via OTP.
   - Upon replying with the 6-digit OTP:
     - The database updates `is_email_verified = 1` and commits immediately.
     - The full interactive society service menu (`Select Option` with 9 tiles) is displayed with immediate access.

### 3.2 Conversational Navigation & Routing Rules
- Words such as `"hi"`, `"hello"`, `"hey"`, `"start"`, or `"menu"` automatically transition to the User Resolver / Main Menu without triggering fallback error cards ("Service 'hi' is being updated").
- Clean single-purpose action options: Intermediary steps (such as "Verification Code Sent" or "Change Email") do not show redundant `[🏠 Main Menu]` buttons to prevent user confusion.
- Multi-URL cards (such as Accounts & Dues or Committee sub-tiles) render secure 1-click CTA URLs directly into WhatsApp message bodies and interactive buttons.

---

## 4. Work Completed in Recent Iterations (November 2026)

1. **WhatsApp Channel Formatting & Rich Interaction**:
   - Fixed `WhatsAppChannelAdapter.format_response`:
     - Preserves full option metadata (`label`, `value`, `web_app_url`, `url`, `desc`).
     - Up to 3 options rendered as native WhatsApp Reply Buttons (`type: button`).
     - 4 to 10 options rendered as a native WhatsApp Interactive List (`type: list`, button: `Select Option`).
     - Single portal URL actions formatted as WhatsApp CTA URL buttons (`type: cta_url`) with secondary navigation split-delivery.
2. **Flow Engine Fallback & Template Variable Resolution**:
   - Enhanced `MultipleChoiceNode` to gracefully resolve options from both `service_res.unpacked.data.options` and `service_res.unpacked.options`.
   - Updated template interpolation for service cards to fallback between `{{service_res.unpacked.data.prompt}}` and `{{service_res.unpacked.prompt}}`.
3. **Database Immediate Commit on OTP Match**:
   - Added `frappe.db.commit()` in `society_erp/api/service_dispatcher.py` immediately after `frappe.db.set_value(doctype, target_doc, "is_email_verified", 1)`.
   - Fixed issue where subsequent call to `get_resident_menu()` read stale unverified state and returned empty options.
4. **Flow Transition Rule Sanitization**:
   - Updated `kvc3_chatbot-kvc3_main_flow` transitions in `tabFlow Transition`:
     - Transition `show_service_card -> resolve_user_node`: Condition set to `sub_action in ["menu", "hi", "hello", "start"]`.
     - Transition `show_service_card -> fetch_service_data`: Condition set to `sub_action != "gen_pass" and sub_action not in ["menu", "hi", "hello", "start"]`.

---

## 5. Pending Tasks for Subsequent Conversations

1. **Web Resident Portal: Change Mobile Number Flow**:
   - In the web portal (`/resident/profile` / `/resident/flat`), if a resident's email is already verified:
     - Allow changing the registered mobile number.
     - Trigger an automated OTP message sent to the newly entered mobile number via WhatsApp Cloud API (or Telegram if linked).
     - Provide an OTP verification modal on the portal to finalize the mobile number update.
2. **Production Telegram Webhook Cutover**:
   - Switch production Telegram bot webhook from legacy Flask to `universal_chatbot` endpoint.
3. **Legacy `society_bot` Sunsetting**:
   - Verify all active tenants and owners are successfully communicating via `universal_chatbot`.
   - Decommission legacy Flask processes, systemd/supervisor units, and archive `apps/society-bot`.

---

## 3. Legacy Porting Matrix (All Features Accounted For)

Every module from the standalone `apps/society-bot/` has been completely migrated to the new architecture:

| Legacy `society_bot` Module | Legacy Mechanism | Target Architecture & Implementation | Status |
| :--- | :--- | :--- | :---: |
| `routers/auth_router.py` | Standalone Flask session + OTP generator | `society_erp.api.identity.resolve_chat_user` + `Channel Identity` table in MariaDB. | **MIGRATED** |
| `routers/dues_router.py` | Local sum calculation on raw invoice list | `society_erp.api.dues.get_flat_dues` (ledger balance & submitted sales invoices). | **MIGRATED** |
| `routers/vehicle_router.py` | Multi-turn chat wizard asking for RC, plate, type | Fast summary via chat + instant bottom-sheet WebApp form via `society_erp.api.sso.generate_portal_link(page="/vehicles")`. | **MIGRATED** |
| `routers/parking_router.py` | Hardcoded slot lookups in custom table | `society_erp.api.parking.get_my_parking_slots` querying `tabResident Vehicle` allotted slot mappings. | **MIGRATED** |
| `routers/tenant_router.py` | Multi-turn wizard for lease & tenant info | Summary in chat + instant bottom-sheet WebApp form via `generate_portal_link(page="/tenants")`. | **MIGRATED** |
| `routers/family_router.py` | Multi-turn chat wizard for family members | `society_erp.api.resident_family.get_family_members` + WebApp management link (`page="/family"`). | **MIGRATED** |
| `routers/ticket_router.py` | Chat photo upload + custom ticket endpoint | `society_erp.api.maintenance_portal.get_tickets` + WebApp form with native photo selector (`page="/portal-tickets"`). | **MIGRATED** |
| `routers/staff_router.py` | Staff search & attendance queries | `society_erp.api.domestic_staff.get_my_staff` returning linked cooks/maids + WebApp directory (`page="/staff-directory"`). | **MIGRATED** |
| `routers/visitor_router.py` | Pre-approvals & gate passcode generation | `society_erp.api.visitor.get_recent_visitors` and `preapprove_visitor` generating 4-digit security OTPs. | **MIGRATED** |
| `routers/work_permit_router.py` | Contractor permit queries | `society_erp.api.work_permit.get_work_permits` returning renovation/service permits & expiry dates. | **MIGRATED** |
| `routers/notice_router.py` | Custom circular markdown formatter | `society_erp.api.notices.get_active_notices` returning active pinned society circulars. | **MIGRATED** |
| `routers/resolution_router.py` | Custom resolution scraper | `society_erp.api.resolutions.get_resolutions` querying approved `tabBoard Resolution` records. | **MIGRATED** |
| `routers/guard_router.py` | Bot passcode verification at security gate | `society_erp.api.guard.verify_entry_code` checking against active `tabVisitor Passcode` entries. | **MIGRATED** |
| `routers/aoa_router.py` | Committee member list & committee ticket breakdown | `society_erp.api.maintenance_portal.get_committee_ticket_summary` (restricted to verified committee members). | **MIGRATED** |

---

## 4. Key Architectural Patterns Implemented

### 4.1 Hybrid Conversational + WebApp Pattern
Instead of fragile, error-prone 6-step conversational text wizards for uploading vehicle RC documents, tenant police verifications, or maintenance photos, the system uses a **Hybrid Conversational + WebApp Pattern**:
- **Read Operations**: Fast, interactive inline keyboard summaries directly inside Telegram / WhatsApp (balances, slot numbers, active visitor passes).
- **Mutations & Document Uploads**: Seamless Telegram Mini App (WebApp) bottom-sheets loaded via signed 15-minute single-use SSO tokens (`society_erp/api/sso.py`), utilizing existing tested responsive web forms without re-prompting for credentials.

### 4.2 Non-Closing Interactive Session Graph
In `universal_chatbot`, reaching a terminal node closes the `Chat Conversation`. To provide a modern continuous app-like experience:
- Detail view cards are implemented as `Multiple Choice` nodes.
- Each view card provides:
  1. Action-specific buttons (e.g. `[➕ Add Vehicle (WebApp)]`, `[💳 View Invoices (WebApp)]`).
  2. A persistent `[🔙 Back to Main Menu]` transition button that routes back to the main greeting node, keeping the conversation active and responsive indefinitely.

---

## 5. Remaining Cutover & Decommissioning Plan

### Phase 7: Production Webhook Cutover
1. Verify production domain and reverse proxy SSL certificates.
2. Update the production Telegram Bot webhook to the `universal_chatbot` endpoint:
   ```bash
   curl -F "url=https://<public_domain>/api/method/universal_chatbot.api.v1.webhook.handle_incoming?channel=telegram&deployment_key=kvc3_prod" \
        https://api.telegram.org/bot<PROD_TELEGRAM_BOT_TOKEN>/setWebhook
   ```
3. Monitor inbound messages in `tabChat Message` and `tabConversation State`.

### Phase 8: WhatsApp Cloud API Activation
1. Create a `Bot Channel` for WhatsApp in `universal_chatbot`:
   - Channel Type: `WhatsApp`
   - WhatsApp Phone Number ID: `<phone_number_id>`
   - System User Access Token: `<system_token>`
   - Webhook Verification Token: `<webhook_verify_token>`
2. Configure Meta Developer Portal Webhook callback URL to point to `/api/method/universal_chatbot.api.v1.webhook.handle_incoming`.
3. Test end-to-end flow with resident phone numbers mapped in `Channel Identity`.

### Phase 9: Decommissioning `society_bot`
1. Stop supervisor process:
   ```bash
   sudo supervisorctl stop society_bot
   sudo rm /etc/supervisor/conf.d/society_bot.conf
   sudo supervisorctl reread && sudo supervisorctl update
   ```
2. Archive legacy code repository:
   ```bash
   tar -czf /home/mdfaisal/frappe-bench/backups/society-bot-archive-$(date +%F).tar.gz /home/mdfaisal/frappe-bench/apps/society-bot
   ```
3. Remove or archive the `apps/society-bot` folder from the bench.
