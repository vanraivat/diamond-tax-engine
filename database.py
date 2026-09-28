from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

engine = create_engine('sqlite:///ca_database.db', echo=False)
Base = declarative_base()

class Client(Base):
    __tablename__ = 'clients'
    id = Column(Integer, primary_key=True)
    company_name = Column(String, nullable=False)
    gstin = Column(String, unique=True)
    transactions = relationship("Transaction", back_populates="client")

class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'))
    date = Column(String)
    vendor = Column(String, index=True, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    payment_mode = Column(String)
    ledger_category = Column(String)
    
    # --- NEW COLUMNS FOR HUMAN OVERRIDE ---
    ca_status = Column(String, default="Pending Review")
    ca_notes = Column(String, default="")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    client = relationship("Client", back_populates="transactions")
    audit_flags = relationship("AuditFlag", back_populates="transaction")

class AuditFlag(Base):
    __tablename__ = 'audit_flags'
    id = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey('transactions.id'))
    flag_description = Column(String, nullable=False)
    severity = Column(String)
    transaction = relationship("Transaction", back_populates="audit_flags")

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)