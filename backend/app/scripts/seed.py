from app.db.session import SessionLocal
from app.services.keyword_seed import seed_all


def main() -> None:
    with SessionLocal() as db:
        result = seed_all(db)
    print(result)


if __name__ == "__main__":
    main()

