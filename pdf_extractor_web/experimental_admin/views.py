from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required


@staff_member_required
def index(request):
    return render(request, "experimental_admin/index.html")


@staff_member_required
def transaction_list(request):
    from profiles.models import Transaction

    transactions = Transaction.objects.all()
    return render(
        request,
        "experimental_admin/transaction_list.html",
        {"transactions": transactions},
    )


@staff_member_required
def task_list(request):
    from profiles.models import ProcessingTask

    tasks = ProcessingTask.objects.all()
    return render(request, "experimental_admin/task_list.html", {"tasks": tasks})
