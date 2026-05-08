import random
import re
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, F
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from datetime import timedelta
from django.db.models import Count, Q
from django.db.models import Q
from django.shortcuts import redirect, reverse
from .models import Book
from django.utils.dateparse import parse_date
from django.utils import timezone

from .models import Book, Review, Loan


def get_exact_tag_q(field_name, tag_list):
    """
    쉼표로 구분된 문자열 내에서 특정 태그가 '완전 일치'하는지 찾는 Q 객체 생성
    예: '경제' 검색 시 '경제학'은 제외하고 ', 경제, ' 혹은 '경제'인 경우만 매칭
    """
    if not tag_list:
        return Q()

    q_obj = Q()
    for tag in tag_list:
        tag = tag.strip()
        if not tag: continue
        # 정규식: (시작 또는 쉼표+공백) + 태그명 + (종료 또는 쉼표+공백)
        regex = r'(^|,\s*)' + re.escape(tag) + r'($|,\s*)'
        q_obj |= Q(**{f"{field_name}__iregex": regex})
    return q_obj


def book_list(request):
    all_books = request.GET.get('all')
    q = request.GET.get('q')  # 일반 키워드 검색
    t1 = request.GET.get('t1')  # tag1 (단일)
    t2_raw = request.GET.get('t2')  # tag2 (여러개)
    t3_raw = request.GET.get('t3')  # tag3 (여러개)
    gt_raw = request.GET.get('gt')  # g_tag (여러개)
    st_raw = request.GET.get('st')  # s_tag (여러개)
    date_raw = request.GET.get('date')  # 기간 (2016,2020)
    add_raw = request.GET.get('add')  # 예: "2026-04-01,2026-04-30"

    # 쉼표 구분된 값들을 리스트로 변환
    def split_raw(val):
        return [item.strip() for item in val.split(',') if item.strip()] if val else []

    t2_list = split_raw(t2_raw)
    t3_list = split_raw(t3_raw)
    gt_list = split_raw(gt_raw)
    st_list = split_raw(st_raw)

    # 필터링 모드 활성화 여부
    is_filtering = any([all_books, q, t1, t2_raw, t3_raw, gt_raw, st_raw, date_raw, add_raw])

    if is_filtering:
        books = Book.objects.all()

        if all_books == 'true':
            pass

        # 0. 기본 키워드 검색 (기존 기능 유지)
        if q:
            books = books.filter(Q(title__icontains=q) | Q(author__icontains=q))

        # 1단계: t1 (단일 완전 일치)
        if t1:
            books = books.filter(get_exact_tag_q('tag1', [t1]))

        # 2단계: t2 & t3 행렬 필터링 (Cross Product)
        if t2_list or t3_list:
            matrix_q = Q()
            if t2_list and t3_list:
                # 둘 다 있으면 (A1&B1) | (A1&B2) | (A2&B1) ...
                for v2 in t2_list:
                    for v3 in t3_list:
                        matrix_q |= (get_exact_tag_q('tag2', [v2]) & get_exact_tag_q('tag3', [v3]))
            elif t2_list:
                matrix_q = get_exact_tag_q('tag2', t2_list)
            else:
                matrix_q = get_exact_tag_q('tag3', t3_list)
            books = books.filter(matrix_q)

        # 3단계: gt (g_tag 중 하나라도 포함)
        if gt_list:
            books = books.filter(get_exact_tag_q('y_tag', gt_list))  # 모델 필드명이 y_tag인 경우

        # 4단계: st (s_tag 중 하나라도 포함)
        if st_list:
            books = books.filter(get_exact_tag_q('s_tag', st_list))

        # 5단계: date 범위 필터링
        if date_raw and ',' in date_raw:
            try:
                start, end = date_raw.split(',')
                books = books.filter(pub_year__range=(start.strip(), end.strip()))
            except ValueError:
                pass

        # 6단계: add_date 범위 필터링
        if add_raw and ',' in add_raw:
            try:
                start_str, end_str = add_raw.split(',')
                start_date = parse_date(start_str.strip()) if start_str.strip() else None
                end_date = parse_date(end_str.strip()) if end_str.strip() else None

                if start_date and end_date:
                    # 시작일 ~ 종료일 사이
                    books = books.filter(add_date__range=(start_date, end_date))
                elif start_date:
                    # 시작일 이후 전체
                    books = books.filter(add_date__date__gte=start_date)
                elif end_date:
                    # 종료일 이전 전체
                    books = books.filter(add_date__date__lte=end_date)
            except ValueError:
                pass

        return render(request, 'books/book_search.html', {
            'books': books.distinct().order_by('title'),
            'query': q or "필터 검색 결과"
        })

    # --- [메인 화면 로직: 태그 섹션에도 동일 알고리즘 적용] ---
    # tag_config를 이제 (제목, 필터딕셔너리) 구조로 변경합니다.
    tag_config = [
        ("우리나라 금융의 미래는?", {'t1': "⚪ 사회과학", 't2': "💰 경제", 't3': "💰 금융"}),
        ("코기토 선배의 추천 문학", {'t1': "⚫ 문학"}),
        ("코기토 선배의 인생 가이드", {'t2': "🩺 의학,🕊️ 윤리•도덕"}),
    ]

    tag_sections = []
    for display_title, filters in tag_config:
        section_qs = Book.objects.all()

        # filters 딕셔너리에 있는 키값에 따라 5단계 로직을 동일하게 적용
        if 't1' in filters:
            section_qs = section_qs.filter(get_exact_tag_q('tag1', [filters['t1']]))
        if 't2' in filters:
            section_qs = section_qs.filter(get_exact_tag_q('tag2', filters['t2'].split(',')))
        if 't3' in filters:
            section_qs = section_qs.filter(get_exact_tag_q('tag3', filters['t3'].split(',')))
        if 'gt' in filters:
            section_qs = section_qs.filter(get_exact_tag_q('y_tag', filters['gt'].split(',')))
        if 'st' in filters:
            section_qs = section_qs.filter(get_exact_tag_q('s_tag', filters['st'].split(',')))
        pills = []
        query_params = []

        for key, value in filters.items():
            # 쉼표로 구분된 태그들을 각각의 개별 버튼(pill)으로 분리
            tag_list = [t.strip() for t in value.split(',') if t.strip()]
            for tag in tag_list:
                pills.append({'key': key, 'val': tag})

            query_params.append(f"{key}={value}")

        section_books = section_qs.distinct().order_by('title')[:50]
        if section_books.exists():
            tag_sections.append({
                'title': display_title,
                'books': section_books,
                'pills': pills,
                'combined_query': "&".join(query_params),
                'query_string': "&".join([f"{k}={v}" for k, v in filters.items()])
            })

    # 3. 기본 섹션 데이터 정의

    # (1) 전체 도서 목록 (가나다순)
    all_books = Book.objects.all().order_by('title')[:50]

    # (2) 오늘의 랜덤 추천
    all_pks = list(Book.objects.values_list('id', flat=True))
    random_books = []
    if all_pks:
        random.seed(timezone.now().date().toordinal())
        random_pks = random.sample(all_pks, min(len(all_pks), 50))
        random_books = Book.objects.filter(pk__in=random_pks)

    # (3) 인기 있는 도서 (좋아요 3개 이상)
    like_books = Book.objects.annotate(num_likes=Count('liked_users')) \
                     .filter(num_likes__gte=1) \
                     .order_by('-num_likes')[:50]

    # (4) 평론이 많은 화제의 도서 (리뷰 3개 이상)
    review_books = Book.objects.annotate(num_reviews=Count('reviews')) \
                       .filter(num_reviews__gte=3) \
                       .order_by('-num_reviews')[:50]

    # (5) 출판 기간 지정
    # pub_year가 null이 아니고 2020 이상인 데이터
    year_books = Book.objects.filter(pub_year__isnull=False) \
                     .filter(pub_year__range=(2010, 2019)) \
                     .order_by('-pub_year', 'title')[:50]

    # (6) 새로 들어온 책
    recent_books = Book.objects.filter(add_date__isnull=False) \
                       .filter(add_date__range=["2025-01-01", "2026-12-31"]) \
                       .order_by('-add_date', 'title')[:50]

    # (7) 사용자 이름 작가 섹션
    user_author_books = []
    if request.user.is_authenticated:
        name = request.user.first_name or request.user.username
        user_author_books = Book.objects.filter(author__icontains=name).order_by('title')[:50]

    context = {
        'all_books': all_books,
        'tag_sections': tag_sections,
        'random_books': random_books,
        'like_books': like_books,
        'review_books': review_books,
        'year_books': year_books,
        'recent_books': recent_books,
        'user_author_books': user_author_books,
    }

    return render(request, 'books/book_list.html', context)


# 이하 기존 detail, like, review_add, loan_book 함수는 동일 (생략)
def book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)
    reviews = book.reviews.filter(is_public=True).select_related("user").order_by('-created_at')
    user_liked = False
    if request.user.is_authenticated:
        user_liked = book.liked_users.filter(pk=request.user.pk).exists()
    return render(request, 'books/book_detail.html', {
        'book': book,
        'reviews': reviews,
        'user_liked': user_liked,
    })


@require_POST
@login_required
def book_like(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if book.liked_users.filter(pk=request.user.pk).exists():
        book.liked_users.remove(request.user)
        liked = False
    else:
        book.liked_users.add(request.user)
        liked = True
    return JsonResponse({'ok': True, 'liked': liked, 'likes': book.likes_count})


@require_POST
@login_required
def review_add(request, pk):
    book = get_object_or_404(Book, pk=pk)
    content = (request.POST.get('content') or '').strip()
    try:
        rating = int(request.POST.get('rating', 5))
    except (TypeError, ValueError):
        rating = 5
    if rating < 1 or rating > 5:
        return JsonResponse({'ok': False, 'error': 'invalid_rating'}, status=400)
    if not content:
        return JsonResponse({'ok': False, 'error': 'empty'}, status=400)
    is_anonymous = request.POST.get('is_anonymous') == 'true'
    review = Review.objects.create(
        book=book, user=request.user, content=content,
        rating=rating, is_anonymous=is_anonymous, is_public=True,
    )
    return JsonResponse({
        'ok': True,
        'review': {
            'content': review.content,
            'rating': review.rating,
            'author': '익명' if review.is_anonymous or not review.user else review.user.first_name,
            'created_at': (review.created_at + timedelta(hours=9)).strftime('%Y-%m-%d %H:%M'),
        }
    })


@transaction.atomic
def loan_book(request, pk):
    # 1. 비로그인 사용자 처리
    if not request.user.is_authenticated:
        messages.error(request, "로그인이 필요합니다.")  # 메시지 굽기
        return redirect(f"/accounts/login/?next=/books/{pk}/")  # 로그인 후 다시 이 책으로 오게 함

    if request.method != "POST":
        return redirect("book_detail", pk=pk)
    book = get_object_or_404(Book, pk=pk)
    active_count = Loan.objects.filter(user=request.user, returned_at__isnull=True).count()
    if active_count >= 2:
        messages.error(request, "이미 대출 가능한 최대 권수(2권)를 채웠습니다.")
        return redirect("book_detail", pk=pk)
    already = Loan.objects.filter(user=request.user, book=book, returned_at__isnull=True).exists()
    if already:
        messages.info(request, "이미 이 책을 대출 중입니다.")
        return redirect("book_detail", pk=pk)
    updated = Book.objects.filter(pk=book.pk, stock__gt=0).update(stock=F("stock") - 1)
    if updated == 0:
        messages.error(request, "재고가 없어 대출할 수 없습니다.")
        return redirect("book_detail", pk=pk)
    Loan.objects.create(user=request.user, book=book)
    messages.success(request, "대출이 완료되었습니다.")
    return redirect("my_page")


@require_POST
def update_isbn_status(request):
    book_id = request.POST.get('book_id')
    status = request.POST.get('status')

    if book_id and status in ['Basic', 'None']:
        # .filter().update()는 훨씬 빠르고 DB 잠금 시간을 극단적으로 줄여줍니다.
        # 이미 해당 상태인 경우는 건드리지 않도록 exclude 추가
        updated_count = Book.objects.filter(id=book_id).exclude(isbn=status).update(isbn=status)

        return JsonResponse({'ok': True, 'updated': updated_count > 0})
    return JsonResponse({'ok': False}, status=400)