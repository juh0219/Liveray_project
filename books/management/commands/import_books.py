import csv
import re

from django.core.management.base import BaseCommand
from books.models import Book

COPY_SUFFIX_RE = re.compile(r"\s*c\.(\d+)$", re.IGNORECASE)


class Command(BaseCommand):
    help = "CSV → Book 전체 덮어쓰기 + 복본 stock 합산"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str)

    def handle(self, *args, **options):
        file_path = options["csv_file"]

        Book.objects.all().delete()
        self.stdout.write("기존 데이터 삭제 완료")

        grouped = {}
        total_rows = 0

        with open(file_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            # 헤더 확인용
            self.stdout.write(f"CSV 헤더: {reader.fieldnames}")

            for row in reader:
                total_rows += 1

                title = (row.get("자료명") or "").strip()
                author = (row.get("저자") or "").strip()
                publisher = (row.get("출판사") or "").strip()
                pub_year = (row.get("출판년도") or "").strip()
                call_raw = (row.get("청구기호") or "").strip()

                # ISBN 헤더 후보를 넓게 잡음
                isbn = (
                    row.get("isbn")
                    or row.get("ISBN")
                    or row.get("ISBN13")
                    or row.get("isbn13")
                    or row.get("도서ISBN")
                    or row.get("ISBN 번호")
                    or ""
                )
                isbn = isbn.strip()

                sortnum = (row.get("sortnum") or row.get("분류번호") or row.get("분류 번호") or "")
                sortnum = str(sortnum).strip()
                tag1 = (row.get("tag1") or row.get("태그1") or "").strip()
                tag2 = (row.get("tag2") or row.get("태그2") or "").strip()
                tag3 = (row.get("tag3") or row.get("태그3") or "").strip()
                s_tag = (row.get("s_tag") or row.get("s_태그") or "").strip()
                g_tag = (row.get("g_tag") or row.get("g_태그") or "").strip()
                booknum = (row.get("등록번호") or "").strip()
                add_date = (row.get("등록일") or "").strip()


                if not title:
                    continue

                # 복본 표기 제거
                m = COPY_SUFFIX_RE.search(call_raw)
                call_number = call_raw[:m.start()].rstrip() if m else call_raw

                # 우선 제목+저자+출판사+출판년도+청구기호 기준
                key = (title, author, publisher, pub_year, call_number)

                if key not in grouped:
                    grouped[key] = {
                        "title": title,
                        "author": author,
                        "publisher": publisher,
                        "pub_year": pub_year,
                        "call_number": call_number,
                        "isbn": isbn,
                        "stock": 1,
                        "sortnum": sortnum,
                        "tag1": tag1,
                        "tag2": tag2,
                        "tag3": tag3,
                        "s_tag": s_tag,
                        "g_tag": g_tag,
                        "booknum": booknum,
                        "add_date": add_date,
                    }
                else:
                    grouped[key]["stock"] += 1
                    if not grouped[key]["isbn"] and isbn:
                        grouped[key]["isbn"] = isbn
                    if not grouped[key]["sortnum"] and sortnum:
                        grouped[key]["sortnum"] = sortnum
                    if not grouped[key]["tag1"] and tag1:
                        grouped[key]["tag1"] = tag1
                    if not grouped[key]["tag2"] and tag2:
                        grouped[key]["tag2"] = tag2
                    if not grouped[key]["tag3"] and tag3:
                        grouped[key]["tag3"] = tag3
                    if not grouped[key]["s_tag"] and s_tag:
                        grouped[key]["s_tag"] = s_tag
                    if not grouped[key]["g_tag"] and g_tag:
                        grouped[key]["g_tag"] = g_tag
                    if not grouped[key]["add_date"] and add_date:
                        grouped[key]["add_date"] =add_date

                    if booknum:
                        existing_nums = (
                            grouped[key]["booknum"].split(",")
                            if grouped[key]["booknum"]
                            else[]
                        )

                        if booknum not in existing_nums:
                            existing_nums.append(booknum)

                        grouped[key]["booknum"] = ",".join(existing_nums)

        created_count = 0
        isbn_count = 0

        for data in grouped.values():
            Book.objects.create(
                title=data["title"],
                author=data["author"],
                publisher=data["publisher"],
                pub_year=data["pub_year"],
                call_number=data["call_number"],
                isbn=data["isbn"] or None,
                stock=data["stock"],
                sortnum=data["sortnum"] or "0",
                tag1=data["tag1"],
                tag2=data["tag2"],
                tag3=data["tag3"],
                s_tag=data["s_tag"],
                g_tag=data["g_tag"],
                booknum=data["booknum"],
                add_date=data["add_date"],
            )
            created_count += 1
            if data["isbn"]:
                isbn_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"CSV 행 수: {total_rows}개 / 생성된 도서: {created_count}권 / ISBN 포함 도서: {isbn_count}권"
        ))