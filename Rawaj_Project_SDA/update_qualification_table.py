from database.database import engine, Base
from database.models import QualificationRun


def update_qualification_table():
    print("Updating qualification_runs table...")

    # Drop ONLY the qualification_runs table
    QualificationRun.__table__.drop(
        bind=engine,
        checkfirst=True,
    )

    # Recreate it using the new model
    QualificationRun.__table__.create(
        bind=engine,
        checkfirst=True,
    )

    print("qualification_runs table updated successfully.")


if __name__ == "__main__":
    update_qualification_table()