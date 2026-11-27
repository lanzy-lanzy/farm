from accounts.access import admin_or_owner_required, staff_or_admin_required
from django.contrib import messages
from django.shortcuts import redirect, render

from dashboard.forms import FarmProfileForm
from dashboard.models import FarmProfile
from settings_app.models import SystemSetting

from . import network


@admin_or_owner_required
def settings_view(request):
    profile, _ = FarmProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "farm_name": "Tambulig Poultry Farm",
            "location": "Tambulig, Zamboanga del Sur",
        },
    )
    return render(request, "settings/settings.html", {"profile": profile})


@admin_or_owner_required
def farm_settings(request):
    profile, _ = FarmProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "farm_name": "Tambulig Poultry Farm",
            "location": "Tambulig, Zamboanga del Sur",
        },
    )
    if request.method == "POST":
        form = FarmProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            farm_profile = form.save(commit=False)
            farm_profile.user = request.user
            farm_profile.save()
            messages.success(request, "Farm profile updated successfully.")
            return redirect("settings_app:farm_settings")
    else:
        form = FarmProfileForm(instance=profile)
    return render(request, "settings/farm_settings.html", {"form": form, "profile": profile})


@admin_or_owner_required
def order_workflow_settings(request):
    """Configure automated Buyer & Admin order status progression rules."""
    from buyers.workflow import get_workflow_rules, save_workflow_rules

    if request.method == "POST":
        save_workflow_rules(
            auto_complete_on_delivered=request.POST.get("order_auto_complete_on_delivered") == "on",
            auto_complete_on_buyer_accept=request.POST.get("order_auto_complete_on_buyer_accept") == "on",
            auto_create_sale_on_complete=request.POST.get("order_auto_create_sale_on_complete") == "on",
        )
        messages.success(request, "Order workflow automation rules updated.")
        return redirect("settings_app:order_workflow_settings")

    return render(
        request,
        "settings/order_workflow.html",
        {"rules": get_workflow_rules()},
    )


@staff_or_admin_required
def lan_sharing(request):
    """Minimal, opt-in LAN / Wi-Fi sharing control panel.

    Nothing starts on page load. The admin explicitly chooses:
      POST action=start -> launch a detached ``runserver 0.0.0.0:<port>`` and remember it.
      POST action=stop  -> kill that background process and return to idle.
    GET just reports current state (idle vs sharing) read from the state file.
    """
    current_port = network.current_server_port(request)
    default_port = current_port or 8000
    # A port the running server does NOT hold, so one click always succeeds.
    share_port = network.suggest_free_port(default_port + 1)
    lan_ips = network.lan_addresses()

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "stop":
            if network.stop_lan_server():
                messages.success(request, "Stopped sharing. The background server was closed.")
            else:
                messages.info(request, "There was no active shared server to stop.")
            return redirect("settings_app:lan_sharing")

        if action == "start":
            try:
                port = int(request.POST.get("port") or share_port)
            except (TypeError, ValueError):
                port = 0

            if not 1024 <= port <= 65535:
                messages.error(request, "Choose a port between 1024 and 65535.")
            elif port == current_port:
                messages.warning(
                    request,
                    f"Port {port} is held by this running server, which cannot "
                    "rebind itself. Pick another port (we suggest "
                    f"{share_port}) or restart the main server with "
                    f"`{network.build_command(port)}`.",
                )
            elif network.probe_port(port):
                messages.info(
                    request,
                    f"Something is already listening on port {port}. "
                    f"Try a different port (we suggest {share_port}).",
                )
            else:
                pid = network.start_lan_server(port)
                if network.wait_for_port(port):
                    network.write_state(port, pid)
                    messages.success(
                        request,
                        f"Now sharing on port {port}. Open the address below from a "
                        "device on the same Wi-Fi / LAN.",
                    )
                else:
                    messages.error(
                        request,
                        f"Could not start a server on port {port}. See "
                        "`lan_server.log` for details.",
                    )
            return redirect("settings_app:lan_sharing")

    active = network.sharing_status()
    context = {
        "lan_ips": lan_ips,
        "primary_ip": lan_ips[0] if lan_ips else None,
        "current_port": current_port,
        "default_port": default_port,
        "share_port": share_port,
        "active": active,
        "is_sharing": bool(active),
    }
    return render(request, "settings/lan_sharing.html", context)
