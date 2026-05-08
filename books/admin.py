from django.contrib import admin
from .models import Book, Review, Loan


class ReviewInline(admin.TabularInline):
    model = Review
    extra = 1
    fields = ("user", "rating", "content", "is_public", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author",
        "publisher",
        "pub_year",
        "isbn",
        "call_number",
        "booknum",
        "add_date",
        "stock",
        "likes_count",
        "avg_rating",
        "review_cnt",
        "sortnum",
        "tag1",
        "tag2",
        "tag3",
        "g_tag",
        "s_tag",
    )
    search_fields = (
        "title",
        "author",
        "publisher",
        "call_number",
        "isbn",
        "booknum",
        "add_date",
        "sortnum",
        "tag1",
        "tag2",
        "tag3",
        "g_tag",
        "s_tag",
    )
    list_filter = ("publisher", "pub_year", "sortnum", "tag1", "tag2", "tag3", "g_tag","s_tag",)
    inlines = [ReviewInline]

    @admin.display(description="평균 별점")
    def avg_rating(self, obj: Book):
        avg = obj.average_rating
        return "-" if avg is None else f"{avg:.2f}"

    @admin.display(description="리뷰 수")
    def review_cnt(self, obj: Book):
        return obj.review_count


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("book", "user", "user__first_name", "rating", "is_public", "created_at")
    search_fields = ("book__title", "user__username", "user__first_name", "content")
    list_filter = ("rating", "is_public", "created_at")

@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ("user", "user__first_name", "book", "loaned_at", "returned_at", "is_active")
    list_filter = ("returned_at", "loaned_at")
    search_fields = ("user__username", "user__first_name", "book__title")
    actions = ["mark_returned"]

    @admin.display(description="대출중", boolean=True)
    def is_active(self, obj: Loan):
        return obj.returned_at is None

    @admin.action(description="선택한 대출을 반납 처리(오늘 날짜)")
    def mark_returned(self, request, queryset):
        from django.utils import timezone
        today = timezone.localdate()
        queryset.filter(returned_at__isnull=True).update(returned_at=today)
