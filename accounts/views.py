from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import LoginForm, UserRegistrationForm, UserUpdateForm
from .models import User


class CustomLoginView(LoginView):
    form_class = LoginForm
    template_name = "accounts/login.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        return response


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")


@login_required
def user_list(request):
    users = User.objects.all().order_by("-date_joined")
    return render(request, "accounts/user_list.html", {"users": users})


@login_required
def user_create(request):
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("accounts:user_list")
    else:
        form = UserRegistrationForm()
    return render(request, "accounts/user_form.html", {"form": form})


@login_required
def user_update(request, pk):
    user = User.objects.get(pk=pk)
    if request.method == "POST":
        form = UserUpdateForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            return redirect("accounts:user_list")
    else:
        form = UserUpdateForm(instance=user)
    return render(request, "accounts/user_form.html", {"form": form, "user": user})


@login_required
def user_delete(request, pk):
    user = User.objects.get(pk=pk)
    if request.method == "POST":
        user.delete()
        return redirect("accounts:user_list")
    return render(request, "accounts/user_confirm_delete.html", {"user": user})


@login_required
def profile(request):
    if request.method == "POST":
        form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect("accounts:profile")
    else:
        form = UserUpdateForm(instance=request.user)
    return render(request, "accounts/profile.html", {"form": form})
