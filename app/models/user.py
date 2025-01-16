class User(Base):
    __tablename__ = "users"

    locale = Column(String(10), nullable=False, server_default="ko")  # 기본값은 한국어
