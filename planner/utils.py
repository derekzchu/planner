from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker
from models import engine, Inventory, Plan, Task, WorkOrder, WorkOrderInventory


@contextmanager
def db_session():
    """
    transactional scope for db operations
    """
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
        session.commit()

    except:
        session.rollback()
        raise

    finally:
        session.close()


def populate_inventory():
    """
    populate db with inventory
    """
    with open('inventory.txt') as fobj:
        inventory = fobj.read().strip()

    with db_session() as session:
        for item in inventory.split('\n'):
            item = item.split(',')
            row = Inventory(product_name = item[0], quantity = item[1])
            session.add(row)

def sum_actual_quantity(task):
    sum = 0

    if len(task.work_order) == 0:
        return sum

    for work_order in task.order_order:
        sum += work_order.actual_quantity

    return sum

def clear_dbs():
    """
    Delete any existing plans
    """
    with db_session() as session:
        session.query(Inventory).delete()
        session.query(Plan).delete()
        session.query(Task).delete()
        session.query(WorkOrder).delete()
        session.query(WorkOrderInventory).delete()
