import csv
from pathlib import Path

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
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

        created_users = 0
        updated_users = 0
        created_profiles = 0
        updated_profiles = 0

        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            for idx, row in enumerate(reader, start=2):
                name = (row.get("이름") or "").strip()
                student_id = (row.get("학번") or "").strip()

                if not name:
                    self.stdout.write(
                        self.style.WARNING(f"{idx}행 건너뜀: 이름이 비어 있습니다.")
                    )
                    continue

                if not student_id:
                    self.stdout.write(
                        self.style.WARNING(f"{idx}행 건너뜀: 학번이 비어 있습니다. ({name})")
                    )
                    continue

                if student_id == "00000":
                    username = f"t_{name}"
                    password = "00000"
                    library_code = f"T_{name}"
                else:
                    username = student_id
                    password = student_id
                    library_code = student_id

                existing_profile = Profile.objects.filter(library_code=library_code).first()
                if existing_profile and existing_profile.user.username != username:
                    self.stdout.write(
                        self.style.ERROR(
                            f"{idx}행 오류: library_code '{library_code}'는 이미 "
                            f"다른 유저 '{existing_profile.user.username}'가 사용 중입니다."
                        )
                    )
                    continue

                user, user_created = User.objects.get_or_create(username=username)

                user.first_name = name
                user.email = ""
                user.is_staff = False
                user.is_superuser = False
                user.is_active = True
                user.set_password(password)
                user.save()

                if user_created:
                    created_users += 1
                    self.stdout.write(self.style.SUCCESS(f"유저 생성: {username} ({name})"))
                else:
                    updated_users += 1
                    self.stdout.write(self.style.WARNING(f"유저 업데이트: {username} ({name})"))

                profile, profile_created = Profile.objects.get_or_create(user=user)
                profile.library_code = library_code
                profile.save()

                if profile_created:
                    created_profiles += 1
                    self.stdout.write(self.style.SUCCESS(f"프로필 생성: {username} / {library_code}"))
                else:
                    updated_profiles += 1
                    self.stdout.write(self.style.WARNING(f"프로필 업데이트: {username} / {library_code}"))

        self.stdout.write(self.style.SUCCESS(
            "\n유저 임포트 완료\n"
            f"- 유저 생성: {created_users}명\n"
            f"- 유저 업데이트: {updated_users}명\n"
            f"- 프로필 생성: {created_profiles}명\n"
            f"- 프로필 업데이트: {updated_profiles}명"
        ))