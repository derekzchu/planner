from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker
from models import engine, Inventory, Plan, Task, WorkOrder


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

def clear_dbs():
    """
    Delete any existing plans
    """
    with db_session() as session:
        session.query(Inventory).delete()
