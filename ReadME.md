Create a complete web-based application titled:

**“Development of a Web-Based Poultry Farm Record and Inventory Management System for Chicken Farms in Tambulig, Zamboanga del Sur.”**

The system must be designed for poultry farm owners, caretakers, and farm administrators to help them manage chicken farm records, inventory, expenses, production, sales, and reports in an organized and efficient way.

Use the following technology stack:

* **Backend:** Django using Python with `uv` package manager
* **Frontend:** Django Templates
* **CSS Framework:** Tailwind CSS 4
* **Interactivity:** HTMX and Alpine.js
* **Database:** SQLite for development, with option to switch to PostgreSQL for production
* **Offline-friendly:** No CDN. All CSS, JavaScript, icons, and dependencies must be installed locally or stored in the static files.
* **Design:** Responsive, mobile-friendly, clean dashboard layout with sidebar navigation, cards, tables, filters, charts, and dark mode support.

The system must include the following modules:

1. **Authentication and User Management**

   * Login and logout
   * Role-based access control
   * Admin, Farm Owner, Staff/Caretaker roles
   * User profile management

2. **Dashboard Module**

   * Total number of chickens
   * Available feeds
   * Medicine inventory
   * Egg production summary
   * Mortality count
   * Sales summary
   * Expenses summary
   * Low-stock alerts
   * Recent farm activities

3. **Chicken Flock Management**

   * Add, edit, delete, and view flock records
   * Record batch number, breed, quantity, age, source, date acquired, and status
   * Track growing stage such as chick, grower, layer, or broiler
   * Track mortality, sold chickens, and remaining stock

4. **Inventory Management**

   * Manage feeds, medicines, vaccines, vitamins, equipment, and other farm supplies
   * Record item name, category, quantity, unit, supplier, date purchased, expiration date, and cost
   * Automatic stock deduction when feeds, medicines, or supplies are used
   * Low-stock and expired-item notifications

5. **Feeding Record Module**

   * Record daily feeding schedules
   * Track feed type, quantity used, flock/batch served, and staff responsible
   * Generate feeding history per flock
   * Deduct feed usage automatically from inventory

6. **Medicine and Vaccination Record Module**

   * Record medicine usage, vaccination schedules, and treatment history
   * Track date administered, medicine/vaccine name, dosage, flock/batch, remarks, and person in charge
   * Deduct medicine or vaccine quantity from inventory
   * Notify users for upcoming vaccination schedules

7. **Egg Production Record Module**

   * Record daily egg production
   * Track good eggs, cracked eggs, rejected eggs, and total eggs collected
   * Filter production records by date, flock, or batch
   * Generate weekly and monthly egg production reports

8. **Mortality and Health Monitoring Module**

   * Record dead chickens per flock or batch
   * Add possible cause of death, symptoms, remarks, and action taken
   * Track mortality rate
   * Generate health monitoring reports

9. **Sales Management Module**

   * Record sales of eggs, chickens, manure, or other farm products
   * Track buyer name, product type, quantity, unit price, total amount, date sold, and payment status
   * Generate sales reports
   * Print or export sales records

10. **Expense Management Module**

* Record farm expenses such as feeds, medicine, labor, transportation, utilities, and maintenance
* Track date, category, description, amount, and payment method
* Generate expense summary and profit/loss report

11. **Supplier and Buyer Management**

* Manage supplier records
* Manage buyer/customer records
* Store contact details, address, transaction history, and remarks

12. **Reports and Analytics**

* Daily, weekly, monthly, and yearly reports
* Inventory report
* Production report
* Mortality report
* Sales report
* Expense report
* Profit and loss report
* Printable reports and export to PDF/Excel

13. **Notification and Alert System**

* Low-stock alerts
* Expired medicine/vaccine alerts
* Upcoming vaccination reminders
* High mortality warning
* Recent activity notifications

14. **Settings Module**

* Farm profile settings
* System backup and restore
* Theme settings
* User role permissions
* Farm categories and inventory units management

The application must have the following pages:

* Login Page
* Main Dashboard
* Flock Management Page
* Inventory Page
* Feeding Records Page
* Medicine and Vaccination Page
* Egg Production Page
* Mortality Records Page
* Sales Page
* Expenses Page
* Suppliers Page
* Buyers Page
* Reports Page
* User Management Page
* Settings Page

UI/UX requirements:

* Use a clean agricultural/farm-inspired color palette.
* Use modern dashboard cards with icons.
* Use responsive tables with search, filters, pagination, and action buttons.
* Use modal forms with HTMX where appropriate.
* Use Alpine.js for dropdowns, sidebar toggles, dark mode, and interactive UI components.
* Use toast notifications for successful actions, errors, and warnings.
* Use confirmation dialogs before deleting records.
* Make the system easy to use for non-technical poultry farm owners and caretakers.

Database models must include:

* User
* FarmProfile
* FlockBatch
* InventoryItem
* InventoryTransaction
* FeedingRecord
* MedicineRecord
* VaccinationRecord
* EggProduction
* MortalityRecord
* SalesRecord
* ExpenseRecord
* Supplier
* Buyer
* Notification
* ActivityLog

The system must follow good software development practices:

* Use Django class-based or function-based views consistently.
* Use Django forms or ModelForms.
* Use reusable templates and partials.
* Use proper model relationships.
* Use validation for all forms.
* Use role-based permissions.
* Use clean folder structure.
* Use meaningful variable names.
* Include sample seed data.
* Include admin panel configuration.
* Include README setup instructions using `uv`.
* Include steps for installing Tailwind CSS 4 locally without CDN.
* Include HTMX and Alpine.js as local static files.
* Include database migration instructions.
* Include basic testing for important features.

The final output must include:

1. Complete Django project structure
2. Database models
3. Views
4. URLs
5. Forms
6. Templates
7. Static files setup
8. Tailwind CSS 4 setup
9. HTMX and Alpine.js local setup
10. Dashboard UI
11. CRUD modules
12. Reports module
13. Authentication and role-based access
14. README installation guide
15. Sample data for testing

Make the system professional, user-friendly, responsive, and suitable for chicken farms in Tambulig, Zamboanga del Sur.