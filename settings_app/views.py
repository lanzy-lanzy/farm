from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from dashboard.forms import FarmProfileForm
from dashboard.models import FarmProfile
from settings_app.models import SystemSetting


@login_required
def settings_view(request):
    profile, _ = FarmProfile.objects.get_or_create(user=request.user)
    return render(request, "settings/settings.html", {"profile": profile})


@login_required
def farm_settings(request):
    profile, _ = FarmProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = FarmProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            farm_profile = form.save(commit=False)
            farm_profile.user = request.user
            farm_profile.save()
            return redirect("settings_app:settings")
    else:
        form = FarmProfileForm(instance=profile)
    return render(request, "settings/farm_settings.html", {"form": form, "profile": profile})
