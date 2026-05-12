import csv
from pathlib import Path

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.db import transaction

from accounts.models import Profile


class Command(BaseCommand):
    help = "CSV 파일에서 유저와 프로필 데이터를 임포트합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_path",
            type=str,
            help="임포트할 CSV 파일 경로"
        )

    @transaction.atomic
    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])

        if not csv_path.exists():
            self.stdout.write(self.style.ERROR(f"파일이 존재하지 않습니다: {csv_path}"))
            return

        Profile.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()

        self.stdout.write(self.style.WARNING("기존 일반 유저와 프로필 삭제 완료"))

        created_users = 0
        created_profiles = 0
        skipped_rows = 0
        duplicate_rows = 0
        seen_usernames = set()

        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            for idx, row in enumerate(reader, start=2):
                name = (row.get("이름") or "").strip()
                student_id = (row.get("학번") or "").strip()

                if not name or not student_id:
                    skipped_rows += 1
                    continue

                if student_id == "00000":
                    username = f"t_{name}"
                    password = "00000"
                    library_code = f"T_{name}"
                else:
                    username = student_id
                    password = student_id
                    library_code = student_id

                if username in seen_usernames:
                    duplicate_rows += 1
                    continue

                seen_usernames.add(username)

                user = User.objects.create(
                    username=username,
                    first_name=name,
                    email="",
                    password=make_password(password),
                    is_staff=False,
                    is_superuser=False,
                    is_active=True,
                )

                Profile.objects.create(
                    user=user,
                    library_code=library_code
                )

                created_users += 1
                created_profiles += 1

        self.stdout.write(self.style.SUCCESS(
            "\n유저 임포트 완료\n"
            f"- 유저 생성: {created_users}명\n"
            f"- 프로필 생성: {created_profiles}명\n"
            f"- 빈 값으로 건너뜀: {skipped_rows}개\n"
            f"- 중복으로 건너뜀: {duplicate_rows}개"
        ))