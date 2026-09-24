# Poultry Farm Record and Inventory Management System

**Development of a Web-Based Poultry Farm Record and Inventory Management System for Chicken Farms in Tambulig, Zamboanga del Sur.**

## Technology Stack

- **Backend:** Django 6.0 with Python 3.13 using `uv` package manager
- **Frontend:** Django Templates
- **CSS Framework:** Tailwind CSS 4 (local)
- **Interactivity:** HTMX and Alpine.js (local)
- **Database:** SQLite (development)
- **Offline-friendly:** All assets stored locally

## Features

- Authentication and User Management (Admin, Farm Owner, Staff roles)
- Dashboard with summary cards and charts
- Chicken Flock Management
- Inventory Management with low-stock alerts
- Feeding Record Module
- Medicine and Vaccination Records
- Egg Production Tracking
- Mortality and Health Monitoring
- Sales Management
- Expense Management
- Supplier and Buyer Management
- Reports and Analytics
- Notification and Alert System
- Settings Module

## Installation Guide

### Prerequisites

- Python 3.13 or higher
- `uv` package manager (install from https://docs.astral.sh/uv/)

### Setup Instructions

1. **Clone or navigate to the project directory:**
   ```bash
   cd C:\Users\gerla\2026\farm
   ```

2. **Install dependencies with uv:**
   ```bash
   uv sync
   ```

3. **Run database migrations:**
   ```bash
   uv run python manage.py migrate
   ```

4. **Seed the database with sample data:**
   ```bash
   uv run python manage.py seed_data
   ```

5. **Create a superuser (optional):**
   ```bash
   uv run python manage.py createsuperuser
   ```

6. **Run the development server:**
   ```bash
   uv run python manage.py runserver
   ```

7. **Access the application:**
   - Main App: http://127.0.0.1:8000/
   - Admin Panel: http://127.0.0.1:8000/admin/

### Sample Login Credentials

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | Administrator |
| owner | owner123 | Farm Owner |
| staff | staff123 | Staff/Caretaker |

## Project Structure

```
farm/
├── accounts/           # User management and authentication
├── buyers/            # Buyer/customer management
├── config/            # Django project settings
├── dashboard/         # Dashboard and farm profile
├── eggs/              # Egg production records
├── expenses/          # Expense tracking
├── feeding/           # Feeding records
├── flocks/            # Chicken flock management
├── inventory/         # Inventory management
├── medicine/          # Medicine and vaccination records
├── mortality/         # Mortality records
├── notifications/     # Notifications and activity logs
├── reports/           # Reports and analytics
├── sales/             # Sales records
├── settings_app/      # System settings
├── suppliers/         # Supplier management
├── static/            # Static files (CSS, JS, images)
├── templates/         # HTML templates
└── manage.py
```

## Database Models

- User (with roles: Admin, Owner, Staff)
- FarmProfile
- FlockBatch
- InventoryItem, InventoryCategory, Unit, InventoryTransaction
- FeedingRecord
- MedicineRecord
- EggProduction
- MortalityRecord
- SalesRecord
- ExpenseRecord, ExpenseCategory
- Supplier
- Buyer
- Notification
- ActivityLog
- SystemSetting

## Development

### Sharing on Your Local Network (Wi-Fi / LAN)

Want other computers and mobile phones on the same Wi-Fi to open the app and
API? Use the one-click share launcher — it auto-detects this machine's local
IP, copies the share URL to your clipboard, and serves the app to the network.

1. **First time only (if devices can't connect):** double-click
   `Allow Network Access (once).bat` and accept the admin prompt. This opens
   Windows Firewall for ports 8000-8010.
2. **Start sharing:** double-click `Share Farm App.bat` (or run
   `uv run python share_server.py`). To use another port, pass it as an
   argument, e.g. `uv run python share_server.py 8080`.
3. **Open on other devices** (must be on the same Wi-Fi/LAN), using the IP the
   launcher prints:
   - Other computers / phones (app): `http://<your-lan-ip>:8000/`
   - API from any device: `http://<your-lan-ip>:8000/api/`

The launcher prints the exact addresses and copies the app URL to your
clipboard so you can paste and send it. Close the window (or press Ctrl+C) to
stop sharing.

### Running Tests
```bash
uv run python manage.py test
```

### Collecting Static Files
```bash
uv run python manage.py collectstatic
```

## License

This system is developed for educational purposes for chicken farms in Tambulig, Zamboanga del Sur.
 npx @tailwindcss/cli -i src/input.css -o static/css/styles.css --minify 2>&1
 