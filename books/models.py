from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Avg
from django.utils import timezone


class Book(models.Model):
    title = models.CharField("서명", max_length=200)
    author = models.CharField("저자", max_length=120, blank=True)
    publisher = models.CharField("출판사", max_length=120, blank=True)
    pub_year = models.CharField("출판년도", max_length=10, blank=True)
    call_number = models.CharField("청구기호", max_length=50, blank=True)
    isbn = models.CharField("ISBN", max_length=20, blank=True, null=True)
    cover = models.URLField("표지 링크", blank=True, null=True)
    stock = models.PositiveIntegerField("재고 수", default=0)
    booknum = models.TextField("옥야 번호", blank=True)
    add_date = models.CharField("등록일", max_length=200, blank=True)

    liked_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="liked_books",
        blank=True,
        verbose_name="좋아요 누른 사용자"
    )
    sortnum = models.CharField("분류 번호", max_length=50, default=0, blank=True)
    tag1 = models.CharField("태그1", max_length=50, blank=True)
    tag2 = models.CharField("태그2", max_length=50, blank=True)
    tag3 = models.CharField("태그3", max_length=50, blank=True)
    g_tag = models.CharField("장르태그", max_length=50, blank=True)
    s_tag = models.CharField("특수태그", max_length=100, blank=True)



    class Meta:
        unique_together = ("title", "author", "publisher", "pub_year", "call_number")
        verbose_name = "도서"
        verbose_name_plural = "도서"

    def __str__(self):
        return f"{self.title} ({self.call_number})"

    @property
    def likes_count(self):
        return self.liked_users.count()

    @property
    def review_count(self) -> int:
        return self.reviews.filter(is_public=True).count()

    @property
    def average_rating(self):
        agg = self.reviews.filter(is_public=True).aggregate(avg=Avg("rating"))
        return agg["avg"]  # 없으면 None


class Review(models.Model):
    book = models.ForeignKey(
        Book,
        related_name="reviews",
        on_delete=models.CASCADE,
        verbose_name="도서"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="작성자"
    )
    content = models.TextField("리뷰 내용", max_length=2000)
    rating = models.PositiveSmallIntegerField(
        "별점",
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    is_anonymous = models.BooleanField("익명 여부", default=True)
    created_at = models.DateTimeField("작성일", auto_now_add=True)
    updated_at = models.DateTimeField("수정일", auto_now=True)
    is_public = models.BooleanField("공개 여부", default=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "리뷰"
        verbose_name_plural = "리뷰"

    def __str__(self):
        uname = "익명" if self.is_anonymous or not self.user else self.user.username
        return f"[{self.rating}★] {uname}: {self.content[:20]}..."

class Loan(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="loans")
    book = models.ForeignKey("books.Book", on_delete=models.CASCADE, related_name="loans")

    loaned_at = models.DateField(default=timezone.now)   # 대출일
    due_days = models.PositiveSmallIntegerField(default=14)  # 기본 14일
    returned_at = models.DateField(null=True, blank=True)  # 반납일(반납 전이면 None)

    class Meta:
        ordering = ["-loaned_at"]

    def __str__(self):
        return f"{self.user} - {self.book} ({self.loaned_at})"

    @property
    def is_active(self):
        return self.returned_at is None