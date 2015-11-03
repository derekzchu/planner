from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.schema import CheckConstraint
import datetime

Base = declarative_base()
engine = create_engine('sqlite:///planner.db', echo=True)

class Status(object):
    NOTSTARTED = 'not started'
    INPROGRESS = 'in progress'
    COMPLETED = 'completed'
 
STATUS_ENUM = Enum(Status.NOTSTARTED, Status.INPROGRESS, Status.COMPLETED)   

class Inventory(Base):
    """
    Table for central inventory
    """
    __tablename__ = 'central_inventory'
    id = Column(Integer, primary_key = True)
    product_name = Column(String)
    quantity = Column(Integer, CheckConstraint('quantity >= 0'))

    def __repr__(self):
        return "<central inventory(product_name='%s', quantity='%s')>" \
            % (self.product_name, self.quantity)

    def __init__(self, product_name, quantity):
        self.product_name = product_name
        self.quantity = int(quantity)

    def as_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


def init_db():
    """
    Create the db tables
    """
    Base.metadata.create_all(engine)
