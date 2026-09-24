# Admin Workflow Capability Recommendations — Farm Owner & Administrator

**Project:** Tambulig Poultry Farm Management System
**Author:** Architecture review (senior Django) — 2026-09-23
**Baseline:** v1 buyer/supplier portal + `/api/v2/` implemented (see `buyer_supplier_implementation.md`); 64 tests green.

This document analyzes the current Owner/Admin workflow surface and recommends targeted enhancements in four areas: role capabilities, sidebar navigation, transaction workflow logic, and the enforcement/implementation strategy.

---

## 0. Current State (what the code actually does today)

| Concern | Current implementation | Location |
|---|---|---|
| Roles | `User.ROLE_CHOICES` = admin / owner / staff / buyer / supplier; helpers `is_admin_user()`, `is_owner()`, `is_internal()`, `is_external()` | `accounts/models.py:6-44` |
| External containment | `ExternalPortalAccessMiddleware` allowlists `/portal/, /static/, /media/, /logout/, /notifications/` for external roles | `config/middleware.py:11` |
| Portal guard | `external_portal_required(role)` — role + approved + `is_active` | `accounts/access.py:12` |
| Admin guard | `admin_or_owner_required` — **applied to only 2 views** (`accounts/views.py:84,98`) | `accounts/access.py:37` |
| Account linkage | `create_portal_account(profile, role, operator)` — staff-vouched, pre-approved, 1:1 via `OneToOneField(user)` | `accounts/access.py:48` |
| Sales pipeline | `OrderRequest` lifecycle `submitted → under_review → quoted → accepted → converted`, queue + review views under `/sales/requests/` | `sales/urls.py:8-9` |
| Procurement pipeline | `DeliveryNotice` `announced → received/rejected`, queue + review under `/expenses/deliveries/`, expense prefill on receive | `expenses/urls.py:8-9` |
| Sidebar badges | `queue_context` processor computes `open_order_requests`, `open_delivery_notices`, `pending_verifications` (skipped for external users) | `config/context_processors.py` |
| API | `/api/` read-only owner app; `/api/v2/` portal + internal endpoints | `api/views_v2.py` |

**Key gap found during this review:** every internal view is protected by `@login_required` only. External users are kept out by the middleware redirect, but that is a *redirect*, not an authorization boundary — e.g. a `buyer` POSTing to `/buyers/5/account/create/` is bounced to `/portal/` (safe today), yet any future URL added outside the allowlist prefix logic silently becomes externally reachable. There is no `internal_only` decorator in `accounts/access.py` despite the plan (§1.4) calling for one. This is fixed in §4.1.

---

## 1. Role Capability Expansion

### 1.1 Design principle

Keep the existing invariant: **the farm is the source of truth; money-moving records are created only by internal users.** Expansion should give Owner/Admin *oversight and control levers*, not new data entry paths (staff already handle entry). Differentiation:

- **Staff/Caretaker** — operational: record sales/expenses, work queues, manage contact records. Cannot verify accounts, cannot edit/delete financial records after the fact, cannot manage Users.
- **Farm Owner** — business oversight: everything staff can do + financial corrections, verification, credit limits, reports, and read of the owner mobile API.
- **Administrator** — system custody: everything Owner can do + user account lifecycle (create/edit/delete internal Users), settings, password resets for external users.

### 1.2 Extended permission matrix (additions to plan §1.3)

| Capability | staff | owner | admin |
|---|:-:|:-:|:-:|
| Record direct sale (`SalesRecord`) | ✅ | ✅ | ✅ |
| Edit/delete a `SalesRecord` after creation | ❌ (proposal) | ✅ | ✅ |
| Quote/reject/convert `OrderRequest` | ✅ | ✅ | ✅ |
| Override quoted price at conversion time | ❌ (proposal) | ✅ | ✅ |
| Set/enforce `Buyer.credit_limit` | ❌ | ✅ | ✅ |
| Record expense / receive `DeliveryNotice` | ✅ | ✅ | ✅ |
| Cancel a supplier notice on the farm's behalf | ✅ (with reason) | ✅ | ✅ |
| CRUD Buyer/Supplier contacts | ✅ | ✅ | ✅ |
| Create portal account for a contact | ✅ (vouches → approved) | ✅ | ✅ |
| Deactivate portal account / contact | ❌ (proposal) | ✅ | ✅ |
| Approve/reject verifications | ❌ | ✅ | ✅ |
| Reset external user password | ❌ | ✅ | ✅ |
| Manage internal `User` accounts | ❌ | ❌ (proposal) | ✅ |
| App settings | ❌ | 👁 read | ✅ |
| Reports & exports | ✅ | ✅ | ✅ |

### 1.3 Concrete capability additions

1. **Credit-limit enforcement at conversion.** `Buyer.credit_limit` exists but is inert. On `order_request_convert` (and direct `sales_create` with `payment_status != paid`), compute the buyer's unpaid balance (`SalesRecord.balance()` sum) + new amount; if it exceeds `credit_limit`, block with a form error **unless** `request.user.is_admin_user() or is_owner()` (they may override, logged via `log_activity`).
2. **Financial correction audit.** Owner/Admin edits/deletes of `SalesRecord`/`ExpenseRecord` must write an `ActivityLog` entry with old vs new `total_amount`. Staff simply don't get the edit/delete URLs (§4.2).
3. **External account custody.** Move `buyer_create_account` / `*_deactivate_account` / `verification_action` semantics to match the matrix: deactivate & verification → `admin_or_owner_required`; create (staff-vouched) stays staff+ but records `verified_by=operator` (already does).
4. **Password reset for external users.** Add `POST /users/<pk>/reset-portal-password/` (admin/owner only, internal users excluded): generates a new random password via the existing `get_random_string` pattern, displays it once, forces the user to change it at `/portal/profile/`. Keeps plan §3.6 v1 reality (no SMTP).
5. **Owner KPI surfacing.** The owner's read-only API already covers mobile; on the web dashboard add an "Open commitments" card: sum of unpaid `SalesRecord.balance()` (receivables) and unpaid supplier expenses (payables) — pure aggregation of existing models, no new fields.

---

## 2. Sidebar Navigation Logic (`templates/base.html`)

### 2.1 Current problems

- **Farm Operations is overloaded (8–10 links):** production (Flocks, Feeding, Eggs, Mortality, Medicine) is mixed with money flows (Sales, Expenses) and their queues (Order Requests, Deliveries).
- **Queue links are conditional on count** (`{% if open_order_requests %}`, base.html:150,158): when the queue empties the link vanishes — users lose the mental map of where work goes, and there is no way to see *completed* requests without typing the URL.
- **Buyers/Suppliers sit under "Records" with Reports**, while the workflows that consume them (Sales/Expenses) are two sections away.
- **Administration block is admin/owner-only, but Users/Verifications/Settings are the only partner-management entry points scattered from their domain pages.**

### 2.2 Recommended grouping (labels only — keep all URL names/paths stable)

```
Overview
  Dashboard

Farm Operations                     (production — unchanged audience: staff+)
  Flocks · Feeding · Eggs · Mortality · Medicine

Sales & Orders                      ← NEW GROUP
  Sales                             (/sales/)
  Order Requests        [badge]     (/sales/requests/) — ALWAYS shown, see 2.3
  Buyers                            (/buyers/)

Procurement & Inventory             ← NEW GROUP
  Inventory                         (/inventory/)
  Expenses                          (/expenses/)
  Deliveries            [badge]     (/expenses/deliveries/) — ALWAYS shown
  Suppliers                         (/suppliers/)

Partners & Reports                  ← role-conditional
  Reports                           (/reports/)
  Verifications         [badge]     admin/owner only

Administration                      (unchanged gate: admin/owner)
  Users · Settings
```

Rationale: each money workflow becomes a self-contained column of work — *request → queue → record → counterparty*. A staff member selling eggs sees Sales, Order Requests and Buyers in one visual group; procurement work lives entirely in the second group. Medicine could fold under a collapsible "Health" sub-menu later if the group grows (see 2.4).

### 2.3 Queue links: always visible, badge = open count

Change `{% if open_order_requests %}` to always render the link, with the badge shown only when `>0`, and add a muted "all clear" state. Implementation: `queue_context` should return counts plus a boolean; the template keeps one `<a>` and conditionally renders `<span class="nav-badge">`. Benefits: stable navigation, and the queue pages already handle the empty/converted history view — users can review `converted`/`rejected` items without bookmarking.

### 2.4 Sub-menu (optional, phase 2)

If the 17-link sidebar feels long, make group headers collapsible with Alpine (`x-data="{ openSales: true }"`, persisted in `localStorage`), defaulting open for the group matching `request.path` prefix. No server changes needed. Do **not** introduce hover-flyout menus — the primary device for staff is a phone (current `lg:hidden` drawer pattern).

### 2.5 Active-state hygiene

Current active checks use substring tests (`'/sales/' in url`) which double-highlight on nested paths. Since queue pages already key off `'/sales/requests' in url`, standardize on `request.resolver_match.url_name` comparisons (the pattern already proven in `templates/portal/_nav_links.html`) — one canonical active rule per link.

---

## 3. Workflow Optimization

### 3.1 Sales: Admin-initiated vs Buyer-initiated (unified funnel)

Today both paths exist but don't converge: staff record `SalesRecord` directly (`sales_create`), while buyer requests travel the `OrderRequest` lifecycle. Recommendation — make **`OrderRequest` the single funnel for non-cash sales**, keep direct recording for walk-in cash:

```
BUYER PATH (portal)                 ADMIN/STAFF PATH (internal)
submit OrderRequest ─┐              record SalesRecord directly (walk-in, paid) ← unchanged
                     ▼
        staff queue: review ──► quote / reject
                     │ (buyer accepts)
                     ▼
              convert ──► SalesRecord (+ credit check §1.3.1)
                     ▲
        NEW: staff "New request on behalf of buyer"
        (same form, created_by=staff, status jumps
         straight to accepted → convert in one screen)
```

Concrete changes:

1. **Staff-authored OrderRequest (phone orders).** Add `POST /sales/requests/create-on-behalf/` reusing `OrderRequestForm` with `buyer` as a dropdown. Phone/visit orders are the farm's dominant channel today; today staff must either open the buyer portal flow (impossible) or write the sale directly, losing the quote/acceptance audit trail. On behalf-of requests get `status=accepted` immediately (there is no portal counterparty to quote to) and flow through the same convert step. Add a `source` field: `choices [portal, staff]` (one nullable CharField migration).
2. **Convert as explicit action.** Extract conversion into its own URL `POST /sales/requests/<pk>/convert/` (GET renders prefilled `SalesRecord` form; POST saves + flips status + notifies buyer). Currently review and convert share `order_request_review`; separating them makes the permission story simpler (convert = staff+, price override = owner/admin+, §1.2) and gives a clean notification seam.
3. **Quote expiry (cheap guardrail).** `OrderRequest` in `quoted` for > N days (settings key, default 7) shows an amber "stale" pill in the queue and the review form requires staff+ to re-quote rather than accept. No cron needed — compute from `updated_at` at render time.
4. **Status transitions stay in the model.** Move the allowed-transition map into `OrderRequest` methods (`can_quote()`, `accept(by)`, `convert_to(sale)`) so web views, `/api/v2/` serializers and future flows share one implementation (plan §4.2 already mandates serializer-level validation — centralize it on the model).

### 3.2 Procurement: Admin purchase orders vs Supplier delivery notices

Today only the supplier-initiated path exists (`DeliveryNotice`). The farm cannot yet express "we ordered 50 sacks of layer feeds" — staff must wait for a supplier to announce, or book an expense with no linkage. Recommendation — **PO-lite via `DeliveryNotice.origin`:**

```
SUPPLIER PATH                        ADMIN/STAFF PATH
maintain SupplyItem catalog          NEW: create DeliveryNotice(origin=farm,
announce DeliveryNotice(origin=supplier)   supplier + item + qty + expected_date,
        │                                  status=announced, no portal action)
        ▼                                          │
   staff queue: receive ────► ExpenseRecord (payment_terms prefill — exists)
        │                                  ▲
        ▼                                  │
   notify supplier (exists)      supplier sees "farm-ordered" items in their
                                 Deliveries list, marks "on the way" (status
                                 stays announced; expected_date editable)
```

1. Add `DeliveryNotice.origin = CharField(choices=[supplier, farm], default=supplier)`. Farm-origin notices are created at `POST /expenses/deliveries/create/` (staff+), scoped to that supplier's active `SupplyItem`s. This reuses the entire existing receive→expense pipeline — no new model, no new status.
2. Supplier portal shows farm-origin notices in the Deliveries list with a "Requested by farm" pill; supplier's only power is editing `expected_date` and adding a note (a small `supplier_note` field), never quantity/price.
3. Queue badge logic: farm-origin notices count toward `open_delivery_notices` exactly like supplier ones — staff see one unified inbound-shipments queue.
4. **Rejection symmetry:** staff rejecting a supplier notice already exists; add supplier-side "cannot deliver" cancel for their own `announced` notices (`POST /portal/supplier/deliveries/<pk>/cancel/`), status `rejected` + note. Prevents zombie announcements inflating the farm's badge.

### 3.3 Notification wiring (reuse, don't rebuild)

Every transition above already has a seam in the `notifications` app. Add exactly four new notification points: (a) farm-origin notice created → notify supplier user; (b) supplier cancels own notice → notify the `received_by`/creator staff user; (c) quote stale (>N days) → piggyback on queue page render, no email; (d) conversion blocked by credit limit → notify owner+admin users once per attempt (dedupe by `link` + date).

---

## 4. Implementation Strategy

### 4.1 Authorization hardening (do this first — it's a prerequisite for everything else)

**Add the missing `internal_only` decorator and a role helper to `accounts/access.py`:**

```python
def internal_only(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_internal():
            return HttpResponseForbidden("Internal access required.")
        return view(request, *args, **kwargs)
    return wrapper

def admin_or_owner(view):        # thin wrapper over existing check, for uniform naming
    ...
```

Apply `@internal_only` to **every** internal web view (sales, expenses, buyers, suppliers, inventory, flocks, …) as belt-and-braces alongside `@login_required` — mirroring plan §1.4 ("existing behavior" was never actually implemented). Layered model after this:

| Layer | Mechanism | Catches |
|---|---|---|
| 1. Middleware | prefix allowlist for externals | navigation mistakes, keeps UX (redirect not 403) |
| 2. `@internal_only` | view-level role check | any URL outside middleware scope; direct POSTs |
| 3. `@admin_or_owner` | elevated actions | staff overreach (verification, deactivation, corrections) |
| 4. Queryset scoping | `request.user.buyer/supplier` filter | party-to-party leaks in portal + `/api/v2/` |

**1:1 invariant protection:** the `OneToOneField` on `Buyer.user` / `Supplier.user` (with `SET_NULL`) already guarantees the relationship; add one guard in `create_portal_account`: if `profile_obj.user` is not None, raise `ValueError` instead of creating an orphan second account. Deactivation must flip **both** `profile.is_active` and `user.is_active` (plan §3.2 rule; verify the current `*_deactivate_account` views do — if only one is flipped, fix it, since `external_portal_required` checks `profile.is_active` while `TokenAuthentication` checks `user.is_active`).

### 4.2 New/changed views & URL patterns

| URL | Method | View (app) | Guard | Status |
|---|---|---|---|---|
| `/sales/requests/create-on-behalf/` | GET/POST | `order_request_create_internal` (sales) | `internal_only` | NEW §3.1.1 |
| `/sales/requests/<pk>/convert/` | GET/POST | `order_request_convert` (sales) | `internal_only`; price override checks role in-view | EXTRACT from review §3.1.2 |
| `/expenses/deliveries/create/` | GET/POST | `delivery_notice_create` (expenses) | `internal_only` | NEW §3.2.1 |
| `/portal/supplier/deliveries/<pk>/cancel/` | POST | portal supplier view | `external_portal_required("supplier")` + owner-scope | NEW §3.2.4 |
| `/users/<pk>/reset-portal-password/` | POST | `reset_portal_password` (accounts) | `admin_or_owner` + `user.role in EXTERNAL_ROLES` | NEW §1.3.4 |
| `/buyers/<pk>/account/deactivate/`, `/suppliers/<pk>/account/deactivate/` | POST | existing | **upgrade** `login_required` → `admin_or_owner` | CHANGE §1.2 |
| `/sales/<pk>/edit/`, `/sales/<pk>/delete/`, `/expenses/<pk>/edit/`, `/expenses/<pk>/delete/` | existing | existing | **add** owner/admin check (staff loses these) | CHANGE §1.2 |

All new POST endpoints follow the established HTMX fragment convention (`hx-post`, `hx-target="#modal-container"`, `hx-target-4*`) so no JS framework is introduced.

### 4.3 Model changes (one migration per app, all backward-compatible)

- `buyers.OrderRequest`: `source = CharField(max_length=10, choices=[('portal',…),('staff',…)], default='portal')`
- `suppliers.DeliveryNotice`: `origin = CharField(choices=[('supplier',…),('farm',…)], default='supplier')`, `supplier_note = TextField(blank=True)`
- Transition methods on both models (`allowed_next`, `mark_converted()`, …).
- Existing rows default to the current behavior (`portal`/`supplier`) — no data migration needed.

### 4.4 Context processor & performance

`queue_context` runs 3 COUNTs on **every** internal request. Keep it (counts are tiny here) but: (a) wrap in `@lru_cache`-free `cached_per_request` pattern or simply compute lazily via `django.core.cache` with 60s timeout keyed by nothing (global counts); (b) return `open_order_requests` etc. as ints and let templates decide badge rendering (needed for §2.3 always-visible links). Do not move badge logic into per-page views — the sidebar is the product surface for them.

### 4.5 API (`/api/v2/`) alignment

Mirror the same seams so the mobile/portal API can't do what the web can't: add `source`/`origin` to the v2 serializers (write-restricted: `origin=farm` only via internal endpoints), expose `POST /api/v2/portal/delivery-notices/<id>/cancel/`, and reuse the model transition methods there too (single source of truth for the status machine).

### 4.6 Rollout order & testing

1. **PR-1 (security):** `internal_only` + decorator sweep across internal views + `create_portal_account` guard + deactivation double-flag fix. Pure decorators — zero template churn; run existing 64 tests.
2. **PR-2 (sidebar):** regrouping + always-visible queue links + `url_name` active logic (templates only; per project memory: `npm run build` if new utilities, restart server after template edits).
3. **PR-3 (sales funnel):** `source` field, on-behalf view, convert extraction, credit-limit check + tests per permission-matrix row (pattern already established in `buyers/tests.py`).
4. **PR-4 (procurement):** `origin`/`supplier_note`, farm-order view, supplier cancel, notification points + tests.
5. **PR-5 (custody):** password reset, owner/admin edit gates on financial records, ActivityLog diffs.

Each PR lands with the permission matrix rows it touches encoded as role×capability tests — the §1.3/§1.2 tables are directly translatable, matching the plan's original testing intent.

---

## 5. Summary of Recommendations

| # | Recommendation | Why |
|---|---|---|
| 1 | Implement and apply `@internal_only` everywhere; middleware is containment, not authorization | Closes the plan's §1.4 gap; only 2 views today use a role decorator |
| 2 | Split staff/owner/admin capability tiers (financial corrections, deactivation, credit limits → owner/admin) | Current matrix treats all internal users identically |
| 3 | Regroup sidebar into Sales & Orders / Procurement & Inventory / Partners; always-visible queue links with badges | Matches how work actually flows; removes disappearing-link confusion |
| 4 | Unify sales through `OrderRequest` with staff-created (`source=staff`) requests and an explicit convert step | Phone orders get the same audit trail as portal orders |
| 5 | PO-lite: `DeliveryNotice.origin=farm` for admin-initiated supplier orders + supplier cancel | Farm can proactively order without a new model; reuses the entire receive→expense pipeline |
| 6 | Enforce `Buyer.credit_limit` at conversion with owner/admin override | Field exists but is inert; protects receivables |
| 7 | Centralize status machines as model methods shared by web + `/api/v2/` | One transition rule, two transports |
| 8 | Admin/owner password reset for external users | Plan §3.6 v1 promised it; not yet built |
