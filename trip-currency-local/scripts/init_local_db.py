#!/usr/bin/env python3
"""
로컬 데이터베이스 초기화 스크립트
MySQL 데이터베이스에 초기 스키마와 데이터를 설정
"""
import asyncio
import os
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "services"))


def split_sql_statements(sql: str):
    """
    SQL 스크립트를 DELIMITER 블록까지 감안하여 안전하게 분리
    - CREATE PROCEDURE / FUNCTION / TRIGGER 같은 구문은 내부 ; 포함 가능 → 하나의 블록으로 처리
    """
    statements = []
    lines = sql.splitlines()
    i = 0
    buffer = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # DELIMITER 시작 감지
        if stripped.upper().startswith("DELIMITER "):
            # 지금까지 모은 일반 SQL flush
            text = "\n".join(buffer)
            if text.strip():
                parts = [p.strip() for p in text.split(";") if p.strip()]
                statements.extend(parts)
            buffer = []

            # 새로운 구분자
            parts = stripped.split(None, 1)
            custom_delim = parts[1] if len(parts) > 1 else ";"

            # custom_delim 단독 라인 나올 때까지 모아서 블록으로 추가
            i += 1
            block = []
            while i < len(lines):
                if lines[i].strip() == custom_delim:
                    if block:
                        statements.append("\n".join(block).strip())
                    break
                else:
                    block.append(lines[i])
                i += 1
        else:
            buffer.append(line)
        i += 1

    # 남은 일반 SQL flush
    text = "\n".join(buffer)
    if text.strip():
        parts = [p.strip() for p in text.split(";") if p.strip()]
        statements.extend(parts)

    return statements


async def init_local_database():
    """로컬 데이터베이스 초기화"""
    print("Initializing local MySQL database...")

    try:
        # TODO: AWS 실시간 서비스 변경 - 로컬 DB에서 AWS Aurora로 변경
        os.environ["ENVIRONMENT"] = "local"
        os.environ["DB_HOST"] = "localhost"  # AWS 실시간 시 Aurora 엔드포인트로 변경
        os.environ["DB_PORT"] = "3306"
        os.environ["DB_USER"] = "currency_user"  # AWS 실시간 시 실제 사용자명으로 변경
        os.environ["DB_PASSWORD"] = "password"  # AWS 실시간 시 Secrets Manager 사용
        os.environ["DB_NAME"] = "currency_db"
        os.environ["REDIS_HOST"] = "localhost"  # AWS 실시간 시 ElastiCache 엔드포인트로 변경

        from shared.config import init_config
        from shared.database import init_database, MySQLHelper

        # 설정 초기화
        config = init_config("db-init")
        print(f"[OK] Configuration loaded for {config.environment.value} environment")

        # 데이터베이스 연결 초기화
        await init_database()
        print("[OK] Database connection established")

        mysql_helper = MySQLHelper()

        # SQL 스크립트 실행
        sql_file = project_root / "scripts" / "init-db.sql"

        if sql_file.exists():
            print("[INFO] Executing SQL initialization script...")

            with open(sql_file, "r", encoding="utf-8") as f:
                sql_content = f.read()

            # ✅ split_sql_statements 사용 (DELIMITER 블록 처리)
            sql_statements = split_sql_statements(sql_content)

            for i, statement in enumerate(sql_statements):
                try:
                    if statement.upper().startswith(("SELECT", "SHOW")):
                        result = await mysql_helper.execute_query(statement)
                        if result:
                            print(f"  [INFO] Query {i+1}/{len(sql_statements)} result: {result[0]}")
                        else:
                            print(f"  [OK] Executed query {i+1}/{len(sql_statements)}")
                    else:
                        await mysql_helper.execute_update(statement)
                        print(f"  [OK] Executed statement {i+1}/{len(sql_statements)}")
                except Exception as e:
                    msg = str(e).lower()
                    if "already exists" in msg or "duplicate entry" in msg:
                        print(f"  [WARN] Statement {i+1} skipped (already exists)")
                    else:
                        print(f"  [FAIL] Statement {i+1} failed: {e}")

            print("[OK] SQL script execution completed")
        else:
            print("[FAIL] SQL initialization script not found")
            return False

        # 데이터 검증
        print("[INFO] Verifying database setup...")

        currencies_count = await mysql_helper.execute_query("SELECT COUNT(*) as count FROM currencies")
        print(f"  [INFO] Currencies table: {currencies_count[0]['count']} records")

        history_count = await mysql_helper.execute_query("SELECT COUNT(*) as count FROM exchange_rate_history")
        print(f"  [INFO] Exchange rate history: {history_count[0]['count']} records")

        daily_count = await mysql_helper.execute_query("SELECT COUNT(*) as count FROM daily_exchange_rates")
        print(f"  [INFO] Daily aggregates: {daily_count[0]['count']} records")

        print("[SUCCESS] Local database initialization completed successfully!")
        return True

    except Exception as e:
        print(f"[FAIL] Database initialization failed: {e}")
        return False


async def main():
    """메인 함수"""
    print("Currency Service - Local Database Initialization")
    print("=" * 60)

    success = await init_local_database()

    if success:
        print("\n[SUCCESS] Database is ready for local development!")
        print("\n[INFO] Next steps:")
        print("  1. Start Redis: docker run -d -p 6379:6379 redis:7-alpine")
        print("  2. Run services: make run-currency")
        print("  3. Test API: curl http://localhost:8001/health")
        return 0
    else:
        print("\n[FAIL] Database initialization failed!")
        print("\n[INFO] Troubleshooting:")
        print("  1. Check MySQL is running: docker ps")
        print("  2. Check connection: mysql -h localhost -u currency_user -p")
        print("  3. Check database exists: SHOW DATABASES;")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[INFO] Database initialization interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] Initialization failed: {e}")
        sys.exit(1)
