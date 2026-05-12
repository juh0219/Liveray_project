import random
import re
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, F, Count, Max
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from datetime import timedelta
from django.utils.dateparse import parse_date
from django.utils import timezone

from .models import Book, Review, Loan



# --- 유틸리티 함수 ---

def get_exact_tag_q(field_name, tag_list):
    if not tag_list:
        return Q()
    q_obj = Q()
    for tag in tag_list:
        tag = tag.strip()
        if not tag: continue
        regex = r'(^|,\s*)' + re.escape(tag) + r'($|,\s*)'
        q_obj |= Q(**{f"{field_name}__iregex": regex})
    return q_obj


def get_tags_list(request, key):
    """GET 파라미터에서 쉼표로 구분된 값을 리스트로 변환"""
    val = request.GET.get(key, '')
    return [v.strip() for v in val.split(',') if v.strip()]


# --- 핵심 뷰 함수 ---

def book_search(request):
    """태그 필터링 및 키워드 검색 뷰 (쉼표 구분 태그 분리 처리 적용)"""
    q = request.GET.get('q', '')
    t1 = request.GET.get('t1', '')
    date_raw = request.GET.get('date', '')
    add_raw = request.GET.get('add', '')

    filters = {
        't2': get_tags_list(request, 't2'),
        't3': get_tags_list(request, 't3'),
        'st': get_tags_list(request, 'st'),
        'gt': get_tags_list(request, 'gt'),
    }

    def get_filtered_qs(exclude_key=None):
        qs = Book.objects.all()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(author__icontains=q))
        if t1:
            qs = qs.filter(get_exact_tag_q('tag1', [t1]))

        if exclude_key != 't2' and filters['t2']: qs = qs.filter(get_exact_tag_q('tag2', filters['t2']))
        if exclude_key != 't3' and filters['t3']: qs = qs.filter(get_exact_tag_q('tag3', filters['t3']))
        if exclude_key != 'st' and filters['st']: qs = qs.filter(get_exact_tag_q('s_tag', filters['st']))
        if exclude_key != 'gt' and filters['gt']: qs = qs.filter(get_exact_tag_q('g_tag', filters['gt']))

        if exclude_key != 'date' and date_raw and ',' in date_raw:
            try:
                start, end = date_raw.split(',')
                qs = qs.filter(pub_year__range=(start.strip(), end.strip()))
            except ValueError:
                pass

        if exclude_key != 'add' and add_raw and ',' in add_raw:
            try:
                start_str, end_str = add_raw.split(',')
                start_date = parse_date(start_str.strip()) if start_str.strip() else None
                end_date = parse_date(end_str.strip()) if end_str.strip() else None

                if start_date and end_date:
                    qs = qs.filter(add_date__range=(start_date, end_date))
                elif start_date:
                    qs = qs.filter(add_date__date__gte=start_date)
                elif end_date:
                    qs = qs.filter(add_date__date__lte=end_date)
            except ValueError:
                pass
        return qs

    # [수정] 쉼표로 구분된 문자열을 모두 분리하여 고유 리스트로 만드는 헬퍼 함수
    def get_split_tags(qs, field):
        raw_values = qs.exclude(**{f"{field}__isnull": True}).exclude(**{field: ""}).values_list(field, flat=True)
        tag_set = set()
        for val in raw_values:
            for t in val.split(','):
                tag_set.add(t.strip())
        return tag_set

    # [수정] 일반 태그 추출: 쉼표 분리 처리 및 선택 태그 유지
    # [수정] 일반 태그 추출: 쉼표 분리 처리 및 선택 태그 유지
    def extract_with_active(qs, field, active_list):
        found_set = get_split_tags(qs, field)
        # 1. 현재 선택된 태그들 (가나다순 정렬)
        active_part = sorted(list(set(active_list)))
        # 2. 선택되지 않은 나머지 태그들 (가나다순 정렬)
        other_part = sorted([t for t in found_set if t not in active_part])

        return active_part + other_part

    # [수정] s_tag 정렬: 선택된 태그를 맨 앞으로, 나머지는 최신 연도순 정렬
    def extract_st_sorted(qs, active_list):
        raw_data = qs.exclude(s_tag__isnull=True).exclude(s_tag="").values_list('s_tag', 'pub_year')

        tag_max_year = {}
        for s_tags_str, year in raw_data:
            if not s_tags_str: continue
            try:
                curr_year = int(year) if year else 0
            except:
                curr_year = 0

            for t in s_tags_str.split(','):
                tag = t.strip()
                if not tag: continue
                tag_max_year[tag] = max(tag_max_year.get(tag, 0), curr_year)

        # 전체 태그를 연도 내림차순으로 미리 정렬
        sorted_tags = sorted(tag_max_year.keys(), key=lambda x: (-tag_max_year[x], x))

        # 1. 현재 선택된 태그들 (가나다순 정렬)
        active_part = sorted(list(set(active_list)))
        # 2. 선택되지 않은 나머지 태그들 (기존 연도순 유지)
        other_part = [x for x in sorted_tags if x not in active_part]

        return active_part + other_part

    # --- 태그 목록 추출 ---
    available_tags = {
        'st': extract_st_sorted(get_filtered_qs('st'), filters['st']),
        't2': extract_with_active(get_filtered_qs('t2'), 'tag2', filters['t2']),
        't3': extract_with_active(get_filtered_qs('t3'), 'tag3', filters['t3']),
        'gt': extract_with_active(get_filtered_qs('gt'), 'g_tag', filters['gt']) if t1 == '⚫ 문학' else []
    }

    # [유지] 날짜 내림차순 정렬
    all_years = sorted(list(get_filtered_qs('date').values_list('pub_year', flat=True).distinct()), reverse=True)
    date_tags = []
    processed_groups = set()
    for y_str in all_years:
        try:
            y = int(y_str)
            decade = (y // 10) * 10
            last = y % 10
            if 0 <= last <= 3:
                group, val = f"{decade}년대 초반", f"{decade},{decade + 3}"
            elif 4 <= last <= 6:
                group, val = f"{decade}년대 중반", f"{decade + 4},{decade + 6}"
            else:
                group, val = f"{decade}년대 후반", f"{decade + 7},{decade + 9}"
            if group not in processed_groups:
                date_tags.append({'display': group, 'value': val})
                processed_groups.add(group)
        except:
            continue

    books = get_filtered_qs().distinct().order_by('-add_date', 'title')

    context = {
        'books': books,
        'available_tags': available_tags,
        'date_tags': date_tags,
        'active_tags': {**filters, 't1': t1, 'date': date_raw, 'add': add_raw},
        'query': q or t1 or "필터 결과"
    }
    return render(request, 'books/book_search.html', context)


def book_list(request):
    """메인 대시보드 뷰"""
    filter_params = ['q', 't1', 't2', 't3', 'st', 'gt', 'date', 'all', 'add']
    if any(param in request.GET for param in filter_params):
        return book_search(request)

    tag_config = [
        ("우리나라 금융의 미래는?", {'t1': "⚪ 사회과학", 't2': "💰 경제", 't3': "💰 금융"}),
        ("코기토 선배의 추천 문학", {'t1': "⚫ 문학"}),
        ("코기토 선배의 인생 가이드", {'t2': "🩺 의학,🕊️ 윤리•도덕"}),
    ]

    tag_sections = []
    for display_title, filters in tag_config:
        section_qs = Book.objects.all()
        if 't1' in filters: section_qs = section_qs.filter(get_exact_tag_q('tag1', [filters['t1']]))
        if 't2' in filters: section_qs = section_qs.filter(get_exact_tag_q('tag2', filters['t2'].split(',')))
        if 't3' in filters: section_qs = section_qs.filter(get_exact_tag_q('tag3', filters['t3'].split(',')))

        pills = []
        query_params = []
        for key, value in filters.items():
            for tag in [t.strip() for t in value.split(',') if t.strip()]:
                pills.append({'key': key, 'val': tag})
            query_params.append(f"{key}={value}")

        section_books = section_qs.distinct().order_by('title')[:20]
        if section_books.exists():
            tag_sections.append({
                'title': display_title,
                'books': section_books,
                'pills': pills,
                'combined_query': "&".join(query_params),
                'query_string': "&".join(query_params)
            })

    all_books = Book.objects.all().order_by('title')[:50]
    # 추천 섹션 (캐싱 없이 간단히 구현)
    all_pks = list(Book.objects.values_list('id', flat=True))
    random_books = []
    if all_pks:
        random.seed(timezone.now().date().toordinal())
        random_pks = random.sample(all_pks, min(len(all_pks), 20))
        random_books = Book.objects.filter(pk__in=random_pks)

    like_books = Book.objects.annotate(num_likes=Count('liked_users')) \
                     .filter(num_likes__gte=1) \
                     .order_by('-num_likes')[:20]

    # (4) 평론이 많은 화제의 도서 (리뷰 3개 이상)
    review_books = Book.objects.annotate(num_reviews=Count('reviews')) \
                       .filter(num_reviews__gte=3) \
                       .order_by('-num_reviews')[:20]

    # (5) 출판 기간 지정
    # pub_year가 null이 아니고 2020 이상인 데이터
    year_books = Book.objects.filter(pub_year__isnull=False) \
                     .filter(pub_year__range=(2010, 2013)) \
                     .order_by('-pub_year', 'title')[:20]

    # (6) 새로 들어온 책
    recent_books = Book.objects.filter(add_date__isnull=False) \
                       .filter(add_date__range=["2025-01-01", "2026-12-31"]) \
                       .order_by('-add_date', 'title')[:20]

    user_author_books = []
    if request.user.is_authenticated:
        name = request.user.first_name or request.user.username
        user_author_books = Book.objects.filter(author__icontains=name).order_by('title')[:20]

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


# --- 상세 및 액션 함수 (생략 없이 유지) ---

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