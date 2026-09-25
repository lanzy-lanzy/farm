# Buyer & Supplier Account Management — Implementation Plan

**Project:** Tambulig Poultry Farm Management System (Django 5.x)
**Status:** v1 implemented (2026-09-23) — self-service registration (§3.1 Path B), SMTP password reset (§3.6 v2) and email-verification remain Phase 2
**Scope:** Give existing `buyers.Buyer` and `suppliers.Supplier` records real, verifiable login accounts; define what those accounts can do; and add the transaction-initiation workflow between them and the farm.

---

## 0. Current State (Baseline)

| Area | Today |
|---|---|
| Auth | Custom `accounts.User(AbstractUser)` with roles `admin`, `owner`, `staff` (`AUTH_USER_MODEL = "accounts.User"`) |
| Buyers | `buyers.Buyer` — plain contact record (name, phone, email, `buyer_type`, `is_active`), created only by farm staff |
| Suppliers | `suppliers.Supplier` — same pattern, plus a free-text `supplies` field |
| Transactions | One-directional FKs: `sales.SalesRecord.buyer`, `inventory.InventoryItem.supplier`, `expenses.ExpenseRecord.supplier`. All recorded *by staff*, never by the external party |
| Web UI | Server-rendered templates, HTMX fragment modals (`_form.html`, `_delete.html`), crispy-tailwind forms |
| REST API | `api/` app is **intentionally read-only** for the owner's mobile app (`IsOwner` permission rejects all non-GET) |

**Key design constraint:** the farm system is the source of truth. Buyers/suppliers get *accounts attached to their existing records*, not parallel identities. Staff remain the ones who confirm money-moving records.

---

## 1. User Roles & Permissions

### 1.1 Role model

Extend `accounts.User.ROLE_CHOICES` with two external roles:

```python
ROLE_CHOICES = [
    ("admin",   "Administrator"),
    ("owner",   "Farm Owner"),
    ("staff",   "Staff/Caretaker"),
    ("buyer",   "Buyer"),        # NEW — external
    ("supplier","Supplier"),     # NEW — external
]
```

Add convenience helpers on `User`:

```python
def is_external(self):        # buyer or supplier
def is_internal(self):        # admin / owner / staff
```

### 1.2 Account linkage

Each external `User` is linked **1:1** to exactly one `Buyer` or `Supplier` row (`OneToOneField`, `related_name="user"`). The link is the authorization boundary: a buyer only ever sees data reachable through their own `Buyer` FK.

### 1.3 Permission matrix

| Capability | admin | owner | staff | buyer (ext.) | supplier (ext.) |
|---|:-:|:-:|:-:|:-:|:-:|
| Dashboard / farm records (existing apps) | ✅ | ✅ | ✅ | ❌ | ❌ |
| CRUD Buyer/Supplier contact records | ✅ | ✅ | ✅ | ❌ (own profile only) | ❌ (own profile only) |
| View own profile | ✅ | ✅ | ✅ | ✅ | ✅ |
| Edit own contact info (name/phone/address/logo) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Change own password | ✅ | ✅ | ✅ | ✅ | ✅ |
| View own **sales history** (order status, totals, balance) | ✅ | ✅ | ✅ | ✅ (own only) | ❌ |
| Submit **purchase requests** (want to buy eggs/chicken) | ❌ n/a | ❌ n/a | ❌ n/a | ✅ | ❌ |
| View own **supply/purchase-history** (what farm bought) | ❌ | ❌ | ❌ | ❌ | ✅ (own only) |
| Maintain **product catalog** (what they supply, prices) | ❌ | ❌ | ❌ | ❌ | ✅ (own only) |
| Submit **delivery/offer notices** | ❌ | ❌ | ❌ | ❌ | ✅ |
| Approve/convert requests → official `SalesRecord` / `ExpenseRecord` | ✅ | ✅ | ✅ | ❌ | ❌ |
| Verify (activate) external accounts, reset their passwords | ✅ | ✅ | ❌ | ❌ | ❌ |
| Deactivate external account/link | ✅ | ✅ | ✅ (propose) | ❌ | ❌ |

**Rules:**
1. External users are redirected to their own portal (`/portal/…`), never the farm dashboard/sidebar.
2. Every external queryset is filtered by `request.user.buyer` / `request.user.supplier` at the view layer — never trust a client-supplied ID for the party identity.
3. Only staff+ can create the *financial* truth (`SalesRecord`, `ExpenseRecord`). Buyer requests are pre-records (`OrderRequest`) with their own status lifecycle.
4. Verification (activate) is admin/owner only — staff can create accounts for walk-in buyers but cannot self-approve.

### 1.4 Access-level enforcement (implementation)

New decorators/mixins in `accounts/access.py` (shared by web + API):

- `internal_only` — existing behavior, guards current views.
- `external_portal_required(role)` — asserts `login_required`, role matches, and verification is approved; otherwise 403 / redirect to a "pending verification" page.
- DRF classes: `IsInternalUser`, `IsVerifiedBuyer`, `IsVerifiedSupplier`, `IsInternalOrVerifiedParty`.

---

## 2. Data Models

### 2.1 Changes to existing models

**`accounts.User`**
- `role`: add `buyer` / `supplier` choices (no schema change; choices only).

**`buyers.Buyer`** (all new fields nullable/defaulted → backward compatible with the ~existing rows)

| Field | Type | Purpose |
|---|---|---|
| `user` | `OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name="buyer_profile")` | account linkage |
| `verification_status` | `CharField choices [pending, approved, rejected] default pending` | existing rows stay `pending` until an admin reviews them |
| `verified_by` / `verified_at` | `FK(User, null=True)` / `DateTimeField(null=True)` | audit |
| `rejection_reason` | `TextField blank` | feedback to applicant |
| `credit_limit` | `DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)` | optional; caps pending/unpaid balance |

**`suppliers.Supplier`** — same five fields minus `credit_limit`, plus:
| Field | Type | Purpose |
|---|---|---|
| `payment_terms` | `CharField choices [cod, net15, net30] default cod` | used when converting delivery → expense |
| `dti_registration` | `CharField max_length=50 blank` | optional business credential for verification |

> Migration note: `verification_status` for rows that already exist and are actively referenced by sales/expenses can be bulk-set to `approved` in the data migration — contact records the farm already trades with are implicitly verified.

### 2.2 New models

**`buyers.OrderRequest`** — buyer-initiated purchase request (pre-SalesRecord):

| Field | Type / notes |
|---|---|
| `request_number` | `CharField unique` e.g. `REQ-2026-0001` (generated in `save()`) |
| `buyer` | `FK(Buyer, related_name="order_requests")` |
| `product_type` | reuse `SalesRecord.PRODUCT_CHOICES` (eggs / chicken / dressed / manure / other) |
| `product_name` | `CharField` |
| `quantity`, `requested_unit_price` | `DecimalField` (price optional — farm may quote) |
| `requested_date` | `DateField` |
| `status` | `[submitted, under_review, quoted, accepted, rejected, converted, cancelled]` |
| `quoted_unit_price`, `staff_note` | set by staff during review |
| `sales_record` | `OneToOne(SalesRecord, null=True, blank=True)` — set on conversion; the audit link |
| `created_by` | FK User (buyer's own user, or staff creating on their behalf) |
| `created_at`, `updated_at` | timestamps |

**`suppliers.SupplyItem`** — structured catalog replacing free-text `Supplier.supplies` (keep `supplies` as legacy display until migrated):

| Field | notes |
|---|---|
| `supplier` | `FK(Supplier, related_name="supply_items")` |
| `name`, `category` | e.g. "Layer feeds 50kg"; align category with `inventory` categories where sensible |
| `unit_price`, `unit` | `FK` to existing `inventory.Unit` |
| `availability` | `[in_stock, made_to_order, seasonal]` |
| `inventory_item` | `FK(inventory.InventoryItem, null=True)` — stock row this item adds to on receive; mapped by staff (Django admin), never editable by the supplier |
| `is_active`, `updated_at` | |

**`suppliers.DeliveryNotice`** — supplier-initiated "goods on the way" notice:

| Field | notes |
|---|---|
| `supplier` | FK |
| `supply_item` | FK (nullable — ad-hoc orders and supplier notices use free-text `description` only) |
| `inventory_item` | `FK(InventoryItem, null=True)` — permanent stock row this delivery was booked into, decided at receive; overrides the `SupplyItem.inventory_item` default |
| `description`, `quantity`, `expected_date` | |
| `status` | `[announced, received, rejected]` |
| `expense_record` | `OneToOne(ExpenseRecord, null=True)` — set when staff books the purchase |
| `received_by` | FK User, null |

**`accounts.VerificationEvent`** *(optional, nice-to-have)* — log of status transitions on the Buyer/Supplier link (who, from → to, reason). Skip in v1; `notifications.log_activity` already covers basic audit.

### 2.3 ER summary

```
User(role=buyer)     1──1 Buyer 1──* OrderRequest *──1 SalesRecord
User(role=supplier)  1──1 Supplier 1──* SupplyItem *──1 InventoryItem (optional stock mapping)
                             Supplier 1──* DeliveryNotice *──1 ExpenseRecord
InventoryItem.sales_product_type (optional, unique) ← sales of that product deduct this item
```

---

## 3. Workflow Logic

### 3.1 Account registration (two entry paths)

**Path A — Staff creates on behalf (walk-in / phone buyer):**
1. Staff creates/opens the `Buyer` (or `Supplier`) record as today (HTMX modal).
2. Staff clicks **"Create account"** → fills email + phone → system generates a `User` with `role=buyer`, `verification_status=pending`, and a random password.
3. Staff sends credentials out-of-band (SMS/email is a stub; farm coordinates locally). Record auto-set to `approved` because staff vouches for it (`verified_by=staff user`).

**Path B — Self-service request (greenfield, later phase):**
1. Visitor submits `/register/buyer/` or `/register/supplier/` form (name, business name, phone, email, password, `supplies` or product interest).
2. System creates `Buyer`/`Supplier` (`pending`) + `User` (`is_active=False`, role set, **no farm data access while inactive**).
3. Admin/owner sees pending items on a **Verification Queue** page (also surfaced via existing `notifications` app).
4. Admin **approves** (flips `verification_status=approved`, `user.is_active=True`, logs `log_activity`) or **rejects** (reason stored; user stays inactive).
5. Approved user logs in → lands on external portal.

**Login routing:** in `accounts` login view, after auth: `role in (admin, owner, staff)` → `dashboard:index`; external roles → `portal:home`. External users must never reach internal sidebar templates — enforced by a base-template switch (`base_internal.html` vs `base_portal.html`) plus the decorators in §1.4.

### 3.2 Verification / re-verification rules

- Email + phone must be non-blank on the contact record before approval.
- One linked `User` per contact record; unique constraint prevents duplicates.
- Deactivating a `Buyer.is_active` also sets its linked `user.is_active=False` (signal or override in `save()`), instantly revoking login.
- Admin can reset an external user's password ( Django admin or a portal-admin action) → generates temp password, forces change on next login (`User.last_login` + a flag or simply `is_superuser`-style `must_change_password` field on the contact model).

### 3.3 Profile management (external user)

- Editable: contact person, phone, address, (buyer: notes→none; supplier: `supplies`/catalog).
- Read-only to external user: `verification_status`, farm-side notes, `created_by`, credit limit.
- Name change on the profile writes through to the linked `Buyer.name`/`Supplier.name` (single source of truth).

### 3.4 Transaction initiation — Buyer → Farm (sales)

```
submitted → under_review → quoted → accepted → converted
                    ↘ rejected            ↘ cancelled (by buyer, any time before accepted)
```

1. **Buyer** submits `OrderRequest` from portal (product, qty, desired date, optional target price).
2. **Staff** sees it on the Sales page as a badge/list (`OrderRequest.status=submitted`), moves to `under_review`, optionally sets `quoted_unit_price` → status `quoted`.
3. **Buyer** reviews quote in portal → `accepted` (commit) or `rejected`.
4. **Staff** clicks **"Record sale"** on the accepted request: prefills the existing `SalesRecord` form with product/qty/price/buyer. Saving the `SalesRecord` sets `OrderRequest.sales_record` and status `converted`. Payment status remains managed entirely inside `SalesRecord` as today.
5. **Inventory deduction:** if an active `InventoryItem` carries `sales_product_type` matching the sold product, conversion (and direct `SalesRecord` creation) books an `"out"` `InventoryTransaction` (`reference="Sales Record #<pk>"`) via `inventory.services.deduct_for_sale` inside one `transaction.atomic`, then runs the low-stock check. Selling more than the mapped stock is refused for every role (product types without a mapped item, e.g. fresh eggs, are simply untracked).
6. Notifications: reuse `notifications` app to ping staff on `submitted`, buyer on `quoted`/`converted`.
7. Fallback: staff can still record a `SalesRecord` directly without any request (walk-in cash sale) — the request flow is additive, not mandatory.

### 3.5 Transaction initiation — Supplier → Farm (purchases)

1. **Supplier** maintains `SupplyItem` catalog (price, availability).
2. **Supplier** files a `DeliveryNotice` (what, how much, expected date).
3. **Staff** reviews on the Expenses/Inventory side: on arrival, records the existing `ExpenseRecord` and links `DeliveryNotice.expense_record`, status `received` — in one `transaction.atomic`. Stock booking is resolved in order: explicit `DeliveryNotice.inventory_item` chosen at receive (the modal's "Stock booking" block: pick an existing item **or** create a new one with name/unit/category — duplicate names are refused and point at the existing row) → the mapped `SupplyItem.inventory_item` → no stock movement. Booked quantities create an `"in"` `InventoryTransaction` (`reference="Delivery Notice #<pk>"`) via `inventory.services.receive_for_notice`; unmapped deliveries change nothing in stock.
3b. **Ad-hoc orders** (no catalog row): `FarmDeliveryOrderForm` accepts a blank `supply_item` with a free-text `description`; no temporary `SupplyItem` is ever created, so supplier catalogs and `InventoryItem` names stay clean. The permanent stock row is decided only at receive.
4. `payment_terms` on the Supplier pre-fills `ExpenseRecord.payment_status`.
5. Staff may also file orders to suppliers directly (current behavior); notices are supplier-initiated only.

### 3.6 Password reset (external users)

- v1: farm admin issues temp password (matches local-farm reality; no SMTP dependency).
- v2: wire Django `password_reset` with email backend once SMTP is configured (`config/settings.py` has none today).

---

## 4. API & View Requirements

### 4.1 Session-based web views (existing apps, HTMX pattern)

**`buyers/`**
| Route | View | Notes |
|---|---|---|
| `buyers/<pk>/account/create/` | `buyer_create_account` | staff/admin; POST only; form: email, optional name |
| `buyers/<pk>/account/deactivate/` | `buyer_deactivate_account` | flips user + buyer active flags |
| **new `portal/buyer/` namespace** | `buyer_home`, `order_request_list/create/detail/respond/cancel`, `buyer_profile`, `buyer_profile_update`, `password_change` | guarded by `external_portal_required("buyer")`; list/detail querysets filtered by `request.user.buyer`; create/detail/cancel/respond/update all answer HTMX with dialog partials and plain GETs with pages |
| **new `orders/` internal views** (can live in `sales/`) | `order_request_queue`, `order_request_review` (quote/reject), `order_request_convert` (prefill SalesRecord form) | staff+ only |

**`suppliers/`**
| Route | View |
|---|---|
| `suppliers/<pk>/account/create/`, `.../deactivate/` | same pattern as buyers |
| `portal/supplier/` | `supplier_home`, `catalog_list/create/detail/update/delete`, `delivery_notice_list/create/respond/cancel`, `purchase_history`, `supplier_profile`, `supplier_profile_update` — every mutation is a dialog partial under HTMX, with a plain-page fallback |
| internal | `delivery_notice_queue` (staff: mark received/rejected → link expense) |

**`accounts/`**
- `register/buyer/`, `register/supplier/` (Phase 2; self-service)
- `verify/queue/` — admin/owner pending-verification list with approve/reject POSTs
- Login view: add role-based redirect (§3.1)
- Forms: `OrderRequestForm`, `SupplyItemForm`, `DeliveryNoticeForm`, `BuyerProfileForm`/`SupplierProfileForm` (restricted field sets), `CreateAccountForm`

**Template list:** `portal/base.html`, `portal/buyer/*.html`, `portal/supplier/*.html`, `sales/order_request_queue.html`, `expenses/delivery_notice_queue.html`, `accounts/verify_queue.html`, `accounts/register_form.html` — all extending portal/base with the existing sidebar pattern.

### 4.2 DRF API (`api/` app)

The monitoring API stays read-only and owner-scoped. **Add a separate, explicitly-namespaced write-capable surface** so the two policies never mix:

**New permission classes (`api/permissions.py`):**
```python
class IsInternalUser(SafeMethod)          # existing staff/owner/admin; GET everything they can see on web
class IsVerifiedPartyAndScoped(BasePermission)  # buyer/supplier: CRUD only objects whose .buyer/.supplier == their profile
```

**New serializers (`api/serializers.py`):**
- `BuyerProfileSerializer` / `SupplierProfileSerializer` (subset: name, phone, address, verification_status read-only)
- `OrderRequestSerializer` (status/quoted fields `read_only` for buyers; `write` via staff endpoints only)
- `SupplyItemSerializer`, `DeliveryNoticeSerializer`
- `OrderReviewSerializer` (staff: status transition + quoted price + note)

**New routes (`api/urls.py`, router or plain `SimpleRouter` under `/api/v2/`):**

| Endpoint | Methods | Actor |
|---|---|---|
| `POST /api/v2/auth/register/buyer/` (+supplier) | POST | anonymous (Phase 2) |
| `GET/PATCH /api/v2/portal/profile/` | GET, PATCH | external party |
| `GET/POST /api/v2/portal/order-requests/`, `GET /{id}/`, `POST /{id}/cancel/` | as noted | buyer |
| `GET /api/v2/portal/sales-history/` | GET (read of own SalesRecord) | buyer |
| `GET/POST/PATCH/DELETE /api/v2/portal/supply-items/` | CRUD own | supplier |
| `GET/POST /api/v2/portal/delivery-notices/` | GET, POST | supplier |
| `GET /api/v2/portal/purchase-history/` | GET | supplier |
| `GET /api/v2/internal/order-requests/?status=`, `POST .../{id}/quote/`, `POST .../{id}/reject/`, `POST .../{id}/convert/` | as noted | staff |
| `GET/POST /api/v2/internal/delivery-notices/` (queue + farm orders), `POST .../{id}/receive/`, `POST .../{id}/reject/` | as noted | staff |
| `POST /api/v2/internal/verifications/{buyer\|supplier}/{id}/approve\|reject/` | POST | admin/owner |
| `GET /api/v2/internal/verifications/pending/` | GET | admin/owner |
| `GET /api/v2/internal/options/` | GET | staff |

Receive note: `POST .../delivery-notices/{id}/receive/` accepts the expense payload plus an optional
`inventory_item` PK to book the delivered quantity into a specific stock row (ad-hoc deliveries with no
catalog mapping); the stock booking and the expense/notice updates run in one transaction.

**API conventions to follow (already established in `api/`):**
- Token + Session auth both accepted; pagination `PAGE_SIZE=50`.
- Every tabular list (web views, portal, API v1/v2) is newest-first: chronological models order by
  their date/`created_at` field descending (DeliveryNotice by `-created_at` since 2026-09-25);
  lookup catalogs (inventory items, suppliers, buyers, units) stay alphabetical; deliberate
  exceptions: notifications put unread first (newest within each group), upcoming medicine
  schedules and low-stock lists lead with the most urgent.
- `obtain_auth_token` reused for portal login; registration returns 201 without token until verified (`is_active=False` → DRF `TokenAuthentication` already rejects inactive users — verify + rely on that).
- Status transitions validated in serializer `validate_status` / model methods, not in views.
- Never expose farm-internal fields (notes, `created_by` of other records, other buyers) — per-serializer field whitelists, `get_queryset()` filter for every list/detail.

### 4.3 Migrations & rollout order

1. `000x_account_roles_and_linkage` — role choices + `user` FK + verification fields (nullable) on Buyer/Supplier.
2. Data migration: bulk-approve existing traded records (§2.1 note).
3. `OrderRequest`, `SupplyItem`, `DeliveryNotice` models.
4. Accounts/portal views + decorators → internal queue views → notifications wiring.
5. `/api/v2/` endpoints (portal first, internal review endpoints second).
6. Tests: `buyers/tests.py` & `suppliers/tests.py` — permission matrix rows from §1.3 as unit tests (each role × each capability), plus status-machine transition tests.

---

## 5. UI/UX Considerations

### 5.1 Two visual shells
- **Internal shell:** unchanged dashboard/sidebar look.
- **Portal shell (`portal/base.html`):** a *partner* sidebar — same forest-glass rail as the internal shell, but tinted per role (buyer = cyan, supplier = emerald) and containing only that role's own screens. No farm KPIs, no farm records, no admin entry points. The header still names the space clearly ("Buyer Portal — Tambulig Poultry").
  - Nav items live in `portal/_nav_links.html` (grouped, with active state); the sidebar also carries the account-verification chip, one primary CTA ("New Order Request" / "Announce Delivery"), and Change Password + Logout.
  - `config.context_processors.portal_context` supplies `portal_partner` plus the "needs your response" badges (buyer: `status=quoted` requests; supplier: `origin=farm, status=announced` notices).
  - Below `lg` the rail becomes an off-canvas drawer toggled by the hamburger. Portal pages are light-mode only.
  - *History:* this replaces the original simplified top-nav design; the top-nav was dropped because partners needed the same one-glance access to their queue that internal staff have.

### 5.2 Buyer portal screens
- **Home (`portal/buyer/home.html`):** hero with verification + buyer-type chips and the two entry CTAs (the create CTA opens the dialog); four stat cards (outstanding balance, open requests, *needs your response*, requests on record); a **"Quotes waiting for you"** panel listing `status=quoted` requests with the quoted line total, staff note, expiry pill and inline Accept/Decline; recent requests + recent purchases panels; and a "How an order request moves" stepper explainer.
- **New order request:** HTMX dialog (`_request_form.html`) opened from the sidebar CTA, the nav, the hero and the list header. `portal:buyer_request_create` serves the partial to `HX-Request` GETs and the standalone `request_form.html` page otherwise, so the flow still works with JavaScript off. Fields: product type chips → product name, quantity with unit hint, desired date picker.
- **My requests:** responsive table (Request / Product / Qty / Needed By / Status / Actions). Every row action is a dialog: the request number and the eye icon open `_request_detail.html`, `Respond` appears only on quotable rows, and the red X opens `_request_cancel.html`. Accept/Decline are HTMX posts carrying a hidden `action` input; they close the dialog and reload so the flash message is visible. `portal:buyer_request_detail` also renders a full page (`request_detail.html`) for notification deep links and no-JS use.
- **Profile:** read-only contact card, four stat cards (verification, outstanding balance, credit limit, member since) and an account-settings panel. "Edit My Details" opens `_profile_form.html`, posted to `portal:buyer_profile_update`.

### 5.3 Supplier portal screens
- **Home (`portal/supplier/home.html`):** hero with payment-terms / verification / supplies chips; four stat cards (catalog items incl. hidden count, open deliveries, *needs your confirmation*, purchases this month); a **"Farm orders waiting for you"** panel whose date + note form posts by HTMX to `portal:supplier_delivery_respond` (quick action, no page leave); recent delivery notices and a catalog snapshot panel; and a "How deliveries work" explainer covering both notice origins.
- **Catalog:** one page (`catalog_list.html`) hosting the full CRUD — table rows open detail / edit / remove dialogs, and `?add=1` / `?edit=<pk>` deep links land on the page and open the dialog once Alpine has booted.
- **Deliveries:** responsive notice table (Delivery / Source / Quantity / Expected / Status / Actions). Announce opens `_delivery_form.html`, a farm order opens `_delivery_respond.html` to confirm or move the date, and an own announcement opens `_delivery_cancel.html` with an optional reason. Rows the supplier can no longer act on read "Closed". `delivery_form.html` remains the no-JS fallback page.
- **My Business:** read-only details + stats (verification, payment terms, active listings, deliveries received) with the edit form in `_profile_form.html` → `portal:supplier_profile_update`.
- **Purchase history:** responsive table of farm purchases from them with a month filter and total cards.

### 5.5 Cross-cutting
- **Modal contract (both portals):** trigger carries `hx-get`/`hx-post` + `hx-target="#modal-container" hx-swap="innerHTML"`; the partial extends `partials/modal.html` (overlay, Escape and click-away close); invalid submissions return 200 and re-render the partial with field errors; success returns `config.htmx.modal_closed()` — a guarded script that removes `#modal-overlay` if one is open and reloads, which is what lets the same view answer dashboard posts that have no dialog. `is_htmx(request)` picks partial vs. page. No response-targets extension, no new JS framework.
- `#modal-container` sits at `z-index: 70` so dialogs clear the `z-60` off-canvas drawer on phones.
- **Responsive kit:** tables are `.panel.overflow-hidden > .overflow-x-auto > table.w-full.min-w-[..]`, secondary columns collapse with `hidden md:table-cell` / `lg:table-cell`, stat grids are `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`, and `.row--stack` stacks list rows (full-width buttons) below `sm`.
- **Notifications:** portal rows link through `notifications:notification_mark_read`, which flips `is_read` and redirects to `notification.link`, so one click marks the item read and lands the partner on the page that acts on it (a quote goes to the request detail, where Accept/Decline are in the action band). Follow-up, not done: supplier delivery notices still link to the deliveries list rather than the individual notice, because the per-row `target` value belongs to work in flight elsewhere.
- **Tailwind caveat (project-known):** `styles.css` is precompiled Tailwind; any new utility classes require `npm run build`. Prefer existing classes or a small custom `<style>` block for new components (steppers, pills).
- Money display: `₱` with 2 decimals everywhere; balance figures right-aligned; unpaid/pending in amber, converted/received in green.
- Empty states matter: brand-new buyer with no orders should see guidance ("Your first step: request eggs or chicken"), not a blank table.
- Mobile: portal pages must work on phone browsers — this is the primary device for buyers/suppliers (the owner has the separate KMP app; the portal does not need a native client).

---

## 6. Out of scope (v1) — flagged for later

- Self-service registration with email verification links (needs SMTP).
- Online payment / GCash integration against `SalesRecord.balance()`.
- Multi-contact users (one person being both buyer and supplier) — v1 keeps 1 user : 1 role : 1 profile.
- Stock visibility to buyers (e.g., "eggs available today") — requires an inventory-publication decision.
