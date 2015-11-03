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
    work_order_inventory = relationship('WorkOrderInventory', backref = 'inventory', uselist = False)

    def __repr__(self):
        return "<central inventory(product_name='%s', quantity='%s')>" \
            % (self.product_name, self.quantity)

    def __init__(self, product_name, quantity):
        self.product_name = product_name
        self.quantity = int(quantity)

    def as_dict(self, link = None):
        ret = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        if link:
            ret['link'] = link

        return ret


class Plan(Base):
    """
    Table for plan
    """

    def __repr__(self):
        return "<plan(id='%d', name= '%s', date='%s')>"\
            % (self.id, self.name, self.created_date)

    __tablename__ = 'plan'
    id = Column(Integer, primary_key = True)
    name = Column(String(32))
    created_date = Column(DateTime, default = datetime.datetime.utcnow)
    tasks = relationship('Task', backref = 'plan')

    def __init__(self, name):
        self.name = name

    def as_dict(self, link = None):
        ret = {}
        for col in self.__table__.columns:
            if type(col.type) == DateTime:
                ret[col.name] = str(getattr(self, col.name))
            else:
                ret[col.name] = getattr(self, col.name)
        if link:
            ret['link'] = link

        return ret


class Task(Base):
    """
    Table for tasks
    """

    __tablename__ = 'task'
    id = Column(Integer, primary_key = True)
    created_date = Column(DateTime, default = datetime.datetime.utcnow)
    plan_id = Column(Integer, ForeignKey('plan.id'), nullable = False)
    product_id = Column(Integer, nullable = False)
    target_quantity = Column(Integer, nullable = False)
#    status = Column(STATUS_ENUM, default = Status.NOTSTARTED)
    work_order = relationship('WorkOrder', backref = 'task', cascade = 'all, delete, delete-orphan')


    def __init__(self, plan_id, product_id, quantity):
        self.plan_id = plan_id
        self.product_id = product_id
        self.target_quantity = quantity

    def get_status(self):
        complete_wo = 0
        not_started_wo = 0

        for wo in self.work_order:
            if wo.status == Status.COMPLETED:
                complete_wo += 1
            elif wo.status == Status.NOTSTARTED:
                not_started_wo += 1

        num_wo = len(self.work_order)
        if num_wo > 0 and num_wo == complete_wo:
            return Status.COMPLETED
        elif num_wo == not_started_wo:
            return Status.NOTSTARTED
        else:
            return Status.INPROGRESS

    def get_total_actual(self):
        wo_actual_quantity = 0
        for wo in self.work_order:
            wo_actual_quantity += wo.actual_quantity

        return wo_actual_quantity

    def as_dict(self, include_wo = False, link = None):
        ret = {}
        for col in self.__table__.columns:
            if type(col.type) == DateTime:
                ret[col.name] = str(getattr(self, col.name))
            else:
                ret[col.name] = getattr(self, col.name)

        ret['status'] = self.get_status()
        if include_wo:
            ret['actual_quantity'] = self.get_total_actual()
        if link:
            ret['link'] = link

        return ret


class WorkOrder(Base):
    """
    Table for work orders
    """

    __tablename__ = 'work_order'
    id = Column(Integer, primary_key = True)
    created_date = Column(DateTime, default = datetime.datetime.utcnow)
    task_id = Column(Integer, ForeignKey('task.id'), nullable = False)
    status = Column(STATUS_ENUM, default = Status.NOTSTARTED)
    target_quantity = Column(Integer)
    actual_quantity = Column(Integer, default = 0)

    def as_dict(self, link = None):
        ret = {}
        for col in self.__table__.columns:
            if type(col.type) == DateTime:
                ret[col.name] = str(getattr(self, col.name))
            else:
                ret[col.name] = getattr(self, col.name)
        if link:
            ret['link'] = link
        return ret


class WorkOrderInventory(Base):
    """
    Table to track work orders and available inventory.
    Only Tasks can update the central inventory. This table is used to
    track work orders actual inventory used and prevent work orders for
    a specified product to overcommit on a product. We don't care about
    the actual work order, just the quantity.
    """

    __tablename__ = 'work_order_inventory'
    product_id = Column(Integer, ForeignKey('central_inventory.id'), primary_key = True)
    active_inventory = Column(Integer, default = 0)

    def __init__(self, product):
        self.product_id = product
        self.active_inventory = 0


# @event.listens_for(WorkOrder.status, 'set')
# def wo_updated(target, value, old_value, initiator):
#     print "::: in event handler", value
#     with utils.db_session() as session:
#         query_res = session.query(Task).get(target.task_id)
#         assert(query_res)
            
#         query_res.status = value
#         session.flush()

def init_db():
    """
    Create the db tables
    """
    Base.metadata.create_all(engine)
