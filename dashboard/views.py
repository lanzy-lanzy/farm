from accounts.access import internal_only
from django.db import models
from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone

from buyers.models import OrderRequest
from flocks.models import FlockBatch
from inventory.models import InventoryItem
from eggs.models import EggProduction
from deaths.models import DeathRecord
from sales.models import SalesRecord
from expenses.models import ExpenseRecord
from notifications.models import Notification, ActivityLog
from suppliers.models import DeliveryNotice
from .forms import FarmProfileForm
from .models import FarmProfile


@internal_only
def index(request):
    today = timezone.now().date()
    week_ago = today - timezone.timedelta(days=7)
    month_ago = today - timezone.timedelta(days=30)
    is_elevated = request.user.is_admin_user() or request.user.is_owner()

    total_chickens = FlockBatch.objects.filter(status="active").aggregate(
        total=Sum("current_quantity")
    )["total"] or 0

    total_flocks = FlockBatch.objects.filter(status="active").count()

    today_eggs = EggProduction.objects.filter(production_date=today).aggregate(
        total=Sum("total_eggs")
    )["total"] or 0

    week_eggs = EggProduction.objects.filter(
        production_date__gte=week_ago
    ).aggregate(total=Sum("total_eggs"))["total"] or 0

    month_eggs = EggProduction.objects.filter(
        production_date__gte=month_ago
    ).aggregate(total=Sum("total_eggs"))["total"] or 0

    total_mortality = DeathRecord.objects.filter(
        date_recorded__gte=month_ago
    ).aggregate(total=Sum("quantity"))["total"] or 0

    egg_production_chart_data = []
    mortality_chart_data = []
    total_eggs_7d = 0
    for i in range(6, -1, -1):
        date = today - timezone.timedelta(days=i)
        day_eggs = EggProduction.objects.filter(production_date=date).aggregate(
            total=Sum("total_eggs")
        )["total"] or 0
        total_eggs_7d += day_eggs
        egg_production_chart_data.append({"date": date.strftime("%b %d"), "eggs": int(day_eggs)})

        mort_count = DeathRecord.objects.filter(date_recorded=date).aggregate(
            total=Sum("quantity")
        )["total"] or 0
        mortality_chart_data.append({"date": date.strftime("%b %d"), "deaths": mort_count})

    low_stock_items = 0
    expired_items = 0
    week_sales = 0
    month_sales = 0
    week_expenses = 0
    month_expenses = 0
    receivables = 0
    open_requests = 0
    open_deliveries = 0
    trays_sold_chart_data = []
    total_trays_sold_7d = 0

    if is_elevated:
        low_stock_items = InventoryItem.objects.filter(
            is_active=True, quantity__lte=models.F("reorder_level")
        ).count()

        expired_items = InventoryItem.objects.filter(
            is_active=True,
            expiration_date__lte=today,
            expiration_date__isnull=False,
        ).count()

        week_sales = SalesRecord.objects.filter(
            date_sold__gte=week_ago
        ).aggregate(total=Sum("total_amount"))["total"] or 0

        month_sales = SalesRecord.objects.filter(
            date_sold__gte=month_ago
        ).aggregate(total=Sum("total_amount"))["total"] or 0

        week_expenses = ExpenseRecord.objects.filter(
            expense_date__gte=week_ago
        ).aggregate(total=Sum("amount"))["total"] or 0

        month_expenses = ExpenseRecord.objects.filter(
            expense_date__gte=month_ago
        ).aggregate(total=Sum("amount"))["total"] or 0

        receivables = SalesRecord.objects.exclude(payment_status="paid").aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("total_amount") - F("amount_paid"),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            )
        )["total"] or 0

        open_requests = OrderRequest.objects.filter(
            status__in=["submitted", "under_review", "quoted", "accepted"]
        ).count()

        open_deliveries = DeliveryNotice.objects.filter(
            status__in=["announced", "confirmed"]
        ).count()

        for i in range(6, -1, -1):
            date = today - timezone.timedelta(days=i)
            trays_sold = SalesRecord.objects.filter(
                product_type="eggs", date_sold=date
            ).aggregate(total=Sum("quantity"))["total"] or 0
            total_trays_sold_7d += trays_sold
            trays_val = int(trays_sold) if trays_sold == int(trays_sold) else float(trays_sold)
            trays_sold_chart_data.append({"date": date.strftime("%b %d"), "trays": trays_val})

        total_trays_sold_7d = (
            int(total_trays_sold_7d)
            if total_trays_sold_7d == int(total_trays_sold_7d)
            else float(total_trays_sold_7d)
        )

        recent_activities = ActivityLog.objects.all()[:10]
    else:
        recent_activities = ActivityLog.objects.filter(
            model_name__in=[
                "FlockBatch",
                "FeedingRecord",
                "EggProduction",
                "DeathRecord",
                "MedicineRecord",
            ]
        )[:10]

    recent_notifications = Notification.objects.filter(
        user=request.user, is_read=False
    )[:5]

    profile = getattr(request.user, "farm_profile", None)
    farm_name = getattr(profile, "farm_name", "") or "Tambulig Poultry Farm"
    farm_location = getattr(profile, "location", "") or "Tambulig, Zamboanga del Sur"

    context = {
        "is_elevated": is_elevated,
        "farm_name": farm_name,
        "farm_location": farm_location,
        "total_chickens": total_chickens,
        "total_flocks": total_flocks,
        "low_stock_items": low_stock_items,
        "expired_items": expired_items,
        "today_eggs": today_eggs,
        "week_eggs": week_eggs,
        "month_eggs": month_eggs,
        "total_mortality": total_mortality,
        "week_sales": week_sales,
        "month_sales": month_sales,
        "week_expenses": week_expenses,
        "month_expenses": month_expenses,
        "receivables": receivables,
        "open_requests": open_requests,
        "open_deliveries": open_deliveries,
        "recent_activities": recent_activities,
        "recent_notifications": recent_notifications,
        "trays_sold_chart_data": trays_sold_chart_data,
        "total_trays_sold_7d": total_trays_sold_7d,
        "egg_production_chart_data": egg_production_chart_data,
        "total_eggs_7d": total_eggs_7d,
        "mortality_chart_data": mortality_chart_data,
    }
    return render(request, "dashboard/index.html", context)


@internal_only
def farm_profile(request):
    profile, _ = FarmProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = FarmProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            farm_profile = form.save(commit=False)
            farm_profile.user = request.user
            farm_profile.save()
            return redirect("dashboard:index")
    else:
        form = FarmProfileForm(instance=profile)
    return render(request, "dashboard/farm_profile.html", {"form": form, "profile": profile})
