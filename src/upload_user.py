import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, Text, TIMESTAMP
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func

load_dotenv(override=True)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    kis_app_key = Column(Text, nullable=False)
    kis_app_secret = Column(Text, nullable=False)
    kis_access_token = Column(Text, nullable=True)
    account_no = Column(Text, nullable=False)
    investor_type = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


def upload_sample_user():
    engine = create_engine(os.environ["DATABASE_URL"])
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    # 샘플 데이터 생성
    user = User(
        id=1,
        kis_app_key=os.getenv("KIS_APP_KEY"),
        kis_app_secret=os.getenv("KIS_APP_SECRET"),
        kis_access_token=os.getenv("KIS_ACCESS_TOKEN"),
        account_no=os.getenv("KIS_ACCOUNT_NO"),
        investor_type="beginner"
    )
    session.add(user)
    session.commit()
    session.close()
    print("샘플 사용자 데이터가 업로드되었습니다.")

if __name__ == "__main__":
    upload_sample_user()
