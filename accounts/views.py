from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from .forms import SignupForm
from .models import Profile
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from books.models import Loan

class SignUpView(CreateView):
    form_class = SignupForm
    success_url = reverse_lazy('login')
    template_name = 'registration/signup.html'

    def form_valid(self, form):
        response = super().form_valid(form)  # 여기서 User 저장됨
        user = self.object

        # 이름 저장
        user.first_name = form.cleaned_data.get("first_name", "")
        user.save(update_fields=["first_name"])

        # 도서관 번호 저장
        Profile.objects.create(
            user=user,
            library_code=form.cleaned_data.get("library_code", "")
        )
        return response

@login_required
def my_page(request):
    # 현재 대출중(반납 안 됨)인 것만 가져와서 2개 슬롯에 넣기
    active_loans = (
        Loan.objects
        .select_related("book")
        .filter(user=request.user, returned_at__isnull=True)
        .order_by("loaned_at")[:2]
    )

    loan1 = active_loans[0] if len(active_loans) > 0 else None
    loan2 = active_loans[1] if len(active_loans) > 1 else None

    context = {
        "user_obj": request.user,
        "loan1": loan1,
        "loan2": loan2,
    }
    return render(request, "accounts/my_page.html", context)